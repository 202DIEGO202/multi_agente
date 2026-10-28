"""Instancia local que simula una máquina EC2 en este equipo.

Equivalencias: instancia EC2 → carpeta infraestructura-local/instancias/<nombre> con su propio
Docker Compose; red privada → red interna de Docker (solo el balanceador publica puertos);
balanceador (ALB) → servicio edge (nginx); base de datos (RDS) → contenedor db con volumen;
secretos (Secrets Manager) → archivo .env fuera del código. El arranque respeta el orden:
base de datos, backend, aplicaciones, balanceador; después se verifica y se prueba.
"""

import asyncio
import os
import secrets
import socket
import subprocess
import time
from pathlib import Path

import httpx

from app.services.scaffold import compose_file


def read_env(path):
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def write_env(path, values):
    path.write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")


def busy(port):
    with socket.socket() as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def free_port(start, taken=()):
    port = start
    while port in taken or busy(port):
        port += 1
    return port


class InstanceDeployer:
    def __init__(self, events, root):
        self.events = events
        self.root = Path(root)

    def folder(self, name):
        return self.root / "infraestructura-local" / "instancias" / name

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
        """Como stage, pero guarda el paso y devuelve (ok, salida completa) para usarla después."""
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

    async def compose(self, folder, project, args, timeout=1800):
        result = await asyncio.to_thread(
            subprocess.run,
            ["docker", "compose", "-p", project, "-f", "compose.yaml", *args],
            cwd=folder,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return result.returncode == 0, (result.stdout or "") + (result.stderr or "")

    async def verify_http(self, portal, panel):
        lines, ok = [], True
        urls = [f"http://127.0.0.1:{portal}/api/health", f"http://127.0.0.1:{portal}/"]
        if panel:
            urls.append(f"http://127.0.0.1:{panel}/")
        async with httpx.AsyncClient(timeout=10) as client:
            for url in urls:
                for _ in range(15):
                    try:
                        response = await client.get(url)
                        if response.status_code < 400:
                            break
                    except httpx.HTTPError:
                        pass
                    await asyncio.sleep(2)
                try:
                    response = await client.get(url)
                    lines.append(f"{url} → {response.status_code}")
                    ok = ok and response.status_code < 400
                except httpx.HTTPError:
                    lines.append(f"{url} → sin respuesta")
                    ok = False
        return ok, "\n".join(lines)

    async def deploy(self, run_id, slug, version, app_dir, has_panel):
        name = f"{slug}-v{version}"
        project = f"ec2-{name}"[:60]
        folder = self.folder(name)
        folder.mkdir(parents=True, exist_ok=True)
        env = read_env(folder / ".env")
        env.setdefault("POSTGRES_PASSWORD", secrets.token_urlsafe(18))
        env.setdefault("ADMIN_API_TOKEN", secrets.token_urlsafe(32))
        portal = int(env.get("PORTAL_PORT") or free_port(8100))
        env["PORTAL_PORT"] = str(portal)
        panel = None
        if has_panel:
            panel = int(env.get("PANEL_PORT") or free_port(portal + 1, {portal}))
            env["PANEL_PORT"] = str(panel)
        rel = os.path.relpath(app_dir, folder).replace("\\", "/")

        steps = []

        async def done(operation, description, job):
            result = await self.stage(run_id, operation, description, job)
            steps.append(result)
            return result["ok"]

        async def prepare():
            write_env(folder / ".env", env)
            (folder / "compose.yaml").write_text(
                compose_file(project, has_panel, rel, publish=True), encoding="utf-8", newline="\n"
            )
            return True, f"Instancia {name} preparada en {folder}"

        async def up(services):
            return await self.compose(folder, project, ["up", "-d", "--build", "--wait", *services])

        status, summary = "error", "No se ejecutaron las pruebas"
        if await done(
            "preparar_instancia",
            "Preparando la instancia: red, secretos y configuración",
            prepare(),
        ):
            frontends = ["portal"] + (["panel"] if has_panel else [])
            stages = [
                ("base_de_datos", "Base de datos PostgreSQL (primero, con su volumen)", up(["db"])),
                ("backend", "API backend, conectada a la base de datos", up(["backend"])),
                (
                    "aplicaciones",
                    "Aplicaciones de cara al usuario: portal" + (" y panel" if has_panel else ""),
                    up(frontends),
                ),
                (
                    "balanceador",
                    "Balanceador de entrada (edge) y enrutamiento de /api",
                    up(["edge"]),
                ),
            ]
            ok_all = True
            for operation, description, job in stages:
                if not await done(operation, description, job):
                    ok_all = False
                    break
            if ok_all and await done(
                "verificacion_http",
                "Comprobando respuestas de cada aplicación",
                self.verify_http(portal, panel),
            ):
                tests_ok, out = await self.stage_result(
                    run_id,
                    "pruebas",
                    "Pruebas del backend dentro de la instancia",
                    self.compose(
                        folder,
                        project,
                        ["exec", "-T", "backend", "pytest", "-q", "--tb=short"],
                        900,
                    ),
                    steps,
                )
                lines = [line for line in out.strip().splitlines() if line.strip()]
                summary = lines[-1] if lines else "pytest sin salida"
                status = "completado" if tests_ok else "con_fallos"

        urls = {
            "portal": f"http://localhost:{portal}",
            "api": f"http://localhost:{portal}/api/health",
        }
        if panel:
            urls["panel"] = f"http://localhost:{panel}"
        return {
            "estado": status,
            "proyecto": project,
            "urls": urls,
            "puertos": {"portal": portal, **({"panel": panel} if panel else {})},
            "pasos": steps,
            "pruebas": summary,
            "admin_env": f"infraestructura-local/instancias/{name}/.env",
        }

    async def stop(self, slug, version):
        name = f"{slug}-v{version}"
        folder = self.folder(name)
        if not (folder / "compose.yaml").exists():
            return {
                "estado": "sin_instancia",
                "detalle": "No hay instancia desplegada para esta versión",
            }
        ok, out = await self.compose(folder, f"ec2-{name}"[:60], ["down"], 300)
        return {"estado": "detenido" if ok else "error", "detalle": out[-800:]}
