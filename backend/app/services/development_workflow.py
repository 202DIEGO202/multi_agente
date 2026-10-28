"""Durable coordinator. Agent graphs own their checkpoints; this layer owns stage handoffs."""

import asyncio
from uuid import UUID, uuid4, uuid5

from psycopg.types.json import Jsonb

APPROVED = {"aprobado_por_humano", "validado_automaticamente"}
PHASES = {
    "backlog": ("backlog_revisions", "backlog_decisions", "version_backlog", "version_linea_base_origen", "/backlog"),
    "mockups": ("mockup_revisions", "mockup_decisions", "version_mockup", "version_backlog_origen", "/mockups"),
    "arquitectura": ("architecture_revisions", "architecture_decisions", "version_arquitectura", "version_backlog_origen", "/architecture"),
    "construccion": ("construction_revisions", "construction_decisions", "version_construccion", "version_arquitectura_origen", "/construction"),
}


class WorkflowPause(Exception):
    def __init__(self, phase, message, link):
        super().__init__(message)
        self.phase, self.link = phase, link


def functional_fingerprint(items):
    return sorted((i["id"], i["version"]) for i in items if i.get("vigencia", "vigente") == "vigente")


class DevelopmentWorkflow:
    def __init__(self, app):
        self.app = app
        self.db, self.events = app.state.db, app.state.events

    async def start(self, pid, request):
        async with self.db.pool.connection() as conn, conn.transaction():
            project = await (await conn.execute(
                "SELECT mode FROM projects WHERE id=%s AND deleted_at IS NULL FOR UPDATE", (pid,)
            )).fetchone()
            if not project:
                raise LookupError("Proyecto no encontrado")
            prior = await (await conn.execute(
                "SELECT id,input FROM executions WHERE project_id=%s AND kind='flujo_completo' AND request_id=%s",
                (pid, request["id_solicitud"]),
            )).fetchone()
            if prior:
                if prior["input"] != request:
                    raise ValueError("La solicitud ya se utilizó con otro objetivo")
                return str(prior["id"]), False
            if await (await conn.execute(
                "SELECT 1 FROM executions WHERE project_id=%s AND status IN ('pendiente','ejecutando') LIMIT 1", (pid,)
            )).fetchone():
                raise ValueError("Espere a que termine la ejecución activa del proyecto")
            rid, cid = str(uuid4()), str(uuid4())
            await conn.execute("INSERT INTO conversations(id,project_id,title) VALUES(%s,%s,%s)",
                               (cid, pid, "Desarrollo: " + request["objetivo"][:55]))
            await conn.execute(
                "INSERT INTO executions(id,project_id,kind,request_id,input) VALUES(%s,%s,'flujo_completo',%s,%s)",
                (rid, pid, request["id_solicitud"], Jsonb(request)),
            )
            await conn.execute(
                "INSERT INTO development_workflows(id,project_id,mode,conversation_id) VALUES(%s,%s,%s,%s)",
                (rid, pid, project["mode"], cid),
            )
        return rid, True

    async def get(self, pid, rid):
        row = await self.db.one(
            "SELECT w.id,w.mode AS modo,w.conversation_id AS id_conversacion,w.progress AS pasos,"
            "e.status AS estado,e.input AS solicitud,e.output AS resultado,e.created_at AS fecha "
            "FROM development_workflows w JOIN executions e ON e.id=w.id WHERE w.id=%s AND w.project_id=%s",
            (rid, pid),
        )
        if not row:
            raise LookupError("Flujo no encontrado en este proyecto")
        return row

    async def resume(self, pid, rid, retry=False):
        workflow = await self.get(pid, rid)
        async with self.db.pool.connection() as conn, conn.transaction():
            project = await (await conn.execute("SELECT mode FROM projects WHERE id=%s AND deleted_at IS NULL FOR UPDATE", (pid,))).fetchone()
            if not project:
                raise LookupError("Proyecto no encontrado")
            if project["mode"] != workflow["modo"]:
                await conn.execute("UPDATE development_workflows SET mode=%s,updated_at=now() WHERE id=%s", (project["mode"], rid))
                await conn.execute("INSERT INTO events(execution_id,component,operation,status,description,data) VALUES(%s,'coordinador','cambiar_modo','completado','Se continúa con el modo elegido para el proyecto',%s)", (rid, Jsonb({"anterior": workflow["modo"], "nuevo": project["mode"]})))
            active = await (await conn.execute(
                "SELECT 1 FROM executions WHERE project_id=%s AND status IN ('pendiente','ejecutando')", (pid,)
            )).fetchone()
            if active:
                raise ValueError("Ya hay una ejecución activa; espere antes de continuar")
            if retry:
                row = await (await conn.execute("SELECT progress FROM development_workflows WHERE id=%s FOR UPDATE", (rid,))).fetchone()
                progress = row["progress"]
                failed = [(name, step) for name, step in progress.items() if name in PHASES and step.get("ejecucion") and not step.get("completado")]
                blocked = (workflow.get("resultado") or {}).get("fase")
                if not failed and workflow["estado"] == "esperando_revision" and blocked in PHASES and blocked in progress:
                    failed = [(blocked, progress[blocked])]
                if not failed:
                    raise ValueError("No hay una etapa fallida que requiera un nuevo intento")
                name, step = failed[-1]
                child = await (await conn.execute("SELECT status FROM executions WHERE id=%s", (step["ejecucion"],))).fetchone()
                if child["status"] not in ("error", "completado"):
                    raise ValueError("La etapa puede continuar desde su avance; no necesita repetirse")
                step.setdefault("intentos_anteriores", []).append(step["ejecucion"])
                step["reintentar"] = True
                step["completado"] = False
                await conn.execute("UPDATE development_workflows SET progress=%s,updated_at=now() WHERE id=%s", (Jsonb(progress), rid))
            result = await conn.execute(
                "UPDATE executions SET status='pendiente',finished_at=NULL WHERE id=%s "
                "AND status IN ('esperando_revision','error','interrumpido','pausado')", (rid,)
            )
            if not result.rowcount:
                raise ValueError("Este flujo no está detenido")

    async def save(self, rid, progress):
        await self.db.execute("UPDATE development_workflows SET progress=%s,updated_at=now() WHERE id=%s",
                              (Jsonb(progress), rid))

    async def child(self, rid, phase, child_id, graph, runner):
        await self.events.emit(rid, "coordinador", phase, "ejecutando", f"Ejecutando {phase}",
                               {"id_ejecucion_hija": child_id})
        row = await self.db.one("SELECT input,status FROM executions WHERE id=%s", (child_id,))
        if row["status"] != "completado":
            snapshot = await graph.aget_state({"configurable": {"thread_id": child_id}})
            initial = None if snapshot.values else {**row["input"], "execution_id": child_id}
            await runner(self.app, child_id, initial)
        result = await self.db.one("SELECT status,output FROM executions WHERE id=%s", (child_id,))
        if result["status"] != "completado":
            raise RuntimeError(f"La fase {phase} se detuvo; revise su ejecución y continúe este flujo")
        await self.events.emit(rid, "coordinador", phase, "completado", f"Resultado de {phase} guardado",
                               {"id_ejecucion_hija": child_id})

    async def analyze(self, pid, rid, workflow, progress):
        from app.api.routes import run_chat

        if "analisis" not in progress:
            child_id, mid = str(uuid5(UUID(rid), "analisis")), str(uuid5(UUID(rid), "mensaje"))
            message = (
                "Quiero definir una funcionalidad y crear sus requisitos para construir una aplicación completa. "
                "Consulta la documentación disponible y conserva las políticas vigentes. Extrae actores, "
                "requisitos y reglas comprobables. Resuelve dudas cuya respuesta esté documentada; pregunta "
                "solo por decisiones de negocio que falten. No inventes aprobaciones, permisos ni políticas. "
                "Distingue alcance inicial de mejoras opcionales. Objetivo del usuario:\n" + workflow["solicitud"]["objetivo"]
            )
            initial = {"project_id": str(pid), "conversation_id": str(workflow["id_conversacion"]),
                       "message_id": mid, "message": message, "execution_id": child_id}
            async with self.db.pool.connection() as conn, conn.transaction():
                await conn.execute(
                    "INSERT INTO executions(id,project_id,conversation_id,kind,input) VALUES(%s,%s,%s,'chat',%s) ON CONFLICT(id) DO NOTHING",
                    (child_id, pid, workflow["id_conversacion"], Jsonb(initial)),
                )
                await conn.execute(
                    "INSERT INTO messages(id,conversation_id,execution_id,role,content) VALUES(%s,%s,%s,'user',%s) ON CONFLICT DO NOTHING",
                    (mid, workflow["id_conversacion"], child_id, message),
                )
            progress["analisis"] = {"ejecucion": child_id}
            await self.save(rid, progress)
        step = progress["analisis"]
        if not step.get("completado"):
            await self.child(rid, "analisis", step["ejecucion"], self.app.state.analyst.graph, run_chat)
            step["completado"] = True
            await self.save(rid, progress)

    async def baseline(self, pid, workflow):
        state = await self.app.state.projects.state(pid)
        pending = [p for p in state["propuestas"] if p["estado"] in ("propuesto", "pendiente_aclaracion")]
        active = [i for i in state["elementos"] if i["vigencia"] == "vigente"]
        if pending or any(not c.get("fecha_resolucion") for c in state["contradicciones"]):
            raise WorkflowPause("requisitos", "Revise las propuestas y resuelva las contradicciones; después continúe el flujo.", "/state")
        if any(i["tipo"] == "pregunta_pendiente" for i in active):
            raise WorkflowPause("requisitos", "Hay decisiones de negocio sin resolver. Respóndalas con el analista y cierre las preguntas antes de continuar.", "/chat")
        if not any(i["tipo"] in ("requisito_funcional", "requisito_no_funcional") for i in active):
            raise WorkflowPause("requisitos", "Faltan requisitos consolidados para construir el producto.", "/state")
        if not any(i["tipo"] == "actor" for i in active):
            raise WorkflowPause("requisitos", "Faltan los actores de la aplicación (por ejemplo, empleado y jefe inmediato). Pide al analista que los proponga y apruébalos.", "/chat")
        latest = await self.db.one("SELECT version,payload FROM baselines WHERE project_id=%s ORDER BY version DESC LIMIT 1", (pid,))
        if latest:
            items = [v for group, values in latest["payload"].items() if isinstance(values, list)
                     for v in values if isinstance(v, dict) and "id" in v and "version" in v]
            if functional_fingerprint(items) == functional_fingerprint(active):
                return latest["version"]
        if workflow["modo"] == "supervisado":
            raise WorkflowPause("requisitos", "Publique la línea base revisada para continuar.", "/state")
        return (await self.app.state.projects.publish(pid, False))["version_linea_base"]

    async def phase(self, pid, rid, progress, name, source, **extra_source):
        from app.api.architecture import run_architecture
        from app.api.backlog import run_backlog
        from app.api.construction import run_construction
        from app.api.mockups import run_mockups

        table, decisions, version_key, source_key, link = PHASES[name]
        signature = {"origen": source, **extra_source}
        prior = progress.get(name)
        if not prior or prior.get("fuentes") != signature or prior.get("reintentar"):
            history = (prior or {}).get("intentos_anteriores", [])
            request_id = str(uuid5(UUID(rid), name + str(signature) + str(len(history))))
            instructions = "Implementa exclusivamente el alcance vigente, con trazabilidad completa, flujos alternativos, validaciones y permisos definidos. No inventes políticas ni integraciones funcionales."
            if name == "backlog":
                child_id, _ = await self.app.state.backlog.start(pid, "generar", {
                    "id_solicitud": request_id, "version_linea_base": source, "instrucciones": instructions})
            else:
                service = {"mockups": self.app.state.mockups, "arquitectura": self.app.state.architecture,
                           "construccion": self.app.state.construction}[name]
                body = {"id_solicitud": request_id, "instrucciones": instructions,
                        "version_arquitectura" if name == "construccion" else "version_backlog": source}
                if name == "construccion" and history:
                    body["reutilizar_candidato"] = True
                child_id, _ = await service.start(pid, body)
            progress[name] = {"fuentes": signature, "ejecucion": child_id, "intentos_anteriores": history}
            await self.save(rid, progress)
        step = progress[name]
        if not step.get("completado"):
            graph, runner = {
                "backlog": (self.app.state.backlog_team.graph, run_backlog),
                "mockups": (self.app.state.mockup_team.graph, run_mockups),
                "arquitectura": (self.app.state.architecture_team.graph, run_architecture),
                "construccion": (self.app.state.construction_team.graph, run_construction),
            }[name]
            await self.child(rid, name, step["ejecucion"], graph, runner)
            step["completado"] = True
            await self.save(rid, progress)
        # Manual edits create new immutable revisions. Adopt only a revision with the same source.
        row = await self.db.one(
            f"SELECT r.payload,d.status AS decision FROM {table} r LEFT JOIN {decisions} d USING(project_id,version) "
            "WHERE r.project_id=%s ORDER BY r.version DESC LIMIT 1", (pid,))
        if not row or row["payload"][source_key] != source:
            raise WorkflowPause(name, "La versión disponible tiene otro origen; genere y revise una versión con el origen vigente.", link)
        payload = row["payload"]
        if extra_source.get("mockups") and payload.get("version_mockups_origen") != extra_source["mockups"]:
            raise WorkflowPause(name, "El diseño de origen cambió. Actualice esta fase para continuar.", link)
        step["version"] = payload[version_key]
        step["decision"] = row["decision"]
        await self.save(rid, progress)
        if not payload["validacion"]["puede_publicar"]:
            raise WorkflowPause(name, "La validación detectó bloqueos. Corrija esta fase y continúe; los pasos anteriores se conservan.", link)
        if row["decision"] not in APPROVED:
            raise WorkflowPause(name, "Revise el resultado y apruébelo para continuar con la siguiente fase.", link)
        if name == "construccion" and not payload["validacion"].get("runtime_verificado"):
            raise WorkflowPause(name, "Falta verificar el producto en ejecución. No se marcará como terminado sin pruebas reales.", link)
        if name == "construccion" and row["decision"] == "validado_automaticamente" and payload["validacion"].get("observaciones"):
            raise WorkflowPause(name, "Las pruebas pasaron, pero hay observaciones de coherencia pendientes. Revise y corrija el producto; una aprobación automática no resuelve estas observaciones.", link)
        return payload[version_key]

    async def run(self, pid, rid):
        await self.events.status(rid, "ejecutando")
        workflow = await self.get(pid, rid)
        progress = workflow["pasos"]
        try:
            await self.analyze(pid, rid, workflow, progress)
            baseline = await self.baseline(pid, workflow)
            progress["requisitos"] = {"version": baseline, "completado": True}
            await self.save(rid, progress)
            backlog = await self.phase(pid, rid, progress, "backlog", baseline)
            mockups = await self.phase(pid, rid, progress, "mockups", backlog)
            architecture = await self.phase(pid, rid, progress, "arquitectura", backlog, mockups=mockups)
            construction = await self.phase(pid, rid, progress, "construccion", architecture, mockups=mockups)
            if workflow["solicitud"]["desplegar_local"]:
                service = self.app.state.construction
                child_id, created = await service.start_deploy(pid, construction, uuid5(UUID(rid), f"deploy-{construction}"))
                progress["despliegue"] = {"ejecucion": child_id, "version": construction}
                await self.save(rid, progress)
                if created:
                    await service.deploy(pid, construction, child_id)
                deployment = await service.get(pid, construction)
                if (deployment.get("entorno") or {}).get("estado") != "completado":
                    raise WorkflowPause("despliegue", "La instancia local no pasó todas las comprobaciones. Revise su ejecución antes de continuar.", "/construction")
            await self.events.emit(rid, "coordinador", "entrega", "completado", "Producto generado, aprobado y verificado", {"version_construccion": construction})
            await self.events.status(rid, "completado", {"version_construccion": construction, "enlace": "/construction"})
        except WorkflowPause as exc:
            output = {"fase": exc.phase, "mensaje": str(exc), "enlace": exc.link}
            await self.events.emit(rid, "coordinador", exc.phase, "esperando_revision", str(exc), output)
            await self.events.status(rid, "esperando_revision", output)
        except asyncio.CancelledError:
            await self.events.status(rid, "interrumpido", {"mensaje": "Flujo detenido; se conservaron sus versiones y pasos completados."})
            raise
        except Exception as exc:
            await self.events.emit(rid, "coordinador", "flujo", "error", "El flujo se detuvo. Puede continuar desde el último paso conservado.", {"tipo_error": type(exc).__name__})
            await self.events.status(rid, "error", {"mensaje": str(exc) if isinstance(exc, (ValueError, RuntimeError)) else "Fallo de ejecución; revise la actividad.", "enlace": "/activity"})
