from test_persistence import environment, run

from app.models.schemas import Analysis, Change, Review
from app.services.project_service import separate_document_sources, validate_change


def test_document_citations_separate_without_dropping_broken_relations():
    change = Change(
        operacion="crear",
        tipo="requisito_funcional",
        descripcion="Recuperar acceso",
        referencias=["Manual de acceso, p.2", "ACT-999"],
    )
    fixed = separate_document_sources(change)
    assert fixed.fuentes_documentales == ["Manual de acceso, p.2"]
    assert fixed.referencias == ["ACT-999"]
    assert validate_change(fixed, []) == ["Relaciones con elementos inexistentes: ACT-999"]
    assert separate_document_sources(fixed) == fixed


def test_pending_repair_keeps_sources_audit_and_requires_human_approval():
    async def scenario():
        async with environment() as (db, service, _, pid, rid, mid):
            change = Change(
                operacion="crear",
                tipo="requisito_funcional",
                descripcion="Empleado",
                referencias=["Manual de acceso, p.2"],
            )
            # Reproducir una propuesta guardada por la versión anterior.
            from uuid import uuid4

            from psycopg.types.json import Jsonb

            proposal_id = str(uuid4())
            await db.execute(
                "INSERT INTO proposals(id,project_id,execution_id,message_id,change,status,validation) "
                "VALUES(%s,%s,%s,%s,%s,'pendiente_aclaracion',%s)",
                (
                    proposal_id,
                    pid,
                    rid,
                    mid,
                    Jsonb(change.model_dump(mode="json")),
                    Jsonb(["Existen referencias a elementos inexistentes"]),
                ),
            )
            assert await service.repair_document_references(pid) == 1
            assert await service.repair_document_references(pid) == 0
            state = await service.state(pid)
            assert state["elementos"] == []
            assert state["propuestas"][0]["estado"] == "propuesto"
            assert state["propuestas"][0]["validacion"] == []
            audit = await db.one(
                "SELECT data FROM events WHERE execution_id=%s AND operation='reparar_fuentes'",
                (rid,),
            )
            assert audit["data"]["antes"]["referencias"] == ["Manual de acceso, p.2"]
            await service.review(pid, proposal_id, Review(accion="aprobar"))
            state = await service.state(pid)
            assert state["elementos"][0]["fuentes_documentales"] == ["Manual de acceso, p.2"]
            baseline = await service.publish(pid, True)
            assert baseline["requisitos"][0]["fuentes_documentales"] == ["Manual de acceso, p.2"]

    run(scenario())


def test_new_proposals_keep_document_sources_through_approval():
    async def scenario():
        async with environment() as (_, service, _, pid, rid, mid):
            change = Change(
                operacion="crear",
                tipo="requisito_funcional",
                descripcion="Empleado",
                referencias=["Manual de acceso, p.2"],
            )
            result = await service.propose(pid, rid, mid, Analysis(cambios=[change]))
            assert result[0]["estado"] == "propuesto"
            assert result[0]["cambio"]["referencias"] == []
            await service.review(pid, result[0]["id"], Review(accion="aprobar"))
            state = await service.state(pid)
            assert state["elementos"][0]["fuentes_documentales"] == ["Manual de acceso, p.2"]

    run(scenario())
