"""Fase 5: contexto por aplicación, versiones inmutables, carpetas del proyecto y notificaciones."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from psycopg.types.json import Jsonb

from app.config import ROOT
from app.services.construction_rules import aplicaciones, is_privileged
from app.services.diagrams import build_views
from app.services.diagrams import files as architecture_files
from app.services.instance import InstanceDeployer
from app.services.scaffold import STACK, project_key, readme_app, scaffold_files, slug
from app.services.workflow_policy import automatic_approval_allowed

__all__ = ["ConstructionService", "build_context", "project_key", "scaffold_files"]


def trim(text, size=300):
    text = text or ""
    return text if len(text) <= size else text[: size - 1] + "…"


def build_context(project, architecture, backlog, baseline, mockups):
    """Todo lo que necesitan los agentes, con cada pantalla e historia asignada a su aplicación."""
    actors = architecture.get("actores", [])
    stories = backlog["historias"]
    screens = (mockups or {}).get("diseno", {}).get("pantallas", [])
    screen_apps, story_sides, has_panel = aplicaciones(screens, stories, actors)
    software = architecture["software"]
    aplicaciones_info = {
        "portal": "Usuarios del producto: funciones y datos públicos definidos en sus historias. Sin acceso administrativo."
    }
    if has_panel:
        aplicaciones_info["panel"] = (
            "Operadores autorizados: funciones de gestión definidas en sus historias. Requiere autenticación administrativa."
        )
    return {
        "proyecto": project,
        "tiene_panel": has_panel,
        "aplicaciones": aplicaciones_info,
        "tecnologias": STACK,
        "actores": [
            {
                "id": a["id"],
                "nombre": a.get("nombre", ""),
                "descripcion": trim(a.get("descripcion", ""), 200),
                "aplicacion": "panel"
                if is_privileged(f"{a.get('nombre', '')} {a.get('descripcion', '')}")
                else "portal",
            }
            for a in actors
        ],
        "componentes": [
            {
                "id": c["id"],
                "nombre": c["nombre"],
                "tipo": c["tipo"],
                "contenedor": c["contenedor"],
                "responsabilidad": trim(c["responsabilidad"]),
                "operaciones": c["operaciones"],
                "historias": c["ids_historias"],
            }
            for c in software["componentes"]
        ],
        "historias": [
            {
                "id": h["id"],
                "titulo": h["titulo"],
                "quiero": h["quiero"],
                "aplicacion": story_sides.get(h["id"], "portal"),
                "criterios": [
                    {
                        "id": c["id"],
                        "dado": c["dado"],
                        "cuando": c["cuando"],
                        "entonces": c["entonces"],
                    }
                    for c in h["criterios_aceptacion"]
                ],
                "requisitos": [r["id"] for r in h["requisitos_origen"]],
            }
            for h in stories
        ],
        "pantallas": [
            {
                "id": s["id"],
                "titulo": s["titulo"],
                "descripcion": trim(s.get("descripcion", ""), 300),
                "aplicacion": screen_apps[s["id"]],
                "historias": s.get("ids_historias", []),
                "controles": [
                    {
                        "tipo": c["tipo"],
                        "etiqueta": c.get("etiqueta", ""),
                        "obligatorio": c.get("obligatorio", False),
                        "opciones": c.get("opciones", [])[:12],
                        "criterios": c.get("ids_criterios", []),
                        "destino": c.get("destino"),
                    }
                    for c in s["controles"]
                ],
            }
            for s in screens
        ],
        "requisitos": [
            {"id": r["id"], "descripcion": r["descripcion"]}
            for r in (baseline or {}).get("requisitos", [])
        ],
        "reglas_negocio": [
            {"id": i["id"], "descripcion": i["descripcion"]}
            for group in ("reglas_negocio", "restricciones", "decisiones")
            for i in (baseline or {}).get(group, [])
        ],
        "reglas": [
            {
                "id": a["id"],
                "atributo": a["atributo"],
                "escenario": trim(a["escenario"], 200),
                "medida": a["medida"],
            }
            for a in software["atributos_calidad"]
        ],
        "nodos_nube": [
            {
                "id": n["id"],
                "tipo": n["tipo"],
                "tecnologia": n["tecnologia"],
                "replicas": n["replicas"],
            }
            for n in architecture["infraestructura"]["nodos"]
            if n["entorno"] == "nube"
        ],
    }


def report(content):
    findings = (
        "\n".join(
            f"- **{f['severidad']}** · {f['agente']} · {f['codigo']}: {f['descripcion']} {('`' + f['archivo'] + '`') if f.get('archivo') else ''}"
            for f in content["validacion"]["observaciones"]
        )
        or "- Sin observaciones."
    )
    cases = "\n".join(
        f"| {t['id']} | {t['criterio']} | `{t['archivo']}` | {t['descripcion']} |"
        for t in content["casos_prueba"]
    )
    usage = "\n".join(
        f"| {agent} | {u['llamadas']} | {u['entrada']} | {u['salida']} | {u['ms'] / 1000:.1f} s |"
        for agent, u in content["consumo"].items()
    )
    return f"""# Reporte de construcción v{content["version_construccion"]}

