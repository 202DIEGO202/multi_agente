"""Fase 4: contexto compacto, reglas deterministas, versiones inmutables y aprobación."""

import re
from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

from psycopg.types.json import Jsonb

from app.models.architecture import ArchitectureReview
from app.models.schemas import normalized
from app.services.diagrams import build_views, files

SOFTWARE, INFRA, PLANNER = "arquitecto_software", "arquitecto_infraestructura", "planificador"


def trim(text, size=400):
    return text if len(text) <= size else text[: size - 1] + "…"


def actor_name(description):
    """Nombre corto para diagramas: 'Empleado que accede al portal…' -> 'Empleado'."""
    head = re.split(r"\s+(?:que|quien|el cual|la cual)\s+|[,.;:(]", description, maxsplit=1)[0]
    return trim(head.strip() or description, 40)


def compact_context(project, baseline, backlog, mockups):
    """Solo IDs y descripciones cortas: los agentes no reciben historiales ni JSON completo."""

    def items(group):
        return [
            {"id": i["id"], "descripcion": trim(i["descripcion"])} for i in baseline.get(group, [])
        ]

    return {
        "proyecto": project,
        "requisitos": [
            {"id": i["id"], "tipo": i["tipo"], "descripcion": trim(i["descripcion"])}
            for i in baseline["requisitos"]
        ],
        "actores": [
            {
                "id": i["id"],
                "nombre": actor_name(i["descripcion"]),
                "descripcion": trim(i["descripcion"], 200),
            }
            for i in baseline["actores"]
        ],
        "reglas_negocio": items("reglas_negocio"),
        "restricciones": items("restricciones"),
        "decisiones_funcionales": items("decisiones"),
        "historias": [
            {
                "id": h["id"],
                "titulo": h["titulo"],
                "quiero": trim(h["quiero"], 300),
                "criterios": [trim(c["entonces"], 200) for c in h["criterios_aceptacion"]],
                "requisitos": [r["id"] for r in h["requisitos_origen"]],
            }
            for h in backlog["historias"]
        ],
        "pantallas": [
            {"id": s["id"], "titulo": s["titulo"], "historias": s["ids_historias"]}
            for s in (mockups or {}).get("diseno", {}).get("pantallas", [])
        ],
    }


def allowed_technology(value, allowed):
    text = normalized(value)
    return any(normalized(item) and normalized(item) in text for item in allowed)


def reference_resolver(entries):
    """Traduce un nombre ('API Backend') o un texto con ID ('CT-002 API') al ID exacto."""
    by_name = {normalized(name): key for key, name in entries}
    ids = {key for key, _ in entries}

    def resolve(value):
        if value in ids:
            return value
        found = re.search(r"\b[A-Z]{2,3}-[0-9]{3,}\b", value)
        if found and found.group() in ids:
            return found.group()
        return by_name.get(normalized(value), value)

    return resolve


def normalize_software(software, context):
    """Corrige referencias por nombre sin otra llamada al modelo."""
    value = deepcopy(software)
    resolve = reference_resolver(
        [(a["id"], a["nombre"]) for a in context["actores"]]
        + [(c["id"], c["nombre"]) for c in value["contenedores"]]
        + [(c["id"], c["nombre"]) for c in value["componentes"]]
    )
    containers = reference_resolver([(c["id"], c["nombre"]) for c in value["contenedores"]])
    for c in value["componentes"]:
        c["contenedor"] = containers(c["contenedor"])
    for r in value["relaciones"]:
        r["origen"], r["destino"] = resolve(r["origen"]), resolve(r["destino"])
    for f in value["flujos"]:
        for s in [*f["pasos"], *f["alternativa"]]:
            s["de"], s["a"] = resolve(s["de"]), resolve(s["a"])
    return value


