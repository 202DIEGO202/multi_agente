"""Verificación real del producto dentro de Docker: construir, levantar en orden y probar.

No publica puertos, así puede correr mientras hay una instancia activa, y siempre limpia sus
contenedores. Si Docker no está disponible lo informa como advertencia: no es un error del código.
"""

import asyncio
import re
import secrets
import subprocess
from pathlib import Path

from app.services.scaffold import compose_file, project_key

COMPOSE_NAME = "docker-compose.verificacion.yml"


def attribute(text, has_panel):
    """Agente responsable según el texto del error (salida de Docker o pytest).

    Docker indica el servicio que falló en la línea "target <servicio>:"; esa señal manda sobre
    cualquier palabra que aparezca en el registro.
    """
    failed = set(re.findall(r"container \S*-(portal|panel|backend|db)-\d+ exited", text))
    failed |= set(re.findall(r"-(portal|panel|backend|db)-\d+ Error", text))
    if failed:
        targets = failed
    else:
        targets = set(re.findall(r"target (portal|panel|backend|db)", text))

    if targets:
        agents = []
        if "portal" in targets:
            agents.append("desarrollador_portal")
        if "panel" in targets and has_panel:
            agents.append("desarrollador_panel")
        if "backend" in targets:
            agents.append("desarrollador_backend")
        if "db" in targets:
            agents.append("desarrollador_datos")
        return agents or ["desarrollador_backend"]
    low = text.lower()
    if "portal" in low:
        return ["desarrollador_portal"]
    if has_panel and "panel" in low:
        return ["desarrollador_panel"]
    if "init.sql" in low or "postgres" in low:
        return ["desarrollador_datos"]
    if "pytest" in low or "test_" in low or "assert" in low:
        return ["desarrollador_backend", "agente_pruebas"]
    return ["desarrollador_backend"]


def unavailable(text):
    low = text.lower()
    return any(
        marker in low
        for marker in (
            "cannot connect",
            "docker daemon",
            "error during connect",
            "is the docker daemon",
        )
    )


def tail(text, size=1500):
    return (text or "").strip()[-size:]


async def run_check(app_dir, name, has_panel):
    """Devuelve {'disponible', 'errores': [{agente, codigo, descripcion}], 'resumen'}."""
    app_dir = Path(app_dir)
    project = project_key(name)
    (app_dir / COMPOSE_NAME).write_text(
        compose_file(project, has_panel, ".", publish=False), encoding="utf-8", newline="\n"
    )
    env = app_dir / ".env"
    if not env.exists():
        env.write_text(
            f"POSTGRES_PASSWORD={secrets.token_urlsafe(18)}\nADMIN_API_TOKEN={secrets.token_urlsafe(32)}\nPORTAL_PORT=8100\n"
            + ("PANEL_PORT=8101\n" if has_panel else ""),
            encoding="utf-8",
        )
    services = ["db", "backend", "portal"] + (["panel"] if has_panel else []) + ["edge"]

    async def compose(args, timeout):
        """Nunca lanza excepciones: un timeout o Docker caído es un resultado de verificación."""
        command = ["docker", "compose", "-p", project, "-f", COMPOSE_NAME, *args]
        try:
            return await asyncio.to_thread(
                subprocess.run,
                command,
                cwd=app_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(
                command,
                124,
                "",
                f"Tiempo agotado ({timeout} s): docker compose {' '.join(args[:2])}",
            )
        except OSError as exc:
            return subprocess.CompletedProcess(
                command, 127, "", f"Cannot connect: Docker no está disponible ({exc})"
            )

    def error(agentes, codigo, text):
        return [
            {"agente": agente, "codigo": codigo, "descripcion": tail(text)} for agente in agentes
        ]

    try:
        try:
            config = await compose(["config", "-q"], 120)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {
                "disponible": False,
                "errores": [],
                "resumen": f"Docker no respondió ({type(exc).__name__})",
            }
        if config.returncode:
            if unavailable(config.stderr):
                return {
                    "disponible": False,
                    "errores": [],
                    "resumen": "El servicio Docker no está activo",
                }
            return {
                "disponible": True,
                "errores": error(["desarrollador_backend"], "CONFIG_COMPOSE", config.stderr),
                "resumen": "docker compose config falló",
            }

        up = await compose(["up", "-d", "--build", "--wait", *services], 1200)
        if up.returncode:
            text = (up.stdout or "") + (up.stderr or "")
            agents = attribute(text, has_panel)
            return {
                "disponible": True,
                "errores": error(agents, "EJECUCION_CONSTRUCCION", text),
                "resumen": "El producto no se construyó o no arrancó en orden",
            }

        tests = await compose(["exec", "-T", "backend", "pytest", "-q", "--tb=short"], 300)
        lines = [line for line in (tests.stdout or "").strip().splitlines() if line.strip()]
        summary = lines[-1] if lines else "pytest sin salida"
        errors = []
        if tests.returncode == 0 and not re.search(r"\b[1-9]\d* passed\b", tests.stdout or ""):
            errors = error(["agente_pruebas"], "PRUEBAS_NO_EJECUTADAS", "La suite no acreditó ninguna prueba aprobada; pruebas omitidas no verifican el producto.")
        if tests.returncode:
            text = (tests.stdout or "") + (tests.stderr or "")
            errors = error(["desarrollador_backend", "agente_pruebas"], "PRUEBAS_FALLIDAS", text)
            logs = await compose(["logs", "--no-color", "--tail", "35", "db"], 30)
            database_log = (logs.stdout or "") + (logs.stderr or "")
            db_errors = [line for line in database_log.splitlines() if "ERROR:" in line or "DETAIL:" in line]
            if db_errors:
                errors += error(["desarrollador_datos", "desarrollador_backend"], "ERROR_BASE_DATOS", "\n".join(db_errors))
        return {"disponible": True, "errores": errors, "resumen": summary}
    finally:
        try:
            await compose(["down", "-v", "--remove-orphans"], 300)
        except OSError:
            pass
