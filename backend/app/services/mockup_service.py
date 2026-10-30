import copy
from datetime import UTC, datetime
from uuid import uuid4

from psycopg.types.json import Jsonb

from app.models.mockups import Design, DesignReview
from app.models.schemas import normalized


def normalize_design_references(design, backlog):
    """Correcciones inequívocas: formato, duplicados y tipo de referencia; nunca inventar vínculos."""
    value = Design.model_validate(design).model_dump(mode="json")
    stories = {s["id"]: s for s in backlog["historias"]}
    criteria = {c["id"] for s in stories.values() for c in s["criterios_aceptacion"]}
    requirements = {r["id"] for s in stories.values() for r in s["requisitos_origen"]}
    known = set(stories) | criteria | requirements | {s["id"] for s in value["pantallas"]}
    canonical = {r.casefold(): r for r in known}

    def refs(values):
        return list(dict.fromkeys(canonical.get(v.strip().casefold(), v.strip()) for v in values))

    for screen in value["pantallas"]:
        screen["ids_historias"] = refs(screen["ids_historias"])
        screen["ids_criterios_visuales"] = refs(screen["ids_criterios_visuales"])
        incoming = refs(screen["ids_criterios_visuales"] + screen["ids_requisitos_visuales"])
        screen["ids_criterios_visuales"] = [r for r in incoming if r not in requirements]
        screen["ids_requisitos_visuales"] = [r for r in incoming if r in requirements]
        for control in screen["controles"]:
            # Tipar según el contrato de origen, sin asociar historias nuevas automáticamente.
            incoming = refs(control["ids_criterios"] + control["ids_requisitos"])
            control["ids_criterios"] = [r for r in incoming if r not in requirements]
            control["ids_requisitos"] = [r for r in incoming if r in requirements]
            control["opciones"] = list(dict.fromkeys(control["opciones"]))
            if control["destino"]:
                control["destino"] = canonical.get(
                    control["destino"].strip().casefold(), control["destino"]
                )
    return value


def assess_design(design, backlog, semantic):
    value = Design.model_validate(design).model_dump(mode="json")
    stories = {s["id"]: s for s in backlog["historias"]}
    screen_ids = {s["id"] for s in value["pantallas"]}
    findings = []
    covered_stories, covered_criteria = set(), set()

    def error(text, ids):
        findings.append({"severidad": "error", "descripcion": text, "ids_elementos": ids})

    all_criteria = {c["id"] for s in stories.values() for c in s["criterios_aceptacion"]}
    nonvisual = {c["id_criterio"] for c in value["criterios_no_visuales"]}
    if nonvisual - all_criteria:
        error("Criterios no visuales inexistentes", sorted(nonvisual - all_criteria))
    if len(nonvisual) != len(value["criterios_no_visuales"]):
        error("Criterios no visuales duplicados", sorted(nonvisual))
    covered_criteria |= nonvisual & all_criteria
    for sid, story in stories.items():
        criteria = {c["id"] for c in story["criterios_aceptacion"]}
        if criteria and criteria <= nonvisual:
            covered_stories.add(sid)

    for screen in value["pantallas"]:
        refs = set(screen["ids_historias"])
        if refs - stories.keys():
            error("Pantalla relacionada con historias inexistentes", [screen["id"]])
        covered_stories |= refs
        allowed = {
            c["id"] for sid in refs & stories.keys() for c in stories[sid]["criterios_aceptacion"]
        }
        requirements = {
            r["id"] for sid in refs & stories.keys() for r in stories[sid]["requisitos_origen"]
        }
        visual = set(screen["ids_criterios_visuales"])
        if set(screen["ids_requisitos_visuales"]) - requirements:
            error("La pantalla referencia requisitos visuales ajenos", sorted(set(screen["ids_requisitos_visuales"]) - requirements))
        if visual - allowed:
            error("La pantalla referencia criterios visuales ajenos", sorted(visual - allowed))
        covered_criteria.update(visual & allowed)
        for control in screen["controles"]:
            if set(control["ids_requisitos"]) - requirements:
                error(
                    "El control referencia requisitos ajenos a su pantalla",
                    sorted(set(control["ids_requisitos"]) - requirements),
                )
            if set(control["ids_criterios"]) - allowed:
                error(
                    "El control referencia criterios ajenos a su pantalla",
                    [
                        screen["id"],
                        control["clave"],
                        *sorted(set(control["ids_criterios"]) - allowed),
                    ],
                )
            covered_criteria.update(set(control["ids_criterios"]) & allowed)
            if control["destino"] and (
                control["tipo"] != "boton" or control["destino"] not in screen_ids
            ):
                error("Destino de navegación inválido", [screen["id"], control["clave"]])
            if control["tipo"] == "selector" and not control["opciones"]:
                error("El selector no tiene opciones", [screen["id"], control["clave"]])
            if control["tipo"] == "ficha" and not control["opciones"]:
                error("La ficha no tiene datos de ejemplo", [screen["id"], control["clave"]])
    missing = sorted(stories.keys() - covered_stories)
    missing_criteria = sorted(
        {c["id"] for s in stories.values() for c in s["criterios_aceptacion"]} - covered_criteria
    )
    if missing:
        error("Hay historias sin pantalla", missing)
    if missing_criteria:
        error("Hay criterios de aceptación sin representación en el diseño", missing_criteria)
    if value["preguntas"]:
        error("Hay preguntas de diseño pendientes de aclaración", [])

    # Revisar contraste de los tokens principales sin inferencia.
    def lum(color):
        parts = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        parts = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in parts]
        return sum(v * w for v, w in zip(parts, (0.2126, 0.7152, 0.0722)))

    for front, back in (("texto", "fondo"), ("texto", "superficie"), ("texto_boton", "acento")):
        a, b = sorted((lum(value["paleta"][front]), lum(value["paleta"][back])))
        if (b + 0.05) / (a + 0.05) < 4.5:
            error("Contraste insuficiente entre " + front + " y " + back, [])
    known = (
        screen_ids
        | stories.keys()
        | {c["id"] for s in stories.values() for c in s["criterios_aceptacion"]}
    )
    known |= {r["id"] for group in ("epicas", "features") for r in backlog.get(group, [])}
    known |= {r["id"] for s in stories.values() for r in s["requisitos_origen"]}
    # Las observaciones del backlog ya se revisaron en la fase 2; no se repiten como hallazgos de diseño.
    inherited = {
        normalized(f["descripcion"]) for f in backlog.get("validacion", {}).get("observaciones", [])
    }
    for finding in DesignReview.model_validate(semantic).observaciones:
        if set(finding.ids_elementos) - known:
            raise ValueError("El validador de diseño referenció elementos desconocidos")
        if finding.severidad != "error" and normalized(finding.descripcion) in inherited:
            continue
        findings.append(finding.model_dump())
    return {
        "observaciones": findings,
        "historias_sin_pantalla": missing,
        "criterios_sin_representacion": missing_criteria,
        "criterios_no_visuales": value["criterios_no_visuales"],
        "puede_publicar": not any(f["severidad"] == "error" for f in findings),
        "alcance": "Estructura declarativa y contraste; no inspección visual por imagen",
    }