def normalize_infra(infra, software):
    value = deepcopy(infra)
    containers = reference_resolver([(c["id"], c["nombre"]) for c in software["contenedores"]])
    nodes = reference_resolver([(n["id"], n["nombre"]) for n in value["nodos"]])
    for n in value["nodos"]:
        n["aloja"] = list(dict.fromkeys(containers(item) for item in n["aloja"]))
    for c in value["conexiones"]:
        c["origen"], c["destino"] = nodes(c["origen"]), nodes(c["destino"])
    return value


def assess_architecture(context, software, infra, plan, allowed, semantic=None):
    """Reglas que no necesitan modelo. Cada hallazgo indica el agente que debe corregir."""
    findings = []

    def add(agent, code, message, ids, severity="error"):
        findings.append(
            {
                "severidad": severity,
                "codigo": code,
                "agente": agent,
                "descripcion": message,
                "ids_elementos": ids,
            }
        )

    requirements = {r["id"] for r in context["requisitos"]}
    sources = requirements | {
        i["id"] for g in ("reglas_negocio", "restricciones") for i in context[g]
    }
    stories = {h["id"] for h in context["historias"]}
    actors = {a["id"] for a in context["actores"]}
    if software:
        for group, label in (
            ("atributos_calidad", "atributos"),
            ("decisiones", "decisiones"),
            ("contenedores", "contenedores"),
            ("componentes", "componentes"),
            ("flujos", "flujos"),
        ):
            ids = [i["id"] for i in software[group]]
            if len(ids) != len(set(ids)):
                add(SOFTWARE, "ID_DUPLICADO", f"Hay identificadores duplicados en {label}", ids)
        attributes = {a["id"] for a in software["atributos_calidad"]}
        containers = {c["id"]: c for c in software["contenedores"]}
        components = {c["id"]: c for c in software["componentes"]}
        for a in software["atributos_calidad"]:
            if set(a["ids_requisitos"]) - sources:
                add(
                    SOFTWARE,
                    "ORIGEN_INVALIDO",
                    "El atributo cita requisitos inexistentes",
                    [a["id"]],
                )
        for r in context["requisitos"]:
            if r["tipo"] == "requisito_no_funcional" and not any(
                r["id"] in a["ids_requisitos"] for a in software["atributos_calidad"]
            ):
                add(
                    SOFTWARE,
                    "RNF_SIN_ATRIBUTO",
                    "Requisito no funcional sin atributo de calidad",
                    [r["id"]],
                )
        for d in software["decisiones"]:
            if set(d["ids_atributos"]) - attributes:
                add(
                    SOFTWARE,
                    "ADR_SIN_ATRIBUTO",
                    "La decisión cita atributos inexistentes",
                    [d["id"]],
                )
        apis = [c["id"] for c in software["contenedores"] if c["tipo"] == "api"]
        if len(apis) != 1:
            add(
                SOFTWARE,
                "MONOLITO_INVALIDO",
                "Un monolito debe tener exactamente un contenedor de API",
                apis,
            )
        if not any(c["tipo"] == "base_datos" for c in software["contenedores"]):
            add(SOFTWARE, "SIN_BASE_DATOS", "Falta el contenedor de base de datos", [])
        for c in software["contenedores"]:
            if c["tipo"] != "servicio_externo" and not allowed_technology(c["tecnologia"], allowed):
                add(
                    SOFTWARE,
                    "TECNOLOGIA_NO_PERMITIDA",
                    f"Tecnología fuera del catálogo: {c['tecnologia']}",
                    [c["id"]],
                )
        for c in software["componentes"]:
            parent = containers.get(c["contenedor"])
            if not parent or parent["tipo"] == "servicio_externo":
                add(
                    SOFTWARE,
                    "COMPONENTE_SIN_CONTENEDOR",
                    "El componente no pertenece a un contenedor propio",
                    [c["id"]],
                )
            if set(c["ids_historias"]) - stories:
                add(
                    SOFTWARE,
                    "HISTORIA_INEXISTENTE",
                    "El componente cita historias inexistentes",
                    [c["id"]],
                )
        covered = {h for c in software["componentes"] for h in c["ids_historias"]}
        if stories - covered:
            add(
                SOFTWARE,
                "HISTORIA_SIN_COMPONENTE",
                "Historias sin componente que las implemente",
                sorted(stories - covered),
            )
        endpoints = actors | set(containers) | set(components)
        for r in software["relaciones"]:
            if r["origen"] not in endpoints or r["destino"] not in endpoints:
                add(
                    SOFTWARE,
                    "RELACION_INVALIDA",
                    "Relación con extremos inexistentes",
                    [r["origen"], r["destino"]],
                )
        for f in software["flujos"]:
            if set(f["ids_historias"]) - stories:
                add(
                    SOFTWARE,
                    "HISTORIA_INEXISTENTE",
                    "El flujo cita historias inexistentes",
                    [f["id"]],
                )
            for s in [*f["pasos"], *f["alternativa"]]:
                if s["de"] not in endpoints or s["a"] not in endpoints:
                    add(
                        SOFTWARE,
                        "PASO_INVALIDO",
                        "Paso de secuencia con participantes inexistentes",
                        [f["id"]],
                    )
                    break
            if f["alternativa"] and not f["condicion_alternativa"]:
                add(
                    SOFTWARE,
                    "ALTERNATIVA_SIN_CONDICION",
                    "La alternativa necesita su condición",
                    [f["id"]],
                )
            if f["paso_desvio"] and f["paso_desvio"] > len(f["pasos"]):
                add(SOFTWARE, "DESVIO_INVALIDO", "El paso de desvío excede los pasos", [f["id"]])
    if software and infra:
        containers = {c["id"]: c for c in software["contenedores"]}
        nodes = {n["id"]: n for n in infra["nodos"]}
        if len(nodes) != len(infra["nodos"]):
            add(INFRA, "ID_DUPLICADO", "Hay nodos con el mismo identificador", list(nodes))
        for n in infra["nodos"]:
            if n["tipo"] != "servicio_externo" and not allowed_technology(n["tecnologia"], allowed):
                add(
                    INFRA,
                    "TECNOLOGIA_NO_PERMITIDA",
                    f"Tecnología fuera del catálogo: {n['tecnologia']}",
                    [n["id"]],
                )
            if set(n["aloja"]) - set(containers):
                add(
                    INFRA, "ALOJA_INEXISTENTE", "El nodo aloja contenedores inexistentes", [n["id"]]
                )
            if n["tipo"] == "contenedor" and not n["aloja"]:
                add(
                    INFRA,
                    "CONTENEDOR_VACIO",
                    "El nodo de contenedor no aloja ninguna pieza",
                    [n["id"]],
                )
        for env in ("local", "nube"):
            hosted = {c for n in infra["nodos"] if n["entorno"] == env for c in n["aloja"]}
            missing = [
                c
                for c, item in containers.items()
                if item["tipo"] != "servicio_externo" and c not in hosted
            ]
            if missing:
                add(
                    INFRA,
                    f"SIN_DESPLIEGUE_{env.upper()}",
                    f"Contenedores sin lugar de ejecución en {env}",
                    missing,
                )
        for c in infra["conexiones"]:
            if c["origen"] not in nodes or c["destino"] not in nodes:
                add(
                    INFRA,
                    "CONEXION_INVALIDA",
                    "Conexión con nodos inexistentes",
                    [c["origen"], c["destino"]],
                )
            elif nodes[c["origen"]]["entorno"] != nodes[c["destino"]]["entorno"]:
                add(
                    INFRA,
                    "CONEXION_ENTRE_ENTORNOS",
                    "Una conexión mezcla local y nube",
                    [c["origen"], c["destino"]],
                )
        if not any(n["entorno"] == "nube" and n["tipo"] == "balanceador" for n in infra["nodos"]):
            add(
                INFRA,
                "SIN_ENTRADA_NUBE",
                "Falta el punto de entrada (balanceador/ingress) en la nube",
                [],
                "advertencia",
            )
    if plan and software:
        components = {c["id"] for c in software["componentes"]}
        tasks = {t["id"]: t for t in plan["tareas"]}
        for t in plan["tareas"]:
            if set(t["ids_componentes"]) - components:
                add(
                    PLANNER,
                    "COMPONENTE_INEXISTENTE",
                    "La tarea cita componentes inexistentes",
                    [t["id"]],
                )
            if set(t["depende_de"]) - set(tasks) or t["id"] in t["depende_de"]:
                add(
                    PLANNER,
                    "DEPENDENCIA_INVALIDA",
                    "La tarea depende de tareas inexistentes",
                    [t["id"]],
                )
        order = {t["id"]: i for i, t in enumerate(plan["tareas"])}
        for t in plan["tareas"]:
            if any(order.get(d, -1) > order[t["id"]] for d in t["depende_de"]):
                add(
                    PLANNER,
                    "ORDEN_INVALIDO",
                    "Una tarea aparece antes que su dependencia",
                    [t["id"]],
                )
        untouched = components - {c for t in plan["tareas"] for c in t["ids_componentes"]}
        if untouched:
            add(
                PLANNER,
                "COMPONENTE_SIN_TAREA",
                "Componentes sin tarea de implementación",
                sorted(untouched),
                "advertencia",
            )
    if semantic:
        known = (
            sources
            | stories
            | actors
            | {
                i["id"]
                for g in (
                    "atributos_calidad",
                    "decisiones",
                    "contenedores",
                    "componentes",
                    "flujos",
                )
                for i in (software or {}).get(g, [])
            }
            | {n["id"] for n in (infra or {}).get("nodos", [])}
        )
        for finding in ArchitectureReview.model_validate(semantic).observaciones:
            value = finding.model_dump()
            value["ids_elementos"] = [i for i in value["ids_elementos"] if i in known]
            findings.append(value)
    return {
        "observaciones": findings,
        "puede_publicar": not any(f["severidad"] == "error" for f in findings)
        and not (software or {}).get("preguntas"),
        "agentes_con_errores": sorted({f["agente"] for f in findings if f["severidad"] == "error"}),
    }


