"""Identidades, versiones y comprobaciones deterministas del backlog."""

import re
from copy import deepcopy
from datetime import UTC, datetime

from app.models.backlog import (
    BacklogContent,
    Criterion,
    Epic,
    Feature,
    Finding,
    Organization,
    SourceReference,
    Stories,
    Story,
    ValidationReport,
)
from app.models.schemas import normalized
from app.services.roles import is_confirmation, is_privileged, subject_is_privileged

GROUPS = ("epicas", "features", "historias")
BASELINE_GROUPS = (
    "requisitos",
    "objetivos",
    "actores",
    "decisiones",
    "reglas_negocio",
    "restricciones",
    "preguntas_pendientes",
    "supuestos",
)


def already_resolved(question, resolved):
    """Una pregunta que repite una PRE ya descartada no reabre la aclaración."""
    if re.search(r"\bPRE-\d+\b", question) and any(item["id"] in question for item in resolved):
        return True
    words = set(normalized(question).split())
    if len(words) < 4:
        return False
    for item in resolved:
        for text in item["textos"]:
            other = set(normalized(text).split())
            if other and len(words & other) / len(words | other) >= 0.6:
                return True
    return False


def baseline_versions(baseline):
    return {item["id"]: item["version"] for group in BASELINE_GROUPS for item in baseline[group]}


def all_items(content):
    return [item for group in GROUPS for item in content.get(group, [])]


def substantive(item):
    return {key: value for key, value in item.items() if key not in {"id", "version"}}


def version_item(item, known, active_ids):
    old = known.get(item["id"])
    item["version"] = (
        (
            old["version"]
            + int(substantive(old) != substantive(item) or item["id"] not in active_ids)
        )
        if old
        else 1
    )
    return item


def functional_sources(baseline):
    return {
        item["id"]: item
        for group in ("requisitos", "restricciones", "reglas_negocio")
        for item in baseline.get(group, [])
    }


def references(ids, baseline):
    sources = functional_sources(baseline)
    # Repetir una fuente no aporta información; conservar una sola referencia.
    ids = list(dict.fromkeys(ids))
    unknown = sorted(set(ids) - sources.keys())
    if not ids or unknown:
        raise ValueError(
            "Referencias a fuentes funcionales inexistentes en la línea base: "
            + ", ".join(unknown or ["sin fuente"])
        )
    return [
        SourceReference(id=key, version=sources[key]["version"]).model_dump() for key in sorted(ids)
    ]


def criteria(values, story_id, previous=None, history=None):
    previous = previous or []
    historical = {item["id"]: item for item in [*(history or []), *previous]}

    def key(value):
        return tuple(normalized(value[name]) for name in ("dado", "cuando", "entonces"))

    assigned, used = [None] * len(values), set()
    for index, value in enumerate(values):
        match = next(
            (
                old
                for old in [*previous, *historical.values()]
                if key(old) == key(value) and old["id"] not in used
            ),
            None,
        )
        if match:
            assigned[index] = match["id"]
            used.add(match["id"])
    counter = max((int(old["id"].rsplit("-", 1)[-1]) for old in historical.values()), default=0)
    result = []
    for index, value in enumerate(values):
        criterion_id = assigned[index]
        if criterion_id is None:
            if len(values) == len(previous) and previous[index]["id"] not in used:
                criterion_id = previous[index]["id"]
            else:
                counter += 1
                criterion_id = f"{story_id}-CA-{counter:02d}"
            used.add(criterion_id)
        result.append(Criterion(id=criterion_id, **value).model_dump())
    return result


