"""Despliegue remoto automático tras aprobar una construcción.

Equivalencias con "Instancia local" (ver instance.py), pero en vez de correr
`docker compose` en esta misma máquina, lo corre en un servidor remoto (p.ej. un VPS)
por SSH/rsync: red privada → red interna de Docker en el servidor remoto; balanceador →
servicio edge (nginx), publicado en 0.0.0.0 para ser alcanzable desde internet; secretos →
archivo .env que se escribe solo en el servidor remoto, nunca se imprime ni se audita aquí.

Esta función es un no-op seguro si DEPLOY_REMOTE_ENABLED no está activo (ver config.py):
ningún proyecto se ve afectado a menos que el usuario configure explícitamente un servidor.

Requiere que el proceso de Trama tenga alcance real de red (SSH saliente) al servidor
remoto; no funciona desde un entorno sandbox sin salida a internet.
"""

import asyncio
import secrets
import shlex
import subprocess
import time
from pathlib import Path

import httpx

from app.services.instance import busy, read_env, write_env
from app.services.scaffold import compose_file, edge_conf

TIMEOUT_SSH = 60
TIMEOUT_RSYNC = 300
TIMEOUT_COMPOSE_UP = 900
TIMEOUT_PYTEST = 900


class RemoteDeployer:
    def __init__(self, events, root, settings):
        self.events = events
        self.root = Path(root)
        self.settings = settings

    def enabled(self):
        return bool(self.settings.deploy_remote_enabled and self.settings.deploy_remote_host)

    def folder(self, name):
        """Carpeta LOCAL (en esta máquina) donde se guarda únicamente el registro de
        puertos/secretos asignados a esta instancia remota; los archivos de la aplicación
        viven en el servidor remoto, no aquí."""
        return self.root / "infraestructura-remota" / "instancias" / name

    def remote_path(self, name):
        base = self.settings.deploy_remote_base_dir.rstrip("/") or "~/despliegues"
        return f"{base}/{name}"

    def ssh_base(self):
        cmd = ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "BatchMode=yes"]
        if self.settings.deploy_remote_key_path:
            cmd += ["-i", self.settings.deploy_remote_key_path]
        cmd.append(f"{self.settings.deploy_remote_user}@{self.settings.deploy_remote_host}")
        return cmd

    async def ssh(self, remote_command, timeout=TIMEOUT_SSH, input_text=None):
        result = await asyncio.to_thread(
            subprocess.run,
            [*self.ssh_base(), remote_command],
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return result.returncode == 0, (result.stdout or "") + (result.stderr or "")

    async def rsync(self, src, dst_subpath, timeout=TIMEOUT_RSYNC):
        """Sincroniza src/ (carpeta local, debe terminar en / para copiar el contenido) hacia
        <remote_dir>/dst_subpath/ en el servidor remoto."""
        ssh_cmd = " ".join(shlex.quote(part) for part in self.ssh_base()[:-1])
        destino = self.ssh_base()[-1]
        result = await asyncio.to_thread(
            subprocess.run,
            [
                "rsync",
                "-az",
                "--delete",
                "-e",
                ssh_cmd,
                str(src) + ("" if str(src).endswith("/") else "/"),
                f"{destino}:{dst_subpath}/",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return result.returncode == 0, (result.stdout or "") + (result.stderr or "")

    def free_port(self, name):
        """Elige un puerto no usado por otra instancia remota ya registrada localmente.
        No podemos comprobar sockets del servidor remoto desde aquí sin SSH, así que evitamos
        colisiones con lo que esta misma máquina ya asignó antes."""
        used = set()
        base_dir = self.root / "infraestructura-remota" / "instancias"
        if base_dir.exists():
            for other in base_dir.iterdir():
                if other.name == name:
                    continue
                env = read_env(other / ".env")
                for key in ("PORTAL_PORT", "PANEL_PORT"):
                    if env.get(key) and env[key].isdigit():
                        used.add(int(env[key]))
        port = self.settings.deploy_remote_base_port
        while port in used or busy(port):
            port += 1
        return port

    async def stage(self, run_id, operation, description, job):
        start = time.perf_counter()
        await self.events.emit(run_id, "instancia", operation, "ejecutando", description)
        ok, detail = await job
        await self.events.emit(
            run_id,
            "instancia",
            operation,
            "completado" if ok else "error",
            description,
            {"detalle": detail[-1500:]},
            (time.perf_counter() - start) * 1000,
        )
        return {"paso": operation, "ok": ok, "detalle": detail[-1500:]}

    async def stage_result(self, run_id, operation, description, job, steps):
        """Como stage, pero además guarda el paso en steps y devuelve (ok, salida completa)
        para poder usar la salida después (p.ej. para resumir pytest)."""
        start = time.perf_counter()
        await self.events.emit(run_id, "instancia", operation, "ejecutando", description)
        ok, output = await job
        steps.append({"paso": operation, "ok": ok, "detalle": output[-1500:]})
        await self.events.emit(
            run_id,
            "instancia",
            operation,
            "completado" if ok else "error",
            description,
            {"detalle": output[-1500:]},
            (time.perf_counter() - start) * 1000,
        )
        return ok, output

    async def verify_http(self, host, portal, panel):
        lines, ok = [], True
        urls = [f"http://{host}:{portal}/api/health", f"http://{host}:{portal}/"]
        if panel:
            urls.append(f"http://{host}:{panel}/")
        async with httpx.AsyncClient(timeout=10) as client:
            for url in urls:
                for _ in range(20):
                    try:
                        response = await client.get(url)
                        if response.status_code < 400:
                            break
                    except httpx.HTTPError:
                        pass
                    await asyncio.sleep(3)
                try:
                    response = await client.get(url)
                    lines.append(f"{url} → {response.status_code}")
                    ok = ok and response.status_code < 400
                except httpx.HTTPError:
                    lines.append(f"{url} → sin respuesta")
                    ok = False
        return ok, "\n".join(lines)

    async def deploy(self, run_id, slug_name, version, app_dir, has_panel):
        name = f"{slug_name}-v{version}"
        project = f"vps-{name}"[:60]
        host = self.settings.deploy_remote_host
        remote_dir = self.remote_path(name)
        local_record = self.folder(name)
        local_record.mkdir(parents=True, exist_ok=True)
        env = read_env(local_record / ".env")
        env.setdefault("POSTGRES_PASSWORD", secrets.token_hex(24))
        env.setdefault("ADMIN_API_TOKEN", secrets.token_hex(32))
        portal = int(env.get("PORTAL_PORT") or self.free_port(name))
        env["PORTAL_PORT"] = str(portal)
        panel = None
        if has_panel:
            env.setdefault("PANEL_PORT", str(portal + 1))
            panel = int(env["PANEL_PORT"])
        write_env(local_record / ".env", env)

        steps = []

        async def done(operation, description, job):
            result = await self.stage(run_id, operation, description, job)
            steps.append(result)
            return result["ok"]

        async def prepare():
            ok, detail = await self.ssh(
                f"mkdir -p {shlex.quote(remote_dir)}/backend {shlex.quote(remote_dir)}/portal "
                f"{shlex.quote(remote_dir)}/panel {shlex.quote(remote_dir)}/db {shlex.quote(remote_dir)}/edge"
            )
            if not ok:
                return False, detail
            compose = compose_file(project, has_panel, ".", publish=True, bind_host="0.0.0.0")
            ok, detail2 = await self.ssh(f"cat > {shlex.quote(remote_dir)}/compose.yaml", input_text=compose)
            if not ok:
                return False, detail + detail2
            ok, detail3 = await self.ssh(f"cat > {shlex.quote(remote_dir)}/edge/nginx.conf", input_text=edge_conf(has_panel))
            if not ok:
                return False, detail + detail2 + detail3
            env_text = "".join(f"{k}={v}\n" for k, v in env.items())
            ok, detail4 = await self.ssh(f"cat > {shlex.quote(remote_dir)}/.env", input_text=env_text)
            return ok, detail + detail2 + detail3 + detail4

        async def sync(sub):
            local_src = Path(app_dir) / sub
            if not local_src.exists():
                return True, f"{sub}: sin cambios (no existe localmente)"
            return await self.rsync(local_src, f"{remote_dir}/{sub}")

        async def compose_cmd(args):
            cmd = (
                f"cd {shlex.quote(remote_dir)} && docker compose -p {shlex.quote(project)} "
                f"-f compose.yaml {' '.join(shlex.quote(a) for a in args)}"
            )
            return await self.ssh(cmd, timeout=TIMEOUT_COMPOSE_UP)

        status, summary = "error", "No se ejecutaron las pruebas"
        if await done("preparar_instancia_remota", "Preparando carpetas y configuración en el servidor remoto", prepare()):
            subs = ["backend", "portal", "db"] + (["panel"] if has_panel else [])
            sync_ok = True
            for sub in subs:
                if not await done(f"sincronizar_{sub}", f"Copiando {sub} al servidor remoto", sync(sub)):
                    sync_ok = False
                    break
            if sync_ok and await done(
                "balanceador_remoto",
                "Levantando la aplicación en el servidor remoto (puede tardar en el primer build)",
                compose_cmd(["up", "-d", "--build", "--wait"]),
            ):
                if await done(
                    "verificacion_http_remota",
                    "Comprobando respuestas públicas de cada aplicación",
                    self.verify_http(host, portal, panel),
                ):
                    tests_ok, full_out = await self.stage_result(
                        run_id,
                        "pruebas_remotas",
                        "Pruebas del backend dentro del servidor remoto",
                        compose_cmd(["exec", "-T", "backend", "pytest", "-q", "--tb=short"]),
                        steps,
                    )
                    lines = [line for line in full_out.strip().splitlines() if line.strip()]
                    summary = lines[-1] if lines else "pytest sin salida"
                    status = "completado" if tests_ok else "con_fallos"

        urls = {"portal": f"http://{host}:{portal}", "api": f"http://{host}:{portal}/api/health"}
        if panel:
            urls["panel"] = f"http://{host}:{panel}"
        return {
            "estado": status,
            "proyecto": project,
            "urls": urls,
            "puertos": {"portal": portal, **({"panel": panel} if panel else {})},
            "pasos": steps,
            "pruebas": summary,
            "admin_env": str(local_record / ".env"),
            "servidor": host,
            "carpeta_remota": remote_dir,
        }