class ArchitectureService:
    def __init__(self, db, events, mockups, settings):
        self.db, self.events, self.mockups, self.settings = db, events, mockups, settings

    async def start(self, pid, request):
        async with self.db.pool.connection() as conn, conn.transaction():
            await conn.execute("SELECT id FROM projects WHERE id=%s FOR UPDATE", (pid,))
            prior = await (
                await conn.execute(
                    "SELECT id,input FROM executions WHERE project_id=%s AND kind='arquitectura' AND request_id=%s",
                    (pid, request["id_solicitud"]),
                )
            ).fetchone()
            if prior:
                if prior["input"]["request"] != request:
                    raise ValueError("La solicitud ya se usó con otros datos")
                return str(prior["id"]), False
            active = await (
                await conn.execute(
                    "SELECT id FROM executions WHERE project_id=%s AND kind='arquitectura' AND status IN ('pendiente','ejecutando')",
                    (pid,),
                )
            ).fetchone()
            if active:
                raise ValueError("Ya hay una generación de arquitectura en curso")
            backlog = await self.mockups.source(conn, pid, request["version_backlog"])
            baseline = await (
                await conn.execute(
                    "SELECT payload FROM baselines WHERE project_id=%s AND version=%s",
                    (pid, backlog["version_linea_base_origen"]),
                )
            ).fetchone()
            mockups = await (
                await conn.execute(
                    "SELECT r.payload FROM mockup_revisions r JOIN mockup_decisions d USING(project_id,version) "
                    "WHERE r.project_id=%s AND r.backlog_version=%s AND d.status IN ('aprobado_por_humano','validado_automaticamente') "
                    "ORDER BY r.version DESC LIMIT 1",
                    (pid, request["version_backlog"]),
                )
            ).fetchone()
            project = await (
                await conn.execute("SELECT name FROM projects WHERE id=%s", (pid,))
            ).fetchone()
            head = await (
                await conn.execute(
                    "SELECT coalesce(max(version),0) AS v FROM architecture_revisions WHERE project_id=%s",
                    (pid,),
                )
            ).fetchone()
            decision = await (
                await conn.execute(
                    "SELECT status,note FROM architecture_decisions WHERE project_id=%s ORDER BY version DESC LIMIT 1",
                    (pid,),
                )
            ).fetchone()
            context = {
                "datos": compact_context(
                    project["name"],
                    baseline["payload"],
                    backlog,
                    mockups["payload"] if mockups else None,
                ),
                "tecnologias_permitidas": list(self.settings.architecture_technologies),
                "version_backlog": request["version_backlog"],
                "version_linea_base": backlog["version_linea_base_origen"],
                "version_mockups": mockups["payload"]["version_mockup"] if mockups else None,
                "head": head["v"],
                "decision_anterior": decision,
            }
            run_id = str(uuid4())
            initial = {"project_id": str(pid), "request": request, "context": context}
            await conn.execute(
                "INSERT INTO executions(id,project_id,kind,request_id,input) VALUES(%s,%s,'arquitectura',%s,%s)",
                (run_id, pid, request["id_solicitud"], Jsonb(initial)),
            )
        return run_id, True

    async def persist(self, state):
        pid, run_id, ctx = state["project_id"], state["execution_id"], state["context"]
        async with self.db.pool.connection() as conn, conn.transaction():
            project = await (await conn.execute(
                "SELECT mode FROM projects WHERE id=%s FOR UPDATE", (pid,)
            )).fetchone()
            if not project:
                raise LookupError("Proyecto no encontrado")
            existing = await (
                await conn.execute(
                    "SELECT payload FROM architecture_revisions WHERE execution_id=%s", (run_id,)
                )
            ).fetchone()
            if existing:
                return existing["payload"]
            await self.mockups.source(conn, pid, ctx["version_backlog"])
            latest = await (
                await conn.execute(
                    "SELECT coalesce(max(version),0) AS v FROM architecture_revisions WHERE project_id=%s",
                    (pid,),
                )
            ).fetchone()
            if latest["v"] != ctx["head"]:
                raise ValueError("Cambió la arquitectura durante la ejecución")
            data = ctx["datos"]
            content = {
                "version_esquema": "4.0",
                "version_arquitectura": latest["v"] + 1,
                "id_proyecto": pid,
                "nombre_proyecto": data["proyecto"],
                "id_ejecucion": run_id,
                "fecha": datetime.now(UTC).isoformat(),
                "version_backlog_origen": ctx["version_backlog"],
                "version_linea_base_origen": ctx["version_linea_base"],
                "version_mockups_origen": ctx["version_mockups"],
                "instrucciones": state["request"]["instrucciones"],
                "tecnologias_permitidas": ctx["tecnologias_permitidas"],
                "software": state["software"],
                "infraestructura": state["infra"],
                "plan": state.get("plan"),
                "validacion": state["report"],
                "correcciones_automaticas": state.get("corrections", 0),
                "consumo": state.get("usage", {}),
                "actores": data["actores"],
            }
            await conn.execute(
                "INSERT INTO architecture_revisions(project_id,version,backlog_version,execution_id,payload) VALUES(%s,%s,%s,%s,%s)",
                (
                    pid,
                    content["version_arquitectura"],
                    ctx["version_backlog"],
                    run_id,
                    Jsonb(content),
                ),
            )
            await conn.execute(
                "INSERT INTO events(execution_id,component,operation,status,description,data) "
                "VALUES(%s,'arquitectura','guardar_revision','completado','Arquitectura versionada guardada',%s)",
                (
                    run_id,
                    Jsonb(
                        {
                            "version_arquitectura": content["version_arquitectura"],
                            "consumo": content["consumo"],
                        }
                    ),
                ),
            )
        return content

    async def list(self, pid):
        return await self.db.fetch(
            "SELECT r.version,r.backlog_version AS version_backlog,r.execution_id AS id_ejecucion,r.created_at AS fecha,"
            "d.status AS decision FROM architecture_revisions r LEFT JOIN architecture_decisions d USING(project_id,version) "
            "WHERE r.project_id=%s ORDER BY r.version DESC",
            (pid,),
        )

    async def get(self, pid, version):
        row = await self.db.one(
            "SELECT r.payload,d.status AS decision,d.note AS nota FROM architecture_revisions r "
            "LEFT JOIN architecture_decisions d USING(project_id,version) WHERE r.project_id=%s AND r.version=%s",
            (pid, version),
        )
        if not row:
            raise LookupError("Revisión de arquitectura no encontrada")
        try:
            async with self.db.pool.connection() as conn:
                await self.mockups.source(conn, pid, row["payload"]["version_backlog_origen"])
            stale = False
        except ValueError:
            stale = True
        payload = row["payload"]
        # Las vistas se derivan del modelo canónico al leer; no forman parte del contrato guardado.
        if "actores" in payload:
            payload = {
                **payload,
                "vistas": build_views(
                    payload["nombre_proyecto"],
                    payload["actores"],
                    payload["software"],
                    payload["infraestructura"],
                ),
            }
        return {**row, "payload": payload, "desactualizado": stale}

    async def file(self, pid, version, name):
        content = (await self.get(pid, version))["payload"]
        generated = files(content)
        if name not in generated:
            raise LookupError("Archivo no disponible")
        return {"nombre": name, "contenido": generated[name], "archivos": list(generated)}

    async def review(self, pid, version, review):
        async with self.db.pool.connection() as conn, conn.transaction():
            await conn.execute("SELECT id FROM projects WHERE id=%s FOR UPDATE", (pid,))
            row = await (
                await conn.execute(
                    "SELECT payload FROM architecture_revisions WHERE project_id=%s AND version=%s",
                    (pid, version),
                )
            ).fetchone()
            if not row:
                raise LookupError("Revisión de arquitectura no encontrada")
            if await (
                await conn.execute(
                    "SELECT 1 FROM architecture_decisions WHERE project_id=%s AND version=%s",
                    (pid, version),
                )
            ).fetchone():
                raise ValueError("Esta revisión ya tiene una decisión registrada")
            value = row["payload"]
            if review.accion == "aprobar":
                latest = await (
                    await conn.execute(
                        "SELECT max(version) AS v FROM architecture_revisions WHERE project_id=%s",
                        (pid,),
                    )
                ).fetchone()
                if latest["v"] != version:
                    raise ValueError("Solo puede publicar la última revisión")
                await self.mockups.source(conn, pid, value["version_backlog_origen"])
                if not value["validacion"]["puede_publicar"]:
                    raise ValueError("Corrija los errores antes de publicar la arquitectura")
            status = "aprobado_por_humano" if review.accion == "aprobar" else "descartado"
            await conn.execute(
                "INSERT INTO architecture_decisions(project_id,version,status,note) VALUES(%s,%s,%s,%s)",
                (pid, version, status, review.nota),
            )
            await conn.execute(
                "INSERT INTO events(execution_id,component,operation,status,description,data) "
                "VALUES(%s,'arquitectura','revision_humana',%s,'Decisión humana sobre la arquitectura',%s)",
                (value["id_ejecucion"], status, Jsonb({"version": version, "nota": review.nota})),
            )
        return await self.get(pid, version)