def prepare_generated(context, organization, stories, run_id):
    organization = Organization.model_validate(organization)
    stories = Stories.model_validate(stories)
    previous = context["previous"] or {}
    known = context["known"]
    active = {item["id"] for item in all_items(previous)}
    counters, mapping, allocated = dict(context["project"]["counters"]), {}, set()
    baseline = context["baseline"]

    def identify(draft, group, prefix):
        if draft.clave in mapping:
            raise ValueError("Las claves temporales de los agentes deben ser únicas")
        item_id = draft.id_existente
        if item_id:
            if item_id not in known or not item_id.startswith(prefix + "-"):
                raise ValueError(
                    "El agente intentó reutilizar un identificador ajeno o inexistente"
                )
        else:
            matches = [
                item
                for item in previous.get(group, [])
                if normalized(item["titulo"]) == normalized(draft.titulo)
            ]
            if len(matches) == 1:
                item_id = matches[0]["id"]
            else:
                counters[prefix] = counters.get(prefix, 0) + 1
                item_id = f"{prefix}-{counters[prefix]:03d}"
        if item_id in allocated:
            raise ValueError("El agente repitió un identificador de artefacto")
        allocated.add(item_id)
        mapping[draft.clave] = item_id
        return item_id

    epics, features, user_stories = [], [], []
    for draft in organization.epicas:
        item = Epic(
            id=identify(draft, "epicas", "EP"),
            version=1,
            titulo=draft.titulo,
            descripcion=draft.descripcion,
            requisitos_origen=references(draft.ids_requisitos, baseline),
        ).model_dump()
        epics.append(version_item(item, known, active))
    epic_ids = {item["id"] for item in epics}
    for draft in organization.features:
        parent = mapping.get(draft.clave_epica, draft.clave_epica)
        if parent not in epic_ids:
            raise ValueError("Una feature no corresponde a ninguna épica propuesta")
        item = Feature(
            id=identify(draft, "features", "FE"),
            version=1,
            titulo=draft.titulo,
            descripcion=draft.descripcion,
            id_epica=parent,
            requisitos_origen=references(draft.ids_requisitos, baseline),
        ).model_dump()
        features.append(version_item(item, known, active))
    feature_ids = {item["id"] for item in features}
    actors = {item["id"]: item for item in baseline["actores"]}
    for draft in stories.historias:
        parent = mapping.get(draft.clave_feature, draft.clave_feature)
        if not actors:
            raise ValueError(
                "La línea base no tiene actores. Pide al analista que proponga los actores, "
                "apruébalos y publica una nueva línea base"
            )
        if parent not in feature_ids or draft.id_actor not in actors:
            raise ValueError(
                "La historia requiere una feature y un actor existentes en sus contratos de entrada"
            )
        item_id = identify(draft, "historias", "HU")
        actor = actors[draft.id_actor]
        item = Story(
            id=item_id,
            version=1,
            titulo=draft.titulo,
            descripcion=f"Como {actor['descripcion']}, quiero {draft.quiero} para {draft.para}",
            id_feature=parent,
            actor=SourceReference(id=actor["id"], version=actor["version"]),
            como=actor["descripcion"],
            quiero=draft.quiero,
            para=draft.para,
            requisitos_origen=references(draft.ids_requisitos, baseline),
            criterios_aceptacion=criteria(
                [c.model_dump() for c in draft.criterios_aceptacion],
                item_id,
                known.get(item_id, {}).get("criterios_aceptacion", []),
                context.get("criterion_history", {}).get(item_id, []),
            ),
        ).model_dump()
        user_stories.append(version_item(item, known, active))
    candidate = metadata(context, run_id, "generar", context.get("instructions", ""))
    question_sources = {i["id"]: i["descripcion"] for i in baseline["preguntas_pendientes"]}
    resolved = context.get("resolved_questions", [])
    questions = [
        question_sources.get(q, q)
        for q in [*organization.preguntas_pendientes, *stories.preguntas_pendientes]
    ]
    candidate.update(
        epicas=epics,
        features=features,
        historias=user_stories,
        preguntas_pendientes=list(
            dict.fromkeys(q for q in questions if not already_resolved(q, resolved))
        ),
    )
    return candidate, counters


def metadata(context, run_id, operation, note):
    return {
        "version_esquema": "2.0",
        "id_proyecto": str(context["project"]["id"]),
        "version_backlog": context["head"] + 1,
        "version_linea_base_origen": context["baseline"]["version_linea_base"],
        "version_estado_origen": context["project"]["state_revision"],
        "id_ejecucion": run_id,
        "fecha": datetime.now(UTC).isoformat(),
        "operacion": operation,
        "nota": note,
    }


