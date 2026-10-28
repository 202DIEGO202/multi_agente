from uuid import uuid4

from psycopg.types.json import Jsonb
from test_persistence import environment, run

from app.models.schemas import Analysis, Change, Review


def test_modification_keeps_target_type_before_presenting_proposal():
    async def scenario():
        async with environment("automatico") as (db, service, events, pid, rid, mid):
            await service.propose(
                pid,
                rid,
                mid,
                Analysis(
                    cambios=[
                        Change(
                            operacion="crear",
                            tipo="restriccion",
                            descripcion="Edad mayor a 23 años",
                        )
                    ]
                ),
            )
            await db.execute("UPDATE projects SET mode='supervisado' WHERE id=%s", (pid,))
            run_id = await events.create_run(pid, "revision")
            result = await service.propose(
                pid,
                run_id,
                mid,
                Analysis(
                    cambios=[
                        Change(
                            operacion="modificar",
                            id_elemento="RES-001",
                            tipo="requisito_funcional",
                            version_esperada=1,
                            descripcion="Validar edad mayor a 23 años desde la fecha de nacimiento",
                        )
                    ]
                ),
            )
            assert result[0]["cambio"]["tipo"] == "restriccion"
            assert not result[0]["validacion"]
            approved = await service.review(pid, result[0]["id"], Review(accion="aprobar"))
            assert approved["id_elemento"] == "RES-001"
            state = await service.state(pid)
            assert (
                state["elementos"][0]["tipo"] == "restriccion"
                and state["elementos"][0]["version"] == 2
            )
            assert await db.one(
                "SELECT id FROM events WHERE execution_id=%s AND operation='conservar_tipo'",
                (run_id,),
            )

    run(scenario())


def test_legacy_pending_type_repair_preserves_decision_and_audit():
    async def scenario():
        async with environment("automatico") as (db, service, events, pid, rid, mid):
            await service.propose(
                pid,
                rid,
                mid,
                Analysis(
                    cambios=[
                        Change(
                            operacion="crear", tipo="restriccion", descripcion="Bachillerato mínimo"
                        )
                    ]
                ),
            )
            await db.execute("UPDATE projects SET mode='supervisado' WHERE id=%s", (pid,))
            proposal = str(uuid4())
            value = Change(
                operacion="modificar",
                id_elemento="RES-001",
                tipo="requisito_funcional",
                version_esperada=1,
                descripcion="Validar bachillerato antes de enviar solicitud",
            ).model_dump(mode="json")
            await db.execute(
                "INSERT INTO proposals(id,project_id,execution_id,message_id,change,status,validation) VALUES(%s,%s,%s,%s,%s,'pendiente_aclaracion',%s)",
                (
                    proposal,
                    pid,
                    rid,
                    mid,
                    Jsonb(value),
                    Jsonb(["No se puede cambiar el tipo de un elemento existente"]),
                ),
            )
            assert await service.repair_pending_types(pid) == 1
            assert await service.repair_pending_types(pid) == 0
            state = await service.state(pid)
            repaired = next(p for p in state["propuestas"] if str(p["id"]) == proposal)
            assert repaired["estado"] == "propuesto" and repaired["cambio"]["tipo"] == "restriccion"
            assert state["elementos"][0]["version"] == 1  # No se aprueba durante la reparación.
            before = await db.one(
                "SELECT data FROM events WHERE execution_id=%s AND operation='reparar_tipo_propuesta'",
                (rid,),
            )
            assert before["data"]["antes"]["tipo"] == "requisito_funcional"
            assert before["data"]["despues"]["tipo"] == "restriccion"
            await service.review(pid, proposal, Review(accion="aprobar"))
            assert (await service.state(pid))["elementos"][0]["version"] == 2

    run(scenario())