def merge_design(proposed, previous, target=None):
    value = Design.model_validate(proposed).model_dump(mode="json")
    if not target:
        return value
    if not previous or target not in {s["id"] for s in previous["pantallas"]}:
        raise ValueError("Pantalla de origen no encontrada")
    if len(value["pantallas"]) != 1 or value["pantallas"][0]["id"] != target:
        raise ValueError("El refinamiento debe devolver exclusivamente la pantalla seleccionada")
    merged = copy.deepcopy(previous)
    merged["pantallas"] = [
        value["pantallas"][0] if s["id"] == target else s for s in merged["pantallas"]
    ]
    merged["preguntas"] = list(dict.fromkeys(previous.get("preguntas", []) + value["preguntas"]))
    # La paleta global no cambia al refinar solo una pantalla.
    return merged


class MockupService:
    def __init__(self, db, events, backlog):
        self.db, self.events, self.backlog = db, events, backlog

    async def source(self, conn, pid, version):
        row = await (
            await conn.execute(
                "SELECT payload FROM backlog_publications WHERE project_id=%s AND version=%s",
                (pid, version),
            )
        ).fetchone()
        if not row:
            raise ValueError("Primero apruebe y publique el backlog seleccionado")
        latest = await (
            await conn.execute(
                "SELECT max(version) AS v FROM backlog_publications WHERE project_id=%s", (pid,)
            )
        ).fetchone()
        project = await (
            await conn.execute("SELECT state_revision FROM projects WHERE id=%s", (pid,))
        ).fetchone()
        if (
            not project
            or row["payload"]["version_estado_origen"] != project["state_revision"]
            or latest["v"] != version
        ):
            raise ValueError(
                "El backlog de origen está desactualizado; publique una versión vigente"
            )
        conflict = await (
            await conn.execute(
                "SELECT id FROM conflicts WHERE project_id=%s AND resolved_at IS NULL LIMIT 1",
                (pid,),
            )
        ).fetchone()
        if conflict:
            raise ValueError("Resuelva las contradicciones del proyecto antes de continuar")
        return row["payload"]

    async def start(self, pid, request):
        async with self.db.pool.connection() as conn, conn.transaction():
            project = await (await conn.execute(
                "SELECT mode FROM projects WHERE id=%s FOR UPDATE", (pid,)
            )).fetchone()
            if not project:
                raise LookupError("Proyecto no encontrado")
            prior = await (
                await conn.execute(
                    "SELECT id,input FROM executions WHERE project_id=%s AND kind='mockups' AND request_id=%s",
                    (pid, request["id_solicitud"]),
                )
            ).fetchone()
            if prior:
                if prior["input"]["request"] != request:
                    raise ValueError("La solicitud ya se usó con otros datos")
                return str(prior["id"]), False
            active = await (
                await conn.execute(
                    "SELECT id FROM executions WHERE project_id=%s AND kind='mockups' AND status IN ('pendiente','ejecutando')",
                    (pid,),
                )
            ).fetchone()
            if active:
                raise ValueError("Ya hay una generación de mockups en curso")
            backlog = await self.source(conn, pid, request["version_backlog"])
            old = await (
                await conn.execute(
                    "SELECT version,payload FROM mockup_revisions WHERE project_id=%s ORDER BY version DESC LIMIT 1",
                    (pid,),
                )
            ).fetchone()
            previous = old["payload"] if old else None
            if request.get("pantalla_id") and request.get("version_base") != (
                old["version"] if old else 0
            ):
                raise ValueError("Abra la última revisión antes de refinar una pantalla")
            if request.get("pantalla_id") and (
                not previous
                or previous["version_backlog_origen"] != request["version_backlog"]
                or request["pantalla_id"] not in {s["id"] for s in previous["diseno"]["pantallas"]}
            ):
                raise ValueError("Seleccione una pantalla de la revisión vigente del mismo backlog")
            baseline = await (
                await conn.execute(
                    "SELECT payload FROM baselines WHERE project_id=%s AND version=%s",
                    (pid, backlog["version_linea_base_origen"]),
                )
            ).fetchone()
            decision = await (
                await conn.execute(
                    "SELECT status,note FROM mockup_decisions WHERE project_id=%s ORDER BY version DESC LIMIT 1",
                    (pid,),
                )
            ).fetchone()
            run_id = str(uuid4())
            context = {
                "backlog": backlog,
                "linea_base": baseline["payload"],
                "anterior": previous,
                "head": old["version"] if old else 0,
                "decision_anterior": decision,
            }
            initial = {"project_id": str(pid), "request": request, "context": context}
            await conn.execute(
                "INSERT INTO executions(id,project_id,kind,request_id,input) VALUES(%s,%s,'mockups',%s,%s)",
                (run_id, pid, request["id_solicitud"], Jsonb(initial)),
            )
        return run_id, True

    async def persist(self, state):
        pid, run_id = state["project_id"], state["execution_id"]
        ctx = state["context"]
        async with self.db.pool.connection() as conn, conn.transaction():
            project = await (await conn.execute(
                "SELECT mode FROM projects WHERE id=%s FOR UPDATE", (pid,)
            )).fetchone()
            if not project:
                raise LookupError("Proyecto no encontrado")
            existing = await (
                await conn.execute(
                    "SELECT payload FROM mockup_revisions WHERE execution_id=%s", (run_id,)
                )
            ).fetchone()
            if existing:
                return existing["payload"]
            await self.source(conn, pid, state["request"]["version_backlog"])
            latest = await (
                await conn.execute(
                    "SELECT coalesce(max(version),0) AS v FROM mockup_revisions WHERE project_id=%s",
                    (pid,),
                )
            ).fetchone()
            if latest["v"] != ctx["head"]:
                raise ValueError("Cambió la revisión de diseño durante la ejecución")
            design = copy.deepcopy(state["design"])
            previous_design = (
                Design.model_validate(ctx["anterior"]["diseno"]).model_dump(mode="json")
                if ctx["anterior"]
                else {"pantallas": []}
            )
            old = {s["id"]: s for s in previous_design["pantallas"]}
            history = await (
                await conn.execute(
                    "SELECT payload FROM mockup_revisions WHERE project_id=%s ORDER BY version",
                    (pid,),
                )
            ).fetchall()
            versions = {}
            for row in history:
                for s in row["payload"]["diseno"]["pantallas"]:
                    versions[s["id"]] = max(versions.get(s["id"], 0), s["version"])
            palette_changed = bool(
                ctx["anterior"] and ctx["anterior"]["diseno"]["paleta"] != design["paleta"]
            )
            for screen in design["pantallas"]:
                before = old.get(screen["id"])

                def compare(s):
                    return {k: v for k, v in s.items() if k != "version"}

                screen["version"] = (
                    before["version"]
                    if before and compare(before) == compare(screen) and not palette_changed
                    else versions.get(screen["id"], 0) + 1
                )
            old_ids, new_ids = set(old), {s["id"] for s in design["pantallas"]}
            changed = [s["id"] for s in design["pantallas"] if s["id"] in old and s != old[s["id"]]]
            content = {
                "version_esquema": "3.0",
                "version_mockup": latest["v"] + 1,
                "id_proyecto": pid,
                "id_ejecucion": run_id,
                "fecha": datetime.now(UTC).isoformat(),
                "version_backlog_origen": state["request"]["version_backlog"],
                "version_linea_base_origen": ctx["backlog"]["version_linea_base_origen"],
                "historias_origen": [
                    {"id": s["id"], "version": s["version"]} for s in ctx["backlog"]["historias"]
                ],
                "instrucciones": state["request"]["instrucciones"],
                "diseno": design,
                "validacion": state["report"],
                "correcciones_automaticas": state.get("corrections", 0),
                "cambios": {
                    "paleta_modificada": palette_changed,
                    "creadas": sorted(new_ids - old_ids),
                    "modificadas": changed,
                    "retiradas": sorted(old_ids - new_ids),
                },
            }
            await conn.execute(
                "INSERT INTO mockup_revisions(project_id,version,backlog_version,execution_id,payload) VALUES(%s,%s,%s,%s,%s)",
                (
                    pid,
                    content["version_mockup"],
                    content["version_backlog_origen"],
                    run_id,
                    Jsonb(content),
                ),
            )
            await conn.execute(
                "INSERT INTO events(execution_id,component,operation,status,description,data) VALUES(%s,'mockups','guardar_revision','completado','Revisión de mockups guardada',%s)",
                (run_id, Jsonb(content)),
            )
        return content

    async def list(self, pid):
        return await self.db.fetch(
            "SELECT r.version,r.backlog_version AS version_backlog,r.execution_id AS id_ejecucion,r.created_at AS fecha,d.status AS decision FROM mockup_revisions r LEFT JOIN mockup_decisions d USING(project_id,version) WHERE r.project_id=%s ORDER BY r.version DESC",
            (pid,),
        )

    async def get(self, pid, version):
        row = await self.db.one(
            "SELECT r.payload,d.status AS decision,d.note AS nota FROM mockup_revisions r LEFT JOIN mockup_decisions d USING(project_id,version) WHERE r.project_id=%s AND r.version=%s",
            (pid, version),
        )
        if not row:
            raise LookupError("Revisión de mockups no encontrada")
        try:
            async with self.db.pool.connection() as conn:
                await self.source(conn, pid, row["payload"]["version_backlog_origen"])
            stale = False
        except ValueError:
            stale = True
        return {**row, "desactualizado": stale}

    async def review(self, pid, version, review):
        async with self.db.pool.connection() as conn, conn.transaction():
            await conn.execute("SELECT id FROM projects WHERE id=%s FOR UPDATE", (pid,))
            row = await (
                await conn.execute(
                    "SELECT payload FROM mockup_revisions WHERE project_id=%s AND version=%s",
                    (pid, version),
                )
            ).fetchone()
            if not row:
                raise LookupError("Revisión de mockups no encontrada")
            prior = await (
                await conn.execute(
                    "SELECT status FROM mockup_decisions WHERE project_id=%s AND version=%s",
                    (pid, version),
                )
            ).fetchone()
            if prior:
                raise ValueError("Esta revisión ya tiene una decisión registrada")
            value = row["payload"]
            if review.accion == "aprobar":
                latest = await (
                    await conn.execute(
                        "SELECT max(version) AS v FROM mockup_revisions WHERE project_id=%s", (pid,)
                    )
                ).fetchone()
                if latest["v"] != version:
                    raise ValueError("Solo puede publicar la última revisión")
                await self.source(conn, pid, value["version_backlog_origen"])
                if not value["validacion"]["puede_publicar"]:
                    raise ValueError("Corrija los errores y preguntas antes de publicar")
            status = "aprobado_por_humano" if review.accion == "aprobar" else "descartado"
            await conn.execute(
                "INSERT INTO mockup_decisions(project_id,version,status,note) VALUES(%s,%s,%s,%s)",
                (pid, version, status, review.nota),
            )
            await conn.execute(
                "INSERT INTO events(execution_id,component,operation,status,description,data) VALUES(%s,'mockups','revision_humana',%s,'Decisión humana sobre mockups',%s)",
                (
                    value["id_ejecucion"],
                    status,
                    Jsonb(
                        {"version_mockup": version, "nota": review.nota, "accion": review.accion}
                    ),
                ),
            )
        return await self.get(pid, version)

    async def view(self, pid, version, screen_id):
        item = await self.get(pid, version)
        if screen_id not in {s["id"] for s in item["payload"]["diseno"]["pantallas"]}:
            raise LookupError("Pantalla no encontrada en esta revisión")
        await self.events.emit(
            item["payload"]["id_ejecucion"],
            "visor_mockups",
            "pantalla_visualizada",
            "completado",
            "Pantalla presentada en el visor",
            {"version_mockup": version, "pantalla_id": screen_id},
        )
        return {"estado": "registrado"}