def prepare_existing(context, run_id, edit=None):
    if not context["previous"]:
        raise ValueError("No existe una propuesta de backlog")
    content = deepcopy(context["previous"])
    content.pop("validacion", None)
    content.update(
        metadata(
            context,
            run_id,
            "editar" if edit else "validar",
            edit["nota"] if edit else "Nueva revisión del validador funcional",
        )
    )
    if edit:
        item = next((i for i in all_items(content) if i["id"] == edit["id_elemento"]), None)
        if not item:
            raise LookupError("Elemento no encontrado en esta versión del backlog")
        item.update(
            titulo=edit["titulo"],
            descripcion=edit["descripcion"],
            requisitos_origen=references(edit["ids_requisitos"], context["baseline"]),
        )
        if item["id"].startswith("FE-"):
            if not edit.get("id_padre"):
                raise ValueError("La feature requiere una épica")
            item["id_epica"] = edit["id_padre"]
        if item["id"].startswith("HU-"):
            actor = next(
                (a for a in context["baseline"]["actores"] if a["id"] == edit.get("id_actor")), None
            )
            if (
                not actor
                or not edit.get("id_padre")
                or not edit.get("quiero")
                or not edit.get("para")
            ):
                raise ValueError("La historia requiere actor, feature, necesidad y beneficio")
            item.update(
                actor={"id": actor["id"], "version": actor["version"]},
                como=actor["descripcion"],
                id_feature=edit["id_padre"],
                quiero=edit["quiero"],
                para=edit["para"],
            )
            item["descripcion"] = (
                f"Como {item['como']}, quiero {item['quiero']} para {item['para']}"
            )
            if edit.get("criterios_aceptacion") is not None:
                item["criterios_aceptacion"] = criteria(
                    edit["criterios_aceptacion"],
                    item["id"],
                    context["known"][item["id"]].get("criterios_aceptacion", []),
                    context.get("criterion_history", {}).get(item["id"], []),
                )
        version_item(item, context["known"], {i["id"] for i in all_items(context["previous"])})
        if item == next(i for i in all_items(context["previous"]) if i["id"] == item["id"]):
            raise ValueError("No se detectaron modificaciones")
    return content, dict(context["project"]["counters"])


class UnknownReviewReference(ValueError):
    def __init__(self, ids):
        self.ids = sorted(ids)
        super().__init__("El validador referenció elementos inexistentes: " + ", ".join(self.ids))


def review_ids(candidate, baseline, historical_ids=()):
    known = (
        {i["id"] for i in all_items(candidate)}
        | baseline_versions(baseline).keys()
        | set(historical_ids)
    )
    known |= {c["id"] for s in candidate["historias"] for c in s["criterios_aceptacion"]}
    return known


def normalize_review(semantic, known):
    def key(value):
        return re.sub(r"[0-9]+", lambda m: str(int(m.group())), value.strip().upper())

    mapping = {}
    for item in known:
        mapping.setdefault(key(item), []).append(item)
    value = semantic.model_dump(mode="json")
    for finding in value["observaciones"]:
        fixed = []
        for ref in finding["ids_elementos"]:
            matches = mapping.get(key(ref), [])
            fixed.append(matches[0] if len(matches) == 1 else ref)
        finding["ids_elementos"] = list(dict.fromkeys(fixed))
    return semantic.__class__.model_validate(value)


