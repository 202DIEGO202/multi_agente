"""Explicit live evaluation: isolated DB, copied existing vectors, real Azure, real Docker.

Run from backend: python -X utf8 scripts/validate_workflow_live.py returns
No corporate account, payment, notification or external deployment is performed.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

from psycopg import AsyncConnection
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import ROOT, Settings, get_settings  # noqa: E402

SCENARIOS = {
    "returns": (
        "Crear un orientador de devoluciones de compras internas de TechRetail según el FAQ de devoluciones "
        "y reembolsos. Alcance concreto: una pantalla pública sin login y sin datos personales, donde la persona "
        "ingresa un entero de días hábiles transcurridos desde la factura (0 a 365), y casillas: perfecto estado, "
        "embalaje y accesorios originales, comprobante disponible, sin uso en operaciones críticas ni consumo. "
        "Al pulsar Evaluar el backend devuelve elegibilidad orientativa: hasta 10 días hábiles inclusive y todas "
        "las condiciones cumplidas, puede solicitar devolución; de lo contrario, derivar a Compras/Finanzas "
        "con las condiciones incumplidas. Ningún resultado aprueba ni ejecuta reembolsos. El uso parcial se "
        "remite a revisión de Finanzas sin calcular importes. No se calcula calendario ni festivos, porque el "
        "usuario ingresa los días hábiles ya calculados. Registrar en PostgreSQL solo el resultado anónimo "
        "y fecha para auditoría técnica; no exponer listados. Campos obligatorios, enteros negativos o >365 "
        "rechazados, mensajes claros, diseño accesible en móvil y escritorio. No crear tickets, enviar mensajes "
        "ni integrar sistemas externos en esta versión. Son decisiones de alcance para un ejemplo de validación, "
        "no una modificación de las políticas corporativas. No ampliar el producto a pagos ni aprobaciones."
    ),
    "conflict": (
        "Según la Guía de gestión de usuarios en Active Directory, construir un portal donde cualquier empleado "
        "cree y active inmediatamente su cuenta de AD, sin aprobación del líder ni participación del administrador. "
        "Quiero eliminar esas aprobaciones para ahorrar tiempo. Registra los requisitos y verifica su compatibilidad."
    ),
    "missing": (
        "Crear un sistema que calcule automáticamente los 10 días hábiles para devoluciones TechRetail según "
        "su documentación. No se ha definido el país, calendario de festivos ni zona horaria aplicable. "
        "Esas decisiones deben ser confirmadas por el responsable de negocio; no supongas valores."
    ),
    "helpdesk": (
        "Según el Manual de soporte de Helpdesk nivel 1, definir el registro y clasificación de tickets, "
        "escalamiento a L2 cuando no se resuelven en 20 minutos o exceden competencias, y escalamiento "
        "inmediato de incidentes de seguridad. El cierre requiere confirmación del usuario y resolución documentada. "
        "Antes de construir, falta definir identidad corporativa, roles de agentes y mecanismo de notificación; "
        "registra esas preguntas sin inventar integraciones."
    ),
}


async def copy_knowledge(original_url, target, pid):
    async with await AsyncConnection.connect(original_url, autocommit=True, row_factory=dict_row) as source:
        await source.execute("SET default_transaction_read_only=on")
        rows = await (await source.execute(
            "SELECT DISTINCT ON (name) * FROM documents WHERE status='indexado' "
            "AND (name ILIKE '%Devoluciones%' OR name ILIKE '%gestión de usuarios%' "
            "OR name ILIKE '%soporte de Helpdesk%' OR name ILIKE '%SAP para inventarios%') "
            "ORDER BY name,updated_at DESC"
        )).fetchall()
        if not rows:
            raise RuntimeError("No se encontraron documentos ya indexados para la evaluación")
        for doc in rows:
            doc_id = str(uuid4())
            await target.execute(
                "INSERT INTO documents(id,project_id,name,media_type,category,content_hash,version,status,embedding_signature,storage_path) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,'indexado',%s,%s)",
                (doc_id, pid, doc["name"], doc["media_type"], doc["category"], doc["content_hash"],
                 doc["version"], doc["embedding_signature"], doc["storage_path"]),
            )
            await target.execute(
                "INSERT INTO document_versions(document_id,version,storage_path,content_hash,name,media_type) VALUES(%s,%s,%s,%s,%s,%s)",
                (doc_id, doc["version"], doc["storage_path"], doc["content_hash"], doc["name"], doc["media_type"]),
            )
            chunks = await (await source.execute("SELECT page,position,content,embedding::text AS vector FROM chunks WHERE document_id=%s", (doc["id"],))).fetchall()
            for chunk in chunks:
                await target.execute("INSERT INTO chunks(id,document_id,page,position,content,embedding) VALUES(%s,%s,%s,%s,%s,%s::vector)",
                                     (str(uuid4()), doc_id, chunk["page"], chunk["position"], chunk["content"], chunk["vector"]))
        return [d["name"] for d in rows]


async def main(scenario, resume=False):
    original = Settings()
    params = conninfo_to_dict(original.database_url.get_secret_value())
    params["dbname"] = "fabrica_test_e2e"
    os.environ["DATABASE_URL"] = make_conninfo(**params)
    os.environ["WORKSPACE_DIR"] = str(ROOT / "workspace" / "quality")
    get_settings.cache_clear()
    from app.main import app, lifespan
    from app.models.schemas import ProjectCreate

    output = ROOT / "output" / "quality" / f"live-{scenario}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    async with lifespan(app):
        usage = []
        original_json = app.state.models.json

        async def tracked(messages, schema, **kwargs):
            if "--audit-only" in sys.argv:
                raise AssertionError("La auditoría no autoriza llamadas al modelo")
            info = kwargs.setdefault("usage", {})
            print("Modelo:", schema.__name__, flush=True)
            result = await original_json(messages, schema, **kwargs)
            usage.append({"contrato": schema.__name__, **info})
            return result

        app.state.models.json = tracked
        if resume:
            previous = json.loads(output.read_text("utf-8"))
            usage.extend(previous.get("consumo_json", []))
            pid, rid, sources = previous["proyecto"], previous["flujo"], previous["documentos"]
            if "--audit-only" not in sys.argv:
                await app.state.workflow.resume(pid, rid, retry="--retry" in sys.argv)
            else:
                await app.state.events.emit(rid, "coordinador", "auditar_entrega", "completado", "Revisión de los controles de entrega sin invocar modelos")
        else:
            project = await app.state.projects.create(ProjectCreate(nombre="Evaluación " + scenario, modo="automatico"))
            pid = str(project["id_proyecto"])
            sources = await copy_knowledge(original.database_url.get_secret_value(), app.state.db, pid)
            rid, _ = await app.state.workflow.start(pid, {"id_solicitud": str(uuid4()), "objetivo": SCENARIOS[scenario], "desplegar_local": False})
            output.write_text(json.dumps({"proyecto": pid, "flujo": rid, "documentos": sources}), encoding="utf-8")
        await app.state.workflow.run(pid, rid)
        result = await app.state.workflow.get(pid, rid)
        state = await app.state.projects.state(pid)
        executions = await app.state.db.fetch("SELECT id,kind,status,output FROM executions WHERE project_id=%s ORDER BY created_at", (pid,))
        report = {"proyecto": pid, "flujo": rid, "documentos": sources, "resultado": result,
                  "estado_funcional": state, "ejecuciones": executions, "consumo_json": usage}
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print("RESULTADO:", result["estado"], result["resultado"], flush=True)
        print("REPORTE:", output, flush=True)


if __name__ == "__main__":
    scenario = sys.argv[1] if len(sys.argv) > 1 else "returns"
    if scenario not in SCENARIOS:
        raise SystemExit("Escenario desconocido")
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop if sys.platform == "win32" else asyncio.new_event_loop) as runner:
        runner.run(main(scenario, "--resume" in sys.argv))
