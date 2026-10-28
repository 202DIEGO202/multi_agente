from uuid import uuid4

import numpy as np
import pytest
from test_persistence import environment, run

from app.agents.functional_analyst import FunctionalAnalyst
from app.models.schemas import Extraction, Interpretation, ProcedureReview, Review
from app.services.procedure_guard import procedure_guard


def fragment():
    return {
        "id_fragmento": "fragmento-ad",
        "id_documento": "documento-ad",
        "documento": "Guía de gestión de usuarios en Active Directory.pdf",
        "pagina": 1,
        "version_documento": 1,
        "contenido": "La creación de usuarios requiere la aprobación del líder de área. El Administrador de AD ejecuta el alta.",
    }


def revision(estado="requiere_aclaracion"):
    return ProcedureReview.model_validate(
        {
            "estado": estado,
            "motivo": "Debe aclararse si el autorregistro es solo en el portal o crea la cuenta corporativa sin aprobación.",
            "fuentes": [
                {
                    "id_fragmento": "fragmento-ad",
                    "cita": "La creación de usuarios requiere la aprobación del líder de área.",
                }
            ],
        }
    )


def test_approval_policy_requires_clarification_and_real_sources():
    conflicts, questions, report = procedure_guard(revision(), [fragment()], True)
    assert conflicts and questions
    assert report["fuentes_verificadas"][0]["pagina"] == 1
    assert "Guía de gestión" in conflicts[0]
    invalid = revision("compatible")
    invalid.fuentes[0].cita = "La aprobación es opcional"
    assert not procedure_guard(invalid, [fragment()], True)[0]
    assert procedure_guard(invalid, [fragment()], True)[2]["estado"] == "requiere_revision"
    assert procedure_guard(None, [fragment()], True)[2]["estado"] == "requiere_revision"
    assert not procedure_guard(revision("compatible"), [fragment()], True)[0]
    assert not procedure_guard(None, [], False)[0]
    assert procedure_guard(None, [], True)[2]["estado"] == "sin_evidencia"
    assert not procedure_guard(
        ProcedureReview(estado="no_aplica", motivo="El cambio afecta solo los colores"),
        [fragment()],
        True,
    )[0]


@pytest.mark.parametrize("mode", ["supervisado", "automatico"])
def test_followup_retains_policy_and_cannot_consolidate_contradictory_request(mode):
    async def scenario():
        async with environment(mode) as (db, projects, events, pid, oldrun, oldmid):
            cid = (await db.one("SELECT conversation_id FROM messages WHERE id=%s", (oldmid,)))[
                "conversation_id"
            ]
            did, fid = str(uuid4()), str(uuid4())
            f = fragment()
            f.update(id_documento=did, id_fragmento=fid)
            await db.execute(
                "INSERT INTO documents(id,project_id,name,media_type,category,content_hash,status,embedding_signature,storage_path) VALUES(%s,%s,%s,'application/pdf','IT','hash','indexado','test','test')",
                (did, pid, f["documento"]),
            )
            await db.execute(
                "INSERT INTO chunks(id,document_id,page,position,content,embedding) VALUES(%s,%s,1,0,%s,%s)",
                (fid, did, f["contenido"], np.array([1.0, 0.0], dtype=np.float32)),
            )
            await events.emit(
                oldrun, "rag", "resultado", "completado", "Evidencia previa", {"seleccionados": [f]}
            )
            await events.status(oldrun, "completado")
            rid = await events.create_run(pid, "chat", conversation_id=cid)
            mid = str(uuid4())
            message = "Crear directamente el usuario. Datos: cédula, nombres, teléfono y correo."
            await db.execute(
                "INSERT INTO messages(id,conversation_id,execution_id,role,content) VALUES(%s,%s,%s,'user',%s)",
                (mid, cid, rid, message),
            )

            class Models:
                async def json(self, messages, schema, **kwargs):
                    if schema is Interpretation:
                        return Interpretation(consultar_conocimiento=False, actualizar_estado=True)
                    assert schema is Extraction
                    assert fid in messages[-1]["content"]
                    return Extraction.model_validate(
                        {
                            "revision_procedimientos": {
                                "estado": "requiere_aclaracion",
                                "motivo": "¿El autorregistro crea una cuenta del portal o una cuenta AD sin aprobación?",
                                "fuentes": [
                                    {
                                        "id_fragmento": fid,
                                        "cita": "La creación de usuarios requiere la aprobación del líder de área.",
                                    }
                                ],
                            },
                            "cambios": [
                                {
                                    "operacion": "crear",
                                    "tipo": "requisito_funcional",
                                    "descripcion": "El empleado crea directamente su usuario",
                                }
                            ],
                        }
                    )

            analyst = FunctionalAnalyst(db, Models(), None, projects, events, None)
            state = {
                "project_id": pid,
                "conversation_id": str(cid),
                "execution_id": rid,
                "message_id": mid,
                "message": message,
            }
            state.update(await analyst.load(state))
            assert state["procedure_evidence"][0]["id_fragmento"] == fid
            state.update(await analyst.interpret(state))
            assert not state["interpretation"][
                "consultar_conocimiento"
            ]  # Reutiliza evidencia vigente sin otro RAG.
            state.update(await analyst.analyze(state))
            await analyst.consolidate(state)
            result = await projects.state(pid)
            assert not result["elementos"]
            assert result["contradicciones"]
            proposal = next(
                p for p in result["propuestas"] if p["cambio"]["tipo"] == "requisito_funcional"
            )
            assert proposal["estado"] == "pendiente_aclaracion"
            with pytest.raises(ValueError):
                await projects.review(pid, proposal["id"], Review(accion="aprobar"))
            with pytest.raises(ValueError):
                await projects.publish(pid, True)
            # Una aclaración cierra todas las dudas del mismo análisis y reemplaza sus propuestas
            # bloqueadas por un nuevo análisis; nunca las aprueba con texto libre.
            outcome = await projects.resolve_conflict(
                pid, result["contradicciones"][0]["id"], "Revisar el alcance del autorregistro"
            )
            assert outcome["contradicciones_resueltas"] == len(result["contradicciones"])
            assert outcome["propuestas_reemplazadas"] >= 1
            assert "Revisar el alcance del autorregistro" in outcome["reanalisis"]["mensaje"]
            assert outcome["reanalisis"]["id_conversacion"] == str(cid)
            after = await projects.state(pid)
            assert all(c["fecha_resolucion"] for c in after["contradicciones"])
            assert not [p for p in after["propuestas"] if p["estado"] == "pendiente_aclaracion"]
            with pytest.raises(ValueError, match="ya fue revisada"):
                await projects.review(pid, proposal["id"], Review(accion="aprobar"))

    run(scenario())