def validate_backlog(candidate, baseline, semantic, historical_ids=()):
    observations = []
    requirements = {key: item["version"] for key, item in functional_sources(baseline).items()}
    mandatory_requirements = {i["id"] for i in baseline["requisitos"]}
    actors = {i["id"]: i["version"] for i in baseline["actores"]}
    actor_text = {i["id"]: i.get("descripcion", "") for i in baseline["actores"]}
    epics = {i["id"]: i for i in candidate["epicas"]}
    features = {i["id"]: i for i in candidate["features"]}
    stories = candidate["historias"]

    def error(code, message, ids):
        observations.append(
            Finding(
                severidad="error", codigo=code, descripcion=message, ids_elementos=ids
            ).model_dump()
        )

    for group in GROUPS:
        titles = set()
        for item in candidate[group]:
            title = normalized(item["titulo"])
            if title in titles:
                error("TITULO_DUPLICADO", "Hay títulos duplicados en el mismo nivel", [item["id"]])
            titles.add(title)
            for ref in item["requisitos_origen"]:
                if requirements.get(ref["id"]) != ref["version"]:
                    error(
                        "ORIGEN_INVALIDO",
                        "El requisito de origen no corresponde a esta línea base",
                        [item["id"], ref["id"]],
                    )
    for item in candidate["features"]:
        parent = epics.get(item["id_epica"])
        if not parent:
            error("PADRE_INVALIDO", "La épica de la feature no existe", [item["id"]])
        elif {r["id"] for r in item["requisitos_origen"]} - {
            r["id"] for r in parent["requisitos_origen"]
        }:
            error("ORIGEN_FUERA_EPICA", "La feature usa requisitos fuera de su épica", [item["id"]])
    for item in stories:
        criterion_texts = [
            tuple(normalized(c[key]) for key in ("dado", "cuando", "entonces"))
            for c in item["criterios_aceptacion"]
        ]
        if len(criterion_texts) != len(set(criterion_texts)):
            error("CRITERIOS_DUPLICADOS", "Hay criterios de aceptación repetidos", [item["id"]])
        parent = features.get(item["id_feature"])
        if not parent:
            error("PADRE_INVALIDO", "La feature de la historia no existe", [item["id"]])
        elif {r["id"] for r in item["requisitos_origen"]} - {
            r["id"] for r in parent["requisitos_origen"]
        }:
            error(
                "ORIGEN_FUERA_FEATURE",
                "La historia usa requisitos fuera de su feature",
                [item["id"]],
            )
        if actors.get(item["actor"]["id"]) != item["actor"]["version"]:
            error(
                "ACTOR_INVALIDO", "El actor debe existir en la línea base funcional", [item["id"]]
            )
        elif subject_is_privileged(item["titulo"]) and not is_privileged(
            actor_text.get(item["actor"]["id"], "")
        ):
            error(
                "ACTOR_INCOHERENTE",
                "La historia describe una acción de un rol aprobador o administrativo, pero su actor es otro",
                [item["id"], item["actor"]["id"]],
            )
        # Enlazar un requisito no lo cubre: cada RF necesita al menos un criterio comprobable.
        functional = [
            r["id"] for r in item["requisitos_origen"] if r["id"] in mandatory_requirements
        ]
        if len(functional) > 2 * len(item["criterios_aceptacion"]):
            error(
                "HISTORIA_SOBRECARGADA",
                "La historia enlaza demasiados requisitos funcionales para sus criterios de aceptación; "
                "divídala o añada un criterio por requisito",
                [item["id"], *functional],
            )
    for parent_id in epics:
        if not any(i["id_epica"] == parent_id for i in candidate["features"]):
            error("EPICA_VACIA", "La épica no tiene features", [parent_id])
    for parent_id in features:
        if not any(i["id_feature"] == parent_id for i in stories):
            error("FEATURE_SIN_HISTORIAS", "La feature todavía no tiene historias", [parent_id])
    covered_features = {
        r["id"] for item in candidate["features"] for r in item["requisitos_origen"]
    }
    covered_stories = {r["id"] for item in stories for r in item["requisitos_origen"]}
    uncovered = sorted(mandatory_requirements - (covered_features & covered_stories))
    if uncovered:
        error(
            "COBERTURA_INCOMPLETA",
            "Hay requisitos sin cobertura completa de features e historias",
            uncovered,
        )
    if candidate["preguntas_pendientes"]:
        error(
            "ACLARACIONES_PENDIENTES",
            "Resuelva las preguntas en los requisitos de origen y regenere la propuesta",
            [],
        )
    structural = not observations
    known_ids = review_ids(candidate, baseline, historical_ids)
    semantic = normalize_review(semantic, known_ids)
    for finding in semantic.observaciones:
        if set(finding.ids_elementos) - known_ids:
            raise UnknownReviewReference(set(finding.ids_elementos) - known_ids)
        if not is_confirmation(
            finding.model_dump()
        ):  # Confirmaciones del modelo: no son hallazgos.
            observations.append(finding.model_dump())
    report = ValidationReport(
        estructural=structural,
        semantica="completada",
        observaciones=observations,
        requisitos_sin_cobertura=uncovered,
        puede_publicar=not any(i["severidad"] == "error" for i in observations),
    )
    return BacklogContent.model_validate({**candidate, "validacion": report.model_dump()})


def compare_backlogs(before, after):
    old = {item["id"]: item for item in all_items(before or {})}
    new = {item["id"]: item for item in all_items(after or {})}
    return {
        "creados": sorted(new.keys() - old.keys()),
        "retirados": sorted(old.keys() - new.keys()),
        "modificados": sorted(key for key in old.keys() & new.keys() if old[key] != new[key]),
    }