Aplicaciones: {", ".join(content["aplicaciones"])}. Arquitectura v{content["version_arquitectura_origen"]}, backlog v{content["version_backlog_origen"]}.

## Validación (reglas, ejecución real en Docker y revisión)
{findings}

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
{cases}

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
{usage}
"""


class ConstructionService:
    def __init__(self, db, events, settings, mockups=None):
        self.db, self.events, self.settings = db, events, settings
        self.mockups = mockups
        self.instances = InstanceDeployer(events, ROOT)

    def base(self, project):
        return Path(self.settings.workspace_dir) / slug(project)

    def candidate_dir(self, project, version):
        return self.base(project) / "aplicacion" / f"v{version}"

    def write_candidate(self, project, version, files, summary):
        """Escribe el código candidato. Cada iteración lo sobrescribe: el último estado es el entregado."""
        target = self.candidate_dir(project, version).resolve()
        contents = {**files, "README.md": readme_app(summary, version)}
        manifest = target / ".generated-files.json"
        previous = json.loads(manifest.read_text("utf-8")) if manifest.exists() else []
        def safe(path):
            file = (target / path).resolve()
            if not file.is_relative_to(target) or file == target or Path(path).is_absolute() or ".env" in Path(path).parts or path == ".generated-files.json":
                raise ValueError("Ruta de archivo generado no admitida")
            return file
        destinations = {path: safe(path) for path in contents}
        removed = [safe(path) for path in previous if path not in contents]
        for path, text in contents.items():
            file = destinations[path]
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text, encoding="utf-8", newline="\n")
        for file in removed:
            if file.is_file():
                file.unlink()
        manifest.write_text(json.dumps(sorted(contents)), encoding="utf-8")
        return str(target)

    async def notify(self, pid, kind, title, message, link=None, run_id=None):
        await self.db.execute(
            "INSERT INTO notifications(project_id,kind,title,message,link,execution_id) VALUES(%s,%s,%s,%s,%s,%s)",
            (pid, kind, title, message, link, run_id),
        )

    async def start(self, pid, request):
        async with self.db.pool.connection() as conn, conn.transaction():
            await conn.execute("SELECT id FROM projects WHERE id=%s FOR UPDATE", (pid,))
            prior = await (
                await conn.execute(
                    "SELECT id,input FROM executions WHERE project_id=%s AND kind='construccion' AND request_id=%s",
                    (pid, request["id_solicitud"]),
                )
            ).fetchone()
            if prior:
                if prior["input"]["request"] != request:
                    raise ValueError("La solicitud ya se usó con otros datos")
                return str(prior["id"]), False
            if await (
                await conn.execute(
                    "SELECT 1 FROM executions WHERE project_id=%s AND kind='construccion' AND status IN ('pendiente','ejecutando')",
                    (pid,),
                )
            ).fetchone():
                raise ValueError("Ya hay una construcción en curso")
            arch = await (
                await conn.execute(
                    "SELECT r.payload FROM architecture_revisions r JOIN architecture_decisions d USING(project_id,version) "
                    "WHERE r.project_id=%s AND r.version=%s AND d.status IN ('aprobado_por_humano','validado_automaticamente')",
                    (pid, request["version_arquitectura"]),
                )
            ).fetchone()
            if not arch:
                raise ValueError("Primero apruebe esa versión de la arquitectura")
            architecture = arch["payload"]
            if self.mockups:
                await self.mockups.source(conn, pid, architecture["version_backlog_origen"])
            backlog = await (
                await conn.execute(
                    "SELECT payload FROM backlog_publications WHERE project_id=%s AND version=%s",
                    (pid, architecture["version_backlog_origen"]),
                )
            ).fetchone()
            baseline = await (
                await conn.execute(
                    "SELECT payload FROM baselines WHERE project_id=%s AND version=%s",
                    (pid, backlog["payload"]["version_linea_base_origen"]),
                )
            ).fetchone()
            mockups = await (
                await conn.execute(
                    "SELECT r.payload, d.status AS decision FROM mockup_revisions r "
                    "LEFT JOIN mockup_decisions d USING(project_id,version) "
                    "WHERE r.project_id=%s AND r.backlog_version=%s AND coalesce(d.status,'') <> 'descartado' "
                    "ORDER BY coalesce(d.status IN ('aprobado_por_humano','validado_automaticamente'), false) DESC, r.version DESC LIMIT 1",
                    (pid, architecture["version_backlog_origen"]),
                )
            ).fetchone()
            project = await (
                await conn.execute("SELECT name FROM projects WHERE id=%s", (pid,))
            ).fetchone()
            head = await (
                await conn.execute(
                    "SELECT coalesce(max(version),0) AS v FROM construction_revisions WHERE project_id=%s",
                    (pid,),
                )
            ).fetchone()
            datos = build_context(
                project["name"],
                architecture,
                backlog["payload"],
                baseline["payload"] if baseline else {},
                mockups["payload"] if mockups else None,
            )
            context = {
                "datos": datos,
                "workspace_key": f"{str(pid).replace('-', '')[:12]}-{project['name']}",
                "version_arquitectura": request["version_arquitectura"],
                "version_backlog": architecture["version_backlog_origen"],
                "version_linea_base": backlog["payload"]["version_linea_base_origen"],
                "version_mockups": mockups["payload"]["version_mockup"] if mockups else None,
                "mockups_aprobados": bool(mockups and mockups["decision"] in ("aprobado_por_humano", "validado_automaticamente")),
                "head": head["v"],
                "version_candidata": head["v"] + 1,
            }
            if request.get("reutilizar_candidato"):
                prior_candidate = await (await conn.execute(
                    "SELECT payload FROM construction_revisions WHERE project_id=%s ORDER BY version DESC LIMIT 1", (pid,)
                )).fetchone()
                if prior_candidate:
                    candidate = prior_candidate["payload"]
                    if candidate["version_arquitectura_origen"] == request["version_arquitectura"] and candidate.get("version_mockups_origen") == context["version_mockups"]:
                        context["candidato_anterior"] = candidate
            run_id = str(uuid4())
            await conn.execute(
                "INSERT INTO executions(id,project_id,kind,request_id,input) VALUES(%s,%s,'construccion',%s,%s)",
                (
                    run_id,
                    pid,
                    request["id_solicitud"],
                    Jsonb({"project_id": str(pid), "request": request, "context": context}),
                ),
            )
        return run_id, True

    async def persist(self, state):
        pid, run_id, ctx = state["project_id"], state["execution_id"], state["context"]
        datos = ctx["datos"]
        auto_approved = False
        async with self.db.pool.connection() as conn, conn.transaction():
            project = await (await conn.execute(
                "SELECT mode FROM projects WHERE id=%s FOR UPDATE", (pid,)
            )).fetchone()
            if not project:
                raise LookupError("Proyecto no encontrado")
            existing = await (
                await conn.execute(
                    "SELECT payload FROM construction_revisions WHERE execution_id=%s", (run_id,)
                )
            ).fetchone()
            if existing:
                return existing["payload"]
            latest = await (
                await conn.execute(
                    "SELECT coalesce(max(version),0) AS v FROM construction_revisions WHERE project_id=%s",
                    (pid,),
                )
            ).fetchone()
            if latest["v"] != ctx["head"]:
                raise ValueError("Cambió la construcción durante la ejecución")
            approved_arch = await (await conn.execute(
                "SELECT 1 FROM architecture_decisions WHERE project_id=%s AND version=%s "
                "AND status IN ('aprobado_por_humano','validado_automaticamente')",
                (pid, ctx["version_arquitectura"]),
            )).fetchone()
            if not approved_arch:
                raise ValueError("La arquitectura dejó de estar aprobada; vuelva a revisarla")
            if self.mockups:
                await self.mockups.source(conn, pid, ctx["version_backlog"])
            arch = await (
                await conn.execute(
                    "SELECT payload FROM architecture_revisions WHERE project_id=%s AND version=%s",
                    (pid, ctx["version_arquitectura"]),
                )
            ).fetchone()
            version = ctx["version_candidata"]
            content = {
                "version_esquema": "5.0",
                "version_construccion": version,
                "id_proyecto": pid,
                "nombre_proyecto": datos["proyecto"],
                "workspace_key": ctx.get("workspace_key", datos["proyecto"]),
                "id_ejecucion": run_id,
                "fecha": datetime.now(UTC).isoformat(),
                "version_arquitectura_origen": ctx["version_arquitectura"],
                "version_backlog_origen": ctx["version_backlog"],
                "version_mockups_origen": ctx["version_mockups"],
                "mockups_aprobados": ctx["mockups_aprobados"],
                "instrucciones": state["request"]["instrucciones"],
                "aplicaciones": ["portal", *(["panel"] if datos["tiene_panel"] else [])],
                "archivos": {p: c.replace("\x00", "") for p, c in state["files"].items()},
                "tablas": state["data"]["tablas"],
                "endpoints": state["backend"]["endpoints"],
                "pantallas": {
                    "portal": state["portal"].get("pantallas", []),
                    "panel": (state.get("panel") or {}).get("pantallas", []),
                },
                "casos_prueba": state["tests"]["casos"],
                "validacion": state["report"],
                "correcciones_automaticas": state.get("corrections", 0),
                "consumo": state.get("usage", {}),
            }
            await conn.execute(
                "INSERT INTO construction_revisions(project_id,version,architecture_version,execution_id,payload) VALUES(%s,%s,%s,%s,%s)",
                (pid, version, ctx["version_arquitectura"], run_id, Jsonb(content)),
            )
            await conn.execute(
                "INSERT INTO events(execution_id,component,operation,status,description,data) "
                "VALUES(%s,'construccion','guardar_revision','completado','Construcción versionada guardada',%s)",
                (run_id, Jsonb({"version_construccion": version, "consumo": content["consumo"]})),
            )
            if automatic_approval_allowed(
                project["mode"],
                content["validacion"]["puede_publicar"],
                complete=content["validacion"].get("revision_semantica", False),
                runtime_verified=content["validacion"].get("runtime_verificado", False),
                observations=content["validacion"].get("observaciones", []),
            ):
                note = "Validado automáticamente: revisión funcional y pruebas de ejecución completadas sin bloqueos. El despliegue requiere acción explícita."
                await conn.execute(
                    "INSERT INTO construction_decisions(project_id,version,status,note) VALUES(%s,%s,'validado_automaticamente',%s)",
                    (pid, version, note),
                )
                await conn.execute(
                    "INSERT INTO events(execution_id,component,operation,status,description,data) "
                    "VALUES(%s,'construccion','decision_automatica','validado_automaticamente',%s,%s)",
                    (run_id, note, Jsonb({"version": version, "validacion": content["validacion"]})),
                )
                auto_approved = True
        await asyncio.to_thread(self.write_entregables, content, arch["payload"])
        ok = content["validacion"]["puede_publicar"]
        await self.notify(
            pid,
            "construccion",
            f"Construcción v{version} {'lista' if ok else 'con observaciones'}",
            "Código y pruebas en "
            + str(self.candidate_dir(content["workspace_key"], version))
            + (
                ". Validada automáticamente; ya puede iniciar el despliegue desde el botón."
                if auto_approved
                else ". La revisión humana debe aprobarla antes del despliegue."
                if ok
                else ". Revise los bloqueos antes de desplegar."
            ),
            "/construction",
            run_id,
        )
        return content

    def write_entregables(self, content, architecture):
        docs = (
            self.base(content.get("workspace_key", content["nombre_proyecto"]))
            / "entregables"
            / f"v{content['version_construccion']}"
        )
        docs.mkdir(parents=True, exist_ok=True)
        views = build_views(
            architecture["nombre_proyecto"],
            architecture.get("actores", []),
            architecture["software"],
            architecture["infraestructura"],
        )
        for name, text in architecture_files({**architecture, "vistas": views}).items():
            (docs / f"arquitectura-{name.lstrip('.')}").write_text(text, encoding="utf-8")
        (docs / "reporte-construccion.md").write_text(report(content), encoding="utf-8")

    async def list(self, pid):
        return await self.db.fetch(
            "SELECT r.version,r.architecture_version AS version_arquitectura,r.execution_id AS id_ejecucion,r.created_at AS fecha,"
            "d.status AS decision FROM construction_revisions r LEFT JOIN construction_decisions d USING(project_id,version) "
            "WHERE r.project_id=%s ORDER BY r.version DESC",
            (pid,),
        )

    async def get(self, pid, version):
        row = await self.db.one(
            "SELECT r.payload,d.status AS decision,d.note AS nota FROM construction_revisions r "
            "LEFT JOIN construction_decisions d USING(project_id,version) WHERE r.project_id=%s AND r.version=%s",
            (pid, version),
        )
        if not row:
            raise LookupError("Construcción no encontrada")
        deployment = await self.db.one(
            "SELECT status AS estado,ports AS puertos,result AS resultado,execution_id AS id_ejecucion,updated_at AS fecha "
            "FROM deployments WHERE project_id=%s AND version=%s",
            (pid, version),
        )
        name = row["payload"].get("workspace_key", row["payload"]["nombre_proyecto"])
        return {
            **row,
            "entorno": deployment,
            "carpetas": {
                "aplicacion": str(self.candidate_dir(name, version)),
                "entregables": str(self.base(name) / "entregables" / f"v{version}"),
            },
        }

    async def file(self, pid, version, path):
        payload = (await self.get(pid, version))["payload"]
        files = payload.get("archivos", {})
        if path not in files:
            raise LookupError("Archivo no encontrado")
        return {"ruta": path, "contenido": files[path]}

    async def review(self, pid, version, review):
        async with self.db.pool.connection() as conn, conn.transaction():
            await conn.execute("SELECT id FROM projects WHERE id=%s FOR UPDATE", (pid,))
            row = await (
                await conn.execute(
                    "SELECT payload FROM construction_revisions WHERE project_id=%s AND version=%s",
                    (pid, version),
                )
            ).fetchone()
            if not row:
                raise LookupError("Construcción no encontrada")
            if await (
                await conn.execute(
                    "SELECT 1 FROM construction_decisions WHERE project_id=%s AND version=%s",
                    (pid, version),
                )
            ).fetchone():
                raise ValueError("Esta construcción ya tiene una decisión registrada")
            if review.accion == "aprobar" and not row["payload"]["validacion"]["puede_publicar"]:
                raise ValueError("Corrija los bloqueos antes de aprobar la construcción")
            status = "aprobado_por_humano" if review.accion == "aprobar" else "descartado"
            await conn.execute(
                "INSERT INTO construction_decisions(project_id,version,status,note) VALUES(%s,%s,%s,%s)",
                (pid, version, status, review.nota),
            )
        return await self.get(pid, version)

    async def start_deploy(self, pid, version, request_id):
        content = (await self.get(pid, version))["payload"]
        if not content["validacion"]["puede_publicar"]:
            raise ValueError("La construcción tiene bloqueos; corríjalos antes de desplegar")
        decision = await self.db.one(
            "SELECT status FROM construction_decisions WHERE project_id=%s AND version=%s",
            (pid, version),
        )
        if not decision or decision["status"] not in ("aprobado_por_humano", "validado_automaticamente"):
            raise ValueError("Apruebe la construcción antes de desplegarla")
        if decision["status"] == "validado_automaticamente" and content["validacion"].get("observaciones"):
            raise ValueError("La construcción tiene observaciones pendientes de revisión humana; no puede desplegarse con una aprobación automática")
        if self.mockups:
            async with self.db.pool.connection() as conn:
                await self.mockups.source(conn, pid, content["version_backlog_origen"])
        async with self.db.pool.connection() as conn, conn.transaction():
            await conn.execute("SELECT id FROM projects WHERE id=%s FOR UPDATE", (pid,))
            prior = await (await conn.execute(
                "SELECT id,input FROM executions WHERE project_id=%s AND kind='despliegue' AND request_id=%s",
                (pid, request_id),
            )).fetchone()
            if prior:
                if prior["input"].get("version") != version:
                    raise ValueError("La solicitud de despliegue ya se usó para otra versión")
                return str(prior["id"]), False
            if await (await conn.execute(
                "SELECT 1 FROM executions WHERE project_id=%s AND kind='despliegue' AND status IN ('pendiente','ejecutando')",
                (pid,),
            )).fetchone():
                raise ValueError("Ya hay un despliegue en curso")
            run_id = str(uuid4())
            await conn.execute(
                "INSERT INTO executions(id,project_id,kind,request_id,input) VALUES(%s,%s,'despliegue',%s,%s)",
                (run_id, pid, request_id, Jsonb({"version": version})),
            )
        return run_id, True

    async def deploy(self, pid, version, run_id):
        """Instancia local: base de datos, backend, aplicaciones, balanceador, verificación y pruebas."""
        await self.events.status(run_id, "ejecutando")
        content = (await self.get(pid, version))["payload"]
        name = content.get("workspace_key", content["nombre_proyecto"])
        try:
            result = await self.instances.deploy(
                run_id,
                slug(name),
                version,
                self.candidate_dir(name, version),
                "panel" in content["aplicaciones"],
            )
        except (
            Exception
        ) as exc:  # El usuario recibe siempre el resultado, también ante fallos inesperados.
            result = {"estado": "error", "error": type(exc).__name__, "pasos": [], "urls": {}}
        status = result["estado"]
        await self.db.execute(
            "INSERT INTO deployments(project_id,version,execution_id,status,ports,result) VALUES(%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT(project_id,version) DO UPDATE SET execution_id=EXCLUDED.execution_id,status=EXCLUDED.status,"
            "ports=EXCLUDED.ports,result=EXCLUDED.result,updated_at=now()",
            (pid, version, run_id, status, Jsonb(result.get("puertos", {})), Jsonb(result)),
        )
        docs = self.base(name) / "entregables" / f"v{version}"
        docs.mkdir(parents=True, exist_ok=True)
        titles = {
            "completado": f"Instancia local v{version} lista",
            "con_fallos": f"Instancia local v{version} arriba con pruebas fallidas",
            "error": f"No se pudo desplegar la instancia v{version}",
        }
        urls = result.get("urls", {})
        message = (
            f"Portal: {urls.get('portal')}"
            + (f" · Panel: {urls['panel']}" if urls.get("panel") else "")
            + f" · Pruebas: {result.get('pruebas', 'no ejecutadas')}"
            if status != "error"
            else "Revise el detalle de la ejecución en Actividad de IA."
        )
        (docs / "resultado-instancia-local.md").write_text(
            f"# Instancia local v{version}\n\nEstado: **{status}**\n\n"
            + "".join(f"- {key}: {value}\n" for key, value in urls.items())
            + f"- Pruebas: {result.get('pruebas', 'no ejecutadas')}\n"
            + f"- Variables de administración: {result.get('admin_env', '')}\n\n"
            + "\n".join(
                f"## {p['paso']} ({'ok' if p['ok'] else 'falló'})\n```\n{p['detalle']}\n```"
                for p in result.get("pasos", [])
            ),
            encoding="utf-8",
        )
        await self.notify(pid, "despliegue", titles[status], message, "/construction", run_id)
        await self.events.status(run_id, "completado" if status != "error" else "error", result)

    async def stop(self, pid, version):
        content = (await self.get(pid, version))["payload"]
        result = await self.instances.stop(slug(content.get("workspace_key", content["nombre_proyecto"])), version)
        await self.db.execute(
            "UPDATE deployments SET status='detenido',updated_at=now() WHERE project_id=%s AND version=%s",
            (pid, version),
        )
        return result