def test_bad_citation_is_repaired_once_without_creating_business_conflict():
    from app.services.procedure_guard import review_with_citation_repair

    class Events:
        async def emit(self, *args):
            pass

    class Models:
        calls = 0

        async def json(self, messages, schema, **kwargs):
            self.calls += 1
            assert kwargs["max_attempts"] == 1
            return revision("compatible")

    async def scenario():
        bad = revision("compatible")
        bad.fuentes[0].id_fragmento = "id-documento-en-lugar-de-fragmento"
        models = Models()
        conflicts, questions, report = await review_with_citation_repair(
            models,
            Events(),
            "run",
            "Aclarar datos",
            [{"descripcion": "Una aclaración"}],
            [fragment()],
            bad,
        )
        assert models.calls == 1
        assert conflicts == [] and questions == [] and report["estado"] == "compatible"

    run(scenario())


def test_unverifiable_citation_remains_technical_not_a_human_contradiction():
    from app.services.procedure_guard import review_with_citation_repair

    class Events:
        async def emit(self, *args):
            pass

    class Models:
        calls = 0

        async def json(self, messages, schema, **kwargs):
            self.calls += 1
            value = revision("compatible")
            value.fuentes[0].cita = "Texto inventado"
            return value

    async def scenario():
        models = Models()
        conflicts, questions, report = await review_with_citation_repair(
            models, Events(), "run", "Solicitud", [{"descripcion": "Cambio"}], [fragment()], None
        )
        assert models.calls == 1
        assert conflicts == [] and questions == []
        assert report["estado"] == "requiere_revision"

    run(scenario())


def test_one_bad_citation_does_not_discard_verified_ones():
    review = revision("compatible")
    review.fuentes.append(
        review.fuentes[0].model_copy(update={"cita": "Texto parafraseado que no existe"})
    )
    conflicts, questions, report = procedure_guard(review, [fragment()], True)
    assert report["estado"] == "compatible"
    assert len(report["fuentes_verificadas"]) == 1 and report["citas_descartadas"]


def test_long_citation_tolerates_minor_wording_changes():
    review = revision("compatible")
    review.fuentes[
        0
    ].cita = "La creacion de los usuarios requiere la aprobacion del lider de area. El Administrador de AD ejecuta el alta."
    assert procedure_guard(review, [fragment()], True)[2]["estado"] == "compatible"


def test_analyst_parameters_need_no_document():
    review = ProcedureReview(
        estado="decision_analista",
        motivo="Lista de niveles de estudio y textos de error definidos por el analista",
    )
    conflicts, questions, report = procedure_guard(review, [fragment()], True)
    assert conflicts == [] and questions == [] and report["estado"] == "decision_analista"
