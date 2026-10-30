import re
from datetime import UTC, datetime
from uuid import uuid4

from psycopg.types.json import Jsonb
from pydantic import ValidationError as PydanticValidationError

from app.models.schemas import (
    PREFIX,
    Baseline,
    Change,
    CreateChange,
    FunctionalItem,
    ItemType,
    normalized,
)


async def current_items(conn, project_id):
    rows = await (
        await conn.execute(
            "SELECT DISTINCT ON(id) payload FROM functional_items WHERE project_id=%s "
            "ORDER BY id,version DESC",
            (project_id,),
        )
    ).fetchall()
    return [row["payload"] for row in rows]


def separate_document_sources(change: Change) -> Change:
    """Las citas con página son fuentes, nunca relaciones con elementos funcionales."""
    sources = list(change.fuentes_documentales)
    relations = []
    for reference in change.referencias:
        if re.fullmatch(r".+,\s*p(?:ag(?:ina)?)?\.?\s*\d+", reference, re.IGNORECASE):
            if reference not in sources:
                sources.append(reference)
        else:
            relations.append(reference)
    return change.model_copy(update={"referencias": relations, "fuentes_documentales": sources})


def preserve_target_type(change, items):
    """Modificar conserva la identidad/tipo del elemento; no reclasifica el modelo."""
    target = next((item for item in items if item["id"] == change.id_elemento), None)
    if change.operacion != "crear" and target and change.tipo != target["tipo"]:
        return change.model_copy(update={"tipo": ItemType(target["tipo"])})
    return change


def validate_change(change: Change, items: list[dict]):
    errors = []
    by_id = {item["id"]: item for item in items}
    if change.operacion != "crear":
        existing = by_id.get(change.id_elemento)
        if not existing:
            errors.append("El elemento indicado no existe")
        elif existing["version"] != change.version_esperada:
            errors.append("La versión cambió; revise el estado vigente antes de aprobar")
        elif existing["tipo"] != change.tipo:
            errors.append("No se puede cambiar el tipo de un elemento existente")
    for item in items:
        if (
            item["id"] != change.id_elemento
            and item["tipo"] == change.tipo
            and item["vigencia"] == "vigente"
            and normalized(item["descripcion"]) == normalized(change.descripcion)
        ):
            errors.append(f"Descripción duplicada: {item['id']}")
    if set(change.referencias) - by_id.keys():
        errors.append(
            "Relaciones con elementos inexistentes: "
            + ", ".join(sorted(set(change.referencias) - by_id.keys()))
        )
    if change.id_elemento in change.referencias:
        errors.append("Un elemento no puede referenciarse a sí mismo")
    return errors


TECHNICAL_CITATION_PENDING = "La comprobación técnica de una cita sigue pendiente. Esto no es una contradicción que debas resolver manualmente."


def clarified_request(original, conflicts, resolution):
    """Mensaje para que el analista rehaga las propuestas con la aclaración humana."""
    doubts = "\n".join(f"- {text}" for text in conflicts)
    return (
        "Aclaración registrada por el usuario sobre estas dudas:\n" + doubts
        + "\nRespuesta del usuario: " + resolution
        + "\n\nVuelve a proponer los requisitos completos de la solicitud original aplicando esta "
        "aclaración junto con la documentación vigente. Solicitud original:\n" + original
    )


async def check_procedure_sources(conn, project_id, run_id):
    row = await (
        await conn.execute(
            "SELECT data FROM events WHERE execution_id=%s AND operation='compatibilidad_procedimientos' ORDER BY id DESC LIMIT 1",
            (run_id,),
        )
    ).fetchone()
    if not row:
        return []  # Los registros anteriores mantienen su historial original.
    report = row["data"]
    if report.get("estado") == "requiere_revision":
        return [TECHNICAL_CITATION_PENDING]
    if report.get("estado") in {"requiere_aclaracion", "contradice"}:
        return [
            "Esta propuesta se redactó antes de aclarar la compatibilidad con los procedimientos. "
            "Recházala y pide al analista que la proponga de nuevo teniendo en cuenta tu aclaración"
        ]
    for source in report.get("fuentes_verificadas", []):
        current = await (
            await conn.execute(
                "SELECT version FROM project_knowledge_documents WHERE consumer_project_id=%s AND id=%s AND status='indexado'",
                (project_id, source["id_documento"]),
            )
        ).fetchone()
        if not current or current["version"] != source["version_documento"]:
            return [
                "Cambió un procedimiento de origen. Solicita al analista revisar la propuesta con la documentación vigente antes de aprobarla"
            ]
    return []


