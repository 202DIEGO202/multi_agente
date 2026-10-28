"""Persistencia transaccional de propuestas, revisiones y publicaciones de fase 2."""

from uuid import uuid4

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from app.models.backlog import BacklogContent, BacklogPublication
from app.models.schemas import Baseline
from app.services.backlog_logic import all_items, baseline_versions, compare_backlogs
from app.services.project_service import current_items


class BacklogService:
    def __init__(self, db, events):
        self.db, self.events = db, events

    async def _source_current(self, conn, project_id, baseline):
        current = {
            item["id"]: item["version"]
            for item in await current_items(conn, project_id)
            if item["vigencia"] == "vigente"
        }
        return current == baseline_versions(baseline)

    async def context(
        self, project_id, operation, baseline_version=None, version=None, instructions=""
    ):
        async with self.db.pool.connection() as conn, conn.transaction():
            await conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            project = await (
                await conn.execute(
                    "SELECT id,name,mode,counters,state_revision FROM projects WHERE id=%s",
                    (project_id,),
                )
            ).fetchone()
            if not project:
                raise LookupError("Proyecto no encontrado")
            rows = await (
                await conn.execute(
                    "SELECT payload FROM backlog_revisions WHERE project_id=%s ORDER BY version",
                    (project_id,),
                )
            ).fetchall()
            previous = rows[-1]["payload"] if rows else None
            head = previous["version_backlog"] if previous else 0
            previous_decision = (
                await (
                    await conn.execute(
                        "SELECT status AS estado,note AS nota FROM backlog_decisions WHERE project_id=%s AND version=%s",
                        (project_id, head),
                    )
                ).fetchone()
                if head
                else None
            )
            if operation != "generar":
                if version != head or not previous:
                    raise ValueError(
                        "La propuesta cambió; seleccione la última versión antes de continuar"
                    )
                baseline_version = previous["version_linea_base_origen"]
            source = await (
                await conn.execute(
                    "SELECT payload FROM baselines WHERE project_id=%s AND version=%s",
                    (project_id, baseline_version),
                )
            ).fetchone()
            if not source:
                raise ValueError("Publique una línea base funcional antes de generar el backlog")
            baseline = Baseline.model_validate(source["payload"]).model_dump(mode="json")
            if not await self._source_current(conn, project_id, baseline):
                raise ValueError(
                    "La línea base de origen está desactualizada. Revise los requisitos y publique una nueva línea base"
                )
            conflicts = await (
                await conn.execute(
                    "SELECT id FROM conflicts WHERE project_id=%s AND resolved_at IS NULL LIMIT 1",
                    (project_id,),
                )
            ).fetchone()
            if conflicts:
                raise ValueError(
                    "Resuelva las contradicciones críticas antes de continuar con la fase 2"
                )
        known = {}
        criterion_history = {}
        for row in rows:
            for item in all_items(row["payload"]):
                if "criterios_aceptacion" in item:
                    history = criterion_history.setdefault(item["id"], {})
                    for criterion in item["criterios_aceptacion"]:
                        history[criterion["id"]] = criterion
                if item["version"] >= known.get(item["id"], {}).get("version", 0):
                    known[item["id"]] = item
        project["id"] = str(project["id"])
        return {
            "project": project,
            "baseline": baseline,
            "previous": previous,
            "known": known,
            "criterion_history": {
                key: list(values.values()) for key, values in criterion_history.items()
            },
            "head": head,
            "instructions": instructions,
            "previous_decision": previous_decision,
        }

    async def start(self, project_id, operation, request, version=None):
        request = dict(request)
        request_id = request.pop("id_solicitud")
        data = {
            "project_id": str(project_id),
            "operation": operation,
            "request": request,
            "version": version,
        }
        existing = await self.db.one(
            "SELECT id,input FROM executions WHERE project_id=%s AND kind='backlog' AND request_id=%s",
            (project_id, request_id),
        )
        if existing:
            if existing["input"] != data:
                raise ValueError("El identificador de solicitud ya se utilizó con otro contenido")
            return str(existing["id"]), False
        context = await self.context(
            project_id,
            operation,
            request.get("version_linea_base"),
            version,
            request.get("instrucciones", ""),
        )
        # Sin actores no hay quién realice las historias; se avisa antes de gastar tokens.
        if not context["baseline"].get("actores"):
            raise ValueError(
                "La línea base no tiene actores (por ejemplo, empleado y jefe inmediato). "
                "Pide al analista que los proponga, apruébalos y publica una nueva línea base"
            )
        try:
            run_id = await self.events.create_run(
                project_id, "backlog", data, request_id=request_id
            )
        except UniqueViolation as exc:
            existing = await self.db.one(
                "SELECT id,input FROM executions WHERE project_id=%s AND kind='backlog' AND request_id=%s",
                (project_id, request_id),
            )
            if existing and existing["input"] == data:
                return str(existing["id"]), False
            raise ValueError("Ya hay una ejecución de backlog activa en este proyecto") from exc
        return run_id, True

    async def _check_live(self, conn, context):
        project_id = context["project"]["id"]
        project = await (
            await conn.execute("SELECT * FROM projects WHERE id=%s FOR UPDATE", (project_id,))
        ).fetchone()
        head = await (
            await conn.execute(
                "SELECT coalesce(max(version),0) AS version FROM backlog_revisions WHERE project_id=%s",
                (project_id,),
            )
        ).fetchone()
        if (
            head["version"] != context["head"]
            or project["state_revision"] != context["project"]["state_revision"]
        ):
            raise ValueError(
                "El proyecto cambió durante la ejecución. Genere una propuesta con el estado actualizado"
            )
        if not await self._source_current(conn, project_id, context["baseline"]):
            raise ValueError("La línea base ya no corresponde a los requisitos vigentes")
        conflicts = await (
            await conn.execute(
                "SELECT id FROM conflicts WHERE project_id=%s AND resolved_at IS NULL LIMIT 1",
                (project_id,),
            )
        ).fetchone()
        if conflicts:
            raise ValueError("Hay contradicciones críticas pendientes")
        return project

    async def _record_decision(self, conn, content, status, note):
        project_id, version = content["id_proyecto"], content["version_backlog"]
        await conn.execute(
            "INSERT INTO backlog_decisions(id,project_id,version,status,note) VALUES(%s,%s,%s,%s,%s)",
            (str(uuid4()), project_id, version, status, note),
        )
        publication = None
        if status in {"aprobado_por_humano", "validado_automaticamente"}:
            publication = BacklogPublication.model_validate(
                {**content, "estado": status}
            ).model_dump(mode="json")
            await conn.execute(
                "INSERT INTO backlog_publications(project_id,version,payload) VALUES(%s,%s,%s)",
                (project_id, version, Jsonb(publication)),
            )
        await conn.execute(
            "INSERT INTO events(execution_id,component,operation,status,description,data) "
            "VALUES(%s,'revision_backlog','publicar',%s,%s,%s)",
            (
                content["id_ejecucion"],
                status,
                "Decisión de backlog registrada",
                Jsonb(
                    {"version_backlog": version, "nota": note, "contrato_publicado": publication}
                ),
            ),
        )

    async def persist(self, context, content, counters):
        content = BacklogContent.model_validate(content).model_dump(mode="json")
        existing = await self.db.one(
            "SELECT payload FROM backlog_revisions WHERE execution_id=%s",
            (content["id_ejecucion"],),
        )
        if existing:
            return existing["payload"]
        async with self.db.pool.connection() as conn, conn.transaction():
            project = await self._check_live(conn, context)
            merged = dict(project["counters"])
            for prefix in ("EP", "FE", "HU"):
                if merged.get(prefix, 0) != context["project"]["counters"].get(prefix, 0):
                    raise ValueError(
                        "Los identificadores del backlog cambiaron durante la ejecución"
                    )
                if prefix in counters:
                    merged[prefix] = counters[prefix]
            await conn.execute(
                "UPDATE projects SET counters=%s WHERE id=%s", (Jsonb(merged), project["id"])
            )
            await conn.execute(
                "INSERT INTO backlog_revisions(project_id,version,baseline_version,execution_id,parent_version,payload) "
                "VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    project["id"],
                    content["version_backlog"],
                    content["version_linea_base_origen"],
                    content["id_ejecucion"],
                    context["head"] or None,
                    Jsonb(content),
                ),
            )
            await conn.execute(
                "INSERT INTO events(execution_id,component,operation,status,description,data) "
                "VALUES(%s,'persistencia_backlog','guardar_version','completado','Nueva versión de backlog guardada',%s)",
                (
                    content["id_ejecucion"],
                    Jsonb(
                        {
                            "contrato": content,
                            "cambios": compare_backlogs(context["previous"], content),
                        }
                    ),
                ),
            )
            if project["mode"] == "automatico" and content["validacion"]["puede_publicar"]:
                await self._record_decision(
                    conn,
                    content,
                    "validado_automaticamente",
                    "Validación automática conforme a las reglas configuradas",
                )
        return content

    async def list(self, project_id):
        return await self.db.fetch(
            "SELECT b.version,b.baseline_version AS version_linea_base,b.created_at AS fecha,"
            "b.execution_id AS id_ejecucion,b.payload->>'operacion' AS operacion,"
            "coalesce(d.status,CASE WHEN (b.payload->'validacion'->>'puede_publicar')::boolean "
            "THEN 'propuesto' ELSE 'pendiente_aclaracion' END) AS estado "
            "FROM backlog_revisions b LEFT JOIN backlog_decisions d ON d.project_id=b.project_id "
            "AND d.version=b.version WHERE b.project_id=%s ORDER BY b.version DESC",
            (project_id,),
        )

    async def get(self, project_id, version):
        row = await self.db.one(
            "SELECT payload FROM backlog_revisions WHERE project_id=%s AND version=%s",
            (project_id, version),
        )
        if not row:
            raise LookupError("Versión de backlog no encontrada")
        content = row["payload"]
        source = await self.db.one(
            "SELECT payload FROM baselines WHERE project_id=%s AND version=%s",
            (project_id, content["version_linea_base_origen"]),
        )
        async with self.db.pool.connection() as conn:
            current = {
                item["id"]: item["version"]
                for item in await current_items(conn, project_id)
                if item["vigencia"] == "vigente"
            }
        original = baseline_versions(source["payload"])
        changed = sorted(
            key for key in original.keys() | current.keys() if original.get(key) != current.get(key)
        )
        affected = [
            item["id"]
            for item in all_items(content)
            if any(ref["id"] in changed for ref in item["requisitos_origen"])
            or item.get("actor", {}).get("id") in changed
        ]
        decision = await self.db.one(
            "SELECT status AS estado,note AS nota,created_at AS fecha FROM backlog_decisions "
            "WHERE project_id=%s AND version=%s",
            (project_id, version),
        )
        publication = await self.db.one(
            "SELECT payload FROM backlog_publications WHERE project_id=%s AND version=%s",
            (project_id, version),
        )
        state = (
            decision["estado"]
            if decision
            else (
                "propuesto" if content["validacion"]["puede_publicar"] else "pendiente_aclaracion"
            )
        )
        return {
            "contrato": content,
            "estado": state,
            "decision": decision,
            "publicado": bool(publication),
            "desactualizado": bool(changed),
            "origenes_modificados": changed,
            "elementos_afectados": affected,
            "cambios": compare_backlogs((await self._previous(project_id, version)), content),
        }

    async def _previous(self, project_id, version):
        row = await self.db.one(
            "SELECT payload FROM backlog_revisions WHERE project_id=%s AND version<%s "
            "ORDER BY version DESC LIMIT 1",
            (project_id, version),
        )
        return row["payload"] if row else None

    async def review(self, project_id, version, review):
        async with self.db.pool.connection() as conn, conn.transaction():
            await conn.execute("SELECT id FROM projects WHERE id=%s FOR UPDATE", (project_id,))
            row = await (
                await conn.execute(
                    "SELECT payload FROM backlog_revisions WHERE project_id=%s AND version=%s",
                    (project_id, version),
                )
            ).fetchone()
            if not row:
                raise LookupError("Propuesta no encontrada")
            decision = await (
                await conn.execute(
                    "SELECT id FROM backlog_decisions WHERE project_id=%s AND version=%s",
                    (project_id, version),
                )
            ).fetchone()
            if decision:
                raise ValueError(
                    "Esta versión ya tiene una decisión; genere una nueva revisión para cambiarla"
                )
            if review.accion == "aprobar":
                content = row["payload"]
                source = await (
                    await conn.execute(
                        "SELECT payload FROM baselines WHERE project_id=%s AND version=%s",
                        (project_id, content["version_linea_base_origen"]),
                    )
                ).fetchone()
                head = await (
                    await conn.execute(
                        "SELECT max(version) AS version FROM backlog_revisions WHERE project_id=%s",
                        (project_id,),
                    )
                ).fetchone()
                if version != head["version"] or not await self._source_current(
                    conn, project_id, source["payload"]
                ):
                    raise ValueError(
                        "La propuesta está desactualizada; regenere usando la línea base vigente"
                    )
                if not content["validacion"]["puede_publicar"]:
                    raise ValueError(
                        "La propuesta tiene errores o preguntas pendientes; corríjala y vuelva a validar"
                    )
                conflicts = await (
                    await conn.execute(
                        "SELECT id FROM conflicts WHERE project_id=%s AND resolved_at IS NULL LIMIT 1",
                        (project_id,),
                    )
                ).fetchone()
                if conflicts:
                    raise ValueError("Resuelva las contradicciones críticas antes de aprobar")
            await self._record_decision(
                conn,
                row["payload"],
                "aprobado_por_humano" if review.accion == "aprobar" else "descartado",
                review.nota,
            )
        return await self.get(project_id, version)

    async def publication(self, project_id, version):
        row = await self.db.one(
            "SELECT payload FROM backlog_publications WHERE project_id=%s AND version=%s",
            (project_id, version),
        )
        if not row:
            raise LookupError("No existe una publicación aprobada de esta versión")
        return row["payload"]

    async def history(self, project_id, item_id):
        rows = await self.db.fetch(
            "SELECT payload FROM backlog_revisions WHERE project_id=%s ORDER BY version",
            (project_id,),
        )
        result, seen = [], set()
        for row in rows:
            content = row["payload"]
            for item in all_items(content):
                if item["id"] == item_id and item["version"] not in seen:
                    seen.add(item["version"])
                    result.append(
                        {
                            "elemento": item,
                            "version_backlog": content["version_backlog"],
                            "version_linea_base": content["version_linea_base_origen"],
                            "id_ejecucion": content["id_ejecucion"],
                            "fecha": content["fecha"],
                            "nota": content["nota"],
                        }
                    )
        if not result:
            raise LookupError("Elemento de backlog no encontrado en este proyecto")
        return result