class ProjectService:
    def __init__(self, db, events):
        self.db, self.events = db, events

    async def create(self, data):
        project_id = str(uuid4())
        await self.db.execute(
            "INSERT INTO projects(id,name,description,mode) VALUES(%s,%s,%s,'supervisado')",
            (project_id, data.nombre, data.descripcion),
        )
        return await self.get(project_id)

    async def get(self, project_id):
        project = await self.db.one(
            "SELECT id AS id_proyecto,name AS nombre,description AS descripcion,mode AS modo,"
            "state_revision AS version_estado,created_at AS fecha_creacion FROM projects WHERE id=%s AND deleted_at IS NULL",
            (project_id,),
        )
        if not project:
            raise LookupError("Proyecto no encontrado")
        return project

    async def list(self):
        return await self.db.fetch(
            "SELECT p.id AS id_proyecto,p.name AS nombre,p.description AS descripcion,p.mode AS modo,"
            "p.state_revision AS version_estado,p.created_at AS fecha_creacion,"
            "(SELECT count(DISTINCT f.id) FROM functional_items f WHERE f.project_id=p.id) AS elementos,"
            "(SELECT count(*) FROM project_knowledge_documents d WHERE d.consumer_project_id=p.id) AS documentos "
            "FROM projects p WHERE p.deleted_at IS NULL ORDER BY p.created_at DESC"
        )

    async def trash(self):
        return await self.db.fetch(
            "SELECT id AS id_proyecto,name AS nombre,description AS descripcion,mode AS modo,"
            "state_revision AS version_estado,created_at AS fecha_creacion,deleted_at AS fecha_eliminacion "
            "FROM projects WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC"
        )

    async def set_deleted(self, project_id, deleted):
        async with self.db.pool.connection() as conn, conn.transaction():
            project = await (
                await conn.execute(
                    "SELECT id,deleted_at FROM projects WHERE id=%s FOR UPDATE", (project_id,)
                )
            ).fetchone()
            if not project:
                raise LookupError("Proyecto no encontrado")
            if (project["deleted_at"] is not None) == deleted:
                return {"estado": "eliminado" if deleted else "restaurado"}
            if deleted:
                active = await (
                    await conn.execute(
                        "SELECT id FROM executions WHERE project_id=%s AND status IN ('pendiente','ejecutando') LIMIT 1",
                        (project_id,),
                    )
                ).fetchone()
                if active:
                    raise ValueError(
                        "Hay una tarea en curso. Espera a que termine antes de eliminar el proyecto"
                    )
            await conn.execute(
                "UPDATE projects SET deleted_at=CASE WHEN %s THEN now() ELSE NULL END WHERE id=%s",
                (deleted, project_id),
            )
            await conn.execute(
                "INSERT INTO project_lifecycle_events(project_id,operation) VALUES(%s,%s)",
                (project_id, "eliminar" if deleted else "restaurar"),
            )
        return {"estado": "eliminado" if deleted else "restaurado"}

    async def state(self, project_id):
        project = await self.get(project_id)
        async with self.db.pool.connection() as conn, conn.transaction():
            await conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            items = await current_items(conn, project_id)
            proposals = await (
                await conn.execute(
                    "SELECT id,change AS cambio,status AS estado,validation AS validacion,"
                    "resulting_id AS id_elemento,execution_id AS id_ejecucion,created_at AS fecha "
                    "FROM proposals WHERE project_id=%s ORDER BY created_at DESC",
                    (project_id,),
                )
            ).fetchall()
            conflicts = await (
                await conn.execute(
                    "SELECT id,description AS descripcion,resolution AS resolucion,"
                    "resolved_at AS fecha_resolucion FROM conflicts WHERE project_id=%s ORDER BY created_at",
                    (project_id,),
                )
            ).fetchall()
            baselines = await (
                await conn.execute(
                    "SELECT version,created_at AS fecha FROM baselines WHERE project_id=%s ORDER BY version DESC",
                    (project_id,),
                )
            ).fetchall()
            knowledge = await (
                await conn.execute(
                    "SELECT count(DISTINCT d.id) FILTER (WHERE d.status='indexado') AS documentos_indexados,"
                    "count(c.id) FILTER (WHERE d.status='indexado') AS fragmentos FROM project_knowledge_documents d "
                    "LEFT JOIN chunks c ON c.document_id=d.id WHERE d.consumer_project_id=%s",
                    (project_id,),
                )
            ).fetchone()
        return {
            "proyecto": project,
            "elementos": items,
            "propuestas": proposals,
            "contradicciones": conflicts,
            "lineas_base": baselines,
            "conocimiento": knowledge,
        }

    async def _apply(self, conn, project, change, run_id, message_id, approval):
        project_id = project["id"]
        items = await current_items(conn, project_id)
        errors = validate_change(change, items)
        if errors:
            raise ValueError("; ".join(errors))
        if change.operacion == "crear":
            counters = dict(project["counters"])
            prefix = PREFIX[change.tipo]
            counters[prefix] = counters.get(prefix, 0) + 1
            item_id = f"{prefix}-{counters[prefix]:03d}"
            project["counters"] = counters
            await conn.execute(
                "UPDATE projects SET counters=%s WHERE id=%s", (Jsonb(counters), project_id)
            )
            version = 1
        else:
            item_id, version = change.id_elemento, change.version_esperada + 1
        affected = sorted(
            {
                item["id"]
                for item in items
                if item["id"] != item_id
                and item["vigencia"] == "vigente"
                and (item_id in item["referencias"] or item["id"] in change.referencias)
            }
        )
        payload = FunctionalItem(
            id=item_id,
            tipo=change.tipo,
            descripcion=change.descripcion,
            version=version,
            estado=approval,
            vigencia="descartado" if change.operacion == "descartar" else "vigente",
            id_mensaje=str(message_id),
            id_ejecucion=str(run_id),
            referencias=change.referencias,
            fuentes_documentales=change.fuentes_documentales,
            fecha_modificacion=datetime.now(UTC),
            elementos_afectados=affected,
        ).model_dump(mode="json")
        await conn.execute(
            "INSERT INTO functional_items(project_id,id,version,payload) VALUES(%s,%s,%s,%s)",
            (project_id, item_id, version, Jsonb(payload)),
        )
        await conn.execute(
            "UPDATE projects SET state_revision=state_revision+1 WHERE id=%s", (project_id,)
        )
        return item_id

    async def propose(self, project_id, run_id, message_id, analysis):
        result = []
        changes = list(analysis.cambios)
        for question in analysis.preguntas:
            if not any(
                change.tipo == ItemType.QUESTION
                and normalized(change.descripcion) == normalized(question)
                for change in changes
            ):
                changes.append(
                    CreateChange(operacion="crear", tipo=ItemType.QUESTION, descripcion=question)
                )
        async with self.db.pool.connection() as conn, conn.transaction():
            project = await (
                await conn.execute("SELECT * FROM projects WHERE id=%s FOR UPDATE", (project_id,))
            ).fetchone()
            for description in analysis.contradicciones_criticas:
                await conn.execute(
                    "INSERT INTO conflicts(id,project_id,execution_id,description) VALUES(%s,%s,%s,%s) "
                    "ON CONFLICT(execution_id,description) DO NOTHING",
                    (str(uuid4()), project_id, run_id, description),
                )
            unresolved = await (
                await conn.execute(
                    "SELECT id FROM conflicts WHERE project_id=%s AND resolved_at IS NULL",
                    (project_id,),
                )
            ).fetchall()
            for change in changes:
                change = separate_document_sources(change)
                items = await current_items(conn, project_id)
                corrected = preserve_target_type(change, items)
                if corrected.tipo != change.tipo:
                    await conn.execute(
                        "INSERT INTO events(execution_id,component,operation,status,description,data) VALUES(%s,'validacion','conservar_tipo','completado','Tipo original del elemento conservado',%s)",
                        (
                            run_id,
                            Jsonb(
                                {
                                    "antes": change.model_dump(mode="json"),
                                    "despues": corrected.model_dump(mode="json"),
                                    "sin_inferencia": True,
                                }
                            ),
                        ),
                    )
                change = corrected
                value = change.model_dump(mode="json")
                existing = await (
                    await conn.execute(
                        "SELECT id,status,resulting_id FROM proposals WHERE execution_id=%s AND change=%s",
                        (run_id, Jsonb(value)),
                    )
                ).fetchone()
                if existing:
                    result.append(
                        {
                            "id": str(existing["id"]),
                            "estado": existing["status"],
                            "id_elemento": existing["resulting_id"],
                        }
                    )
                    continue
                items = await current_items(conn, project_id)
                errors = validate_change(change, items)
                errors.extend(await check_procedure_sources(conn, project_id, run_id))
                # Repetir la misma propuesta en mensajes posteriores tampoco crea un duplicado.
                pending = await (
                    await conn.execute(
                        "SELECT id FROM proposals WHERE project_id=%s AND change=%s "
                        "AND status IN ('propuesto','pendiente_aclaracion') LIMIT 1",
                        (project_id, Jsonb(value)),
                    )
                ).fetchone()
                if pending:
                    result.append({"id": str(pending["id"]), "estado": "propuesto_existente"})
                    continue
                if unresolved:
                    errors.append("Hay contradicciones críticas pendientes de resolución")
                proposal_id, item_id = str(uuid4()), None
                status = "pendiente_aclaracion" if errors else "propuesto"
                await conn.execute(
                    "INSERT INTO proposals(id,project_id,execution_id,message_id,change,status,validation,"
                    "resulting_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        proposal_id,
                        project_id,
                        run_id,
                        message_id,
                        Jsonb(value),
                        status,
                        Jsonb(errors),
                        item_id,
                    ),
                )
                result.append(
                    {
                        "id": proposal_id,
                        "estado": status,
                        "id_elemento": item_id,
                        "validacion": errors,
                        "cambio": value,
                    }
                )
        return result

    async def repair_document_references(self, project_id):
        repaired = 0
        async with self.db.pool.connection() as conn, conn.transaction():
            await conn.execute("SELECT id FROM projects WHERE id=%s FOR UPDATE", (project_id,))
            rows = await (
                await conn.execute(
                    "SELECT * FROM proposals WHERE project_id=%s "
                    "AND status IN ('propuesto','pendiente_aclaracion') FOR UPDATE",
                    (project_id,),
                )
            ).fetchall()
            items = await current_items(conn, project_id)
            conflicts = await (
                await conn.execute(
                    "SELECT id FROM conflicts WHERE project_id=%s AND resolved_at IS NULL",
                    (project_id,),
                )
            ).fetchall()
            for row in rows:
                original = Change.model_validate(row["change"])
                change = separate_document_sources(original)
                if change.referencias == original.referencias:
                    continue
                errors = validate_change(change, items)
                if conflicts:
                    errors.append("Hay contradicciones críticas pendientes de resolución")
                value = change.model_dump(mode="json")
                # El contrato original y el resultado corregido quedan en la auditoría.
                await conn.execute(
                    "INSERT INTO events(execution_id,component,operation,status,description,data) "
                    "VALUES(%s,'validacion','reparar_fuentes','completado',%s,%s)",
                    (
                        row["execution_id"],
                        "Separación de fuentes documentales y relaciones funcionales",
                        Jsonb(
                            {
                                "id_propuesta": str(row["id"]),
                                "antes": row["change"],
                                "despues": value,
                            }
                        ),
                    ),
                )
                await conn.execute(
                    "UPDATE proposals SET change=%s,validation=%s,status=%s WHERE id=%s",
                    (
                        Jsonb(value),
                        Jsonb(errors),
                        "pendiente_aclaracion" if errors else "propuesto",
                        row["id"],
                    ),
                )
                repaired += 1
        return repaired

    async def repair_pending_types(self, project_id):
        repaired = 0
        async with self.db.pool.connection() as conn, conn.transaction():
            await conn.execute("SELECT id FROM projects WHERE id=%s FOR UPDATE", (project_id,))
            items = await current_items(conn, project_id)
            rows = await (
                await conn.execute(
                    "SELECT * FROM proposals WHERE project_id=%s AND status IN ('propuesto','pendiente_aclaracion') FOR UPDATE",
                    (project_id,),
                )
            ).fetchall()
            conflicts = await (
                await conn.execute(
                    "SELECT id FROM conflicts WHERE project_id=%s AND resolved_at IS NULL",
                    (project_id,),
                )
            ).fetchall()
            for row in rows:
                original = Change.model_validate(row["change"])
                change = preserve_target_type(original, items)
                if original.tipo == change.tipo:
                    continue
                errors = validate_change(change, items)
                errors.extend(await check_procedure_sources(conn, project_id, row["execution_id"]))
                if conflicts:
                    errors.append("Hay contradicciones críticas pendientes de resolución")
                value = change.model_dump(mode="json")
                await conn.execute(
                    "INSERT INTO events(execution_id,component,operation,status,description,data) VALUES(%s,'validacion','reparar_tipo_propuesta','completado','Clasificación técnica corregida; aprobación humana pendiente',%s)",
                    (
                        row["execution_id"],
                        Jsonb(
                            {
                                "id_propuesta": str(row["id"]),
                                "antes": row["change"],
                                "despues": value,
                                "sin_inferencia": True,
                            }
                        ),
                    ),
                )
                await conn.execute(
                    "UPDATE proposals SET change=%s,validation=%s,status=%s WHERE id=%s",
                    (
                        Jsonb(value),
                        Jsonb(errors),
                        "pendiente_aclaracion" if errors else "propuesto",
                        row["id"],
                    ),
                )
                repaired += 1
        return repaired

    async def review(self, project_id, proposal_id, review):
        async with self.db.pool.connection() as conn, conn.transaction():
            project = await (
                await conn.execute("SELECT * FROM projects WHERE id=%s FOR UPDATE", (project_id,))
            ).fetchone()
            proposal = await (
                await conn.execute(
                    "SELECT * FROM proposals WHERE project_id=%s AND id=%s FOR UPDATE",
                    (project_id, proposal_id),
                )
            ).fetchone()
            if not proposal:
                raise LookupError("Propuesta no encontrada")
            if proposal["status"] not in {"propuesto", "pendiente_aclaracion"}:
                raise ValueError("La propuesta ya fue revisada")
            item_id = None
            status = "descartado"
            analyst_decision = False
            if review.accion == "aprobar":
                conflict = await (
                    await conn.execute(
                        "SELECT id FROM conflicts WHERE project_id=%s AND resolved_at IS NULL LIMIT 1",
                        (project_id,),
                    )
                ).fetchone()
                if conflict:
                    raise ValueError("Resuelva las contradicciones críticas antes de consolidar")
                procedure_errors = await check_procedure_sources(
                    conn, project_id, proposal["execution_id"]
                )
                # El analista puede asumir como decisión propia una cita no verificada;
                # nunca una contradicción documental ni un procedimiento desactualizado.
                analyst_decision = review.confirmar_decision_analista and procedure_errors == [
                    TECHNICAL_CITATION_PENDING
                ]
                if analyst_decision:
                    procedure_errors = []
                if procedure_errors:
                    raise ValueError("; ".join(procedure_errors))
                value = dict(proposal["change"])
                if review.descripcion:
                    value["descripcion"] = review.descripcion
                change = Change.model_validate(value)
                item_id = await self._apply(
                    conn,
                    project,
                    change,
                    proposal["execution_id"],
                    proposal["message_id"],
                    "aprobado_por_humano",
                )
                status = "aprobado_por_humano"
            await conn.execute(
                "UPDATE proposals SET status=%s,resulting_id=%s,reviewed_at=now() WHERE id=%s",
                (status, item_id, proposal_id),
            )
            await conn.execute(
                "INSERT INTO events(execution_id,component,operation,status,description,data) "
                "VALUES(%s,'validacion','revision_humana',%s,'Revisión humana registrada',%s)",
                (
                    proposal["execution_id"],
                    status,
                    Jsonb(
                        {
                            "id_propuesta": str(proposal_id),
                            "id_elemento": item_id,
                            "descripcion_revisada": review.descripcion,
                            "decision_analista_sin_cita": analyst_decision,
                        }
                    ),
                ),
            )
        return {"estado": status, "id_elemento": item_id}

    async def resolve_conflict(self, project_id, conflict_id, resolution):
        async with self.db.pool.connection() as conn, conn.transaction():
            await conn.execute("SELECT id FROM projects WHERE id=%s FOR UPDATE", (project_id,))
            target = await (
                await conn.execute(
                    "SELECT execution_id FROM conflicts WHERE project_id=%s AND id=%s AND resolved_at IS NULL",
                    (project_id, conflict_id),
                )
            ).fetchone()
            if not target:
                raise LookupError("Contradicción pendiente no encontrada")
            run_id = target["execution_id"]
            # Un análisis puede expresar la misma duda con varias redacciones: una aclaración las cierra todas.
            resolved = await (
                await conn.execute(
                    "UPDATE conflicts SET resolution=%s,resolved_at=now() "
                    "WHERE project_id=%s AND execution_id=%s AND resolved_at IS NULL RETURNING description",
                    (resolution, project_id, run_id),
                )
            ).fetchall()
            # Las propuestas bloqueadas se redactaron sin la aclaración: se reemplazan con un nuevo análisis.
            superseded = await (
                await conn.execute(
                    "UPDATE proposals SET status='reemplazado',reviewed_at=now() "
                    "WHERE project_id=%s AND execution_id=%s AND status='pendiente_aclaracion' RETURNING id",
                    (project_id, run_id),
                )
            ).fetchall()
            source = await (
                await conn.execute(
                    "SELECT e.conversation_id,m.content FROM executions e "
                    "LEFT JOIN messages m ON m.execution_id=e.id AND m.role='user' WHERE e.id=%s",
                    (run_id,),
                )
            ).fetchone()
            descriptions = [row["description"] for row in resolved]
            await conn.execute(
                "INSERT INTO events(execution_id,component,operation,status,description,data) "
                "VALUES(%s,'validacion','resolver_contradiccion','aprobado_por_humano',%s,%s)",
                (
                    run_id,
                    "Aclaración humana registrada",
                    Jsonb(
                        {
                            "resolucion": resolution,
                            "contradicciones": descriptions,
                            "propuestas_reemplazadas": [str(row["id"]) for row in superseded],
                        }
                    ),
                ),
            )
        reanalysis = None
        if superseded and source and source["conversation_id"] and source["content"]:
            reanalysis = {
                "id_conversacion": str(source["conversation_id"]),
                "mensaje": clarified_request(source["content"], descriptions, resolution),
            }
        return {
            "estado": "resuelto",
            "contradicciones_resueltas": len(descriptions),
            "propuestas_reemplazadas": len(superseded),
            "reanalisis": reanalysis,
        }

    async def answer_question(self, project_id, item_id, answer):
        async with self.db.pool.connection() as conn, conn.transaction():
            project = await (
                await conn.execute("SELECT id FROM projects WHERE id=%s AND deleted_at IS NULL FOR UPDATE", (project_id,))
            ).fetchone()
            if not project:
                raise LookupError("Proyecto no encontrado")
            row = await (
                await conn.execute(
                    "SELECT payload FROM functional_items WHERE project_id=%s AND id=%s ORDER BY version DESC LIMIT 1",
                    (project_id, item_id),
                )
            ).fetchone()
            if not row:
                raise LookupError("Pregunta no encontrada")
            item = row["payload"]
            if item["tipo"] != "pregunta_pendiente":
                raise ValueError("Este elemento no es una pregunta pendiente")
            if item["vigencia"] != "vigente":
                raise ValueError("Esta pregunta ya fue resuelta")
            execution = await (
                await conn.execute("SELECT conversation_id FROM executions WHERE id=%s", (item["id_ejecucion"],))
            ).fetchone()
            conversation_id = execution["conversation_id"] if execution else None
            if not conversation_id:
                latest = await (
                    await conn.execute(
                        "SELECT id FROM conversations WHERE project_id=%s ORDER BY created_at DESC LIMIT 1", (project_id,)
                    )
                ).fetchone()
                conversation_id = latest["id"] if latest else None
            if not conversation_id:
                raise ValueError("No hay una conversación activa para responder esta pregunta")
        message = (
            f"Respondo la pregunta pendiente {item_id} («{item['descripcion']}»): {answer}. "
            "Actualiza los requisitos, actores, reglas, restricciones o decisiones según corresponda "
            "y retira esta pregunta si con esta respuesta ya queda resuelta."
        )
        return {"id_conversacion": str(conversation_id), "mensaje": message}

    async def publish(self, project_id, human_approval):
        async with self.db.pool.connection() as conn, conn.transaction():
            project = await (
                await conn.execute("SELECT * FROM projects WHERE id=%s FOR UPDATE", (project_id,))
            ).fetchone()
            if not project:
                raise LookupError("Proyecto no encontrado")
            blocking = await (
                await conn.execute(
                    "SELECT (SELECT count(*) FROM conflicts WHERE project_id=%s AND resolved_at IS NULL) + "
                    "(SELECT count(*) FROM proposals WHERE project_id=%s "
                    "AND status IN ('propuesto','pendiente_aclaracion')) AS total",
                    (project_id, project_id),
                )
            ).fetchone()
            if blocking["total"]:
                raise ValueError(
                    "Revise las propuestas y resuelva las contradicciones antes de publicar"
                )
            if not human_approval:
                raise ValueError(
                    "Se requiere aprobación humana explícita para publicar"
                )
            latest = await (
                await conn.execute(
                    "SELECT coalesce(max(version),0)+1 AS version FROM baselines WHERE project_id=%s",
                    (project_id,),
                )
            ).fetchone()
            groups = {
                "requisitos": [],
                "objetivos": [],
                "actores": [],
                "decisiones": [],
                "reglas_negocio": [],
                "restricciones": [],
                "preguntas_pendientes": [],
                "supuestos": [],
            }
            mapping = {
                ItemType.FUNCTIONAL: "requisitos",
                ItemType.NON_FUNCTIONAL: "requisitos",
                ItemType.OBJECTIVE: "objetivos",
                ItemType.ACTOR: "actores",
                ItemType.DECISION: "decisiones",
                ItemType.RULE: "reglas_negocio",
                ItemType.CONSTRAINT: "restricciones",
                ItemType.QUESTION: "preguntas_pendientes",
                ItemType.ASSUMPTION: "supuestos",
            }
            for item in await current_items(conn, project_id):
                if item["vigencia"] == "vigente":
                    groups[mapping[item["tipo"]]].append(item)
            if not groups["requisitos"]:
                raise ValueError(
                    "Aún no hay requisitos funcionales o no funcionales consolidados. "
                    "Continúa la conversación con el analista para definirlos y apruébalos "
                    "antes de publicar la línea base."
                )
            try:
                baseline = Baseline(
                    id_proyecto=str(project_id),
                    nombre_proyecto=project["name"],
                    version_linea_base=latest["version"],
                    estado="aprobado_por_humano" if human_approval else "validado_automaticamente",
                    **groups,
                )
            except PydanticValidationError as exc:
                raise ValueError(
                    "No fue posible generar la línea base porque los elementos consolidados "
                    "son inconsistentes entre sí. Revisa los requisitos, actores y demás "
                    "elementos vigentes del proyecto e inténtalo de nuevo."
                ) from exc
            payload = baseline.model_dump(mode="json")
            await conn.execute(
                "INSERT INTO baselines(project_id,version,payload) VALUES(%s,%s,%s)",
                (project_id, latest["version"], Jsonb(payload)),
            )
        return payload
