"""Carga el corpus entregado por medio de la API real (no inserta resultados simulados)."""

import json
import os
import time
from pathlib import Path
from uuid import uuid4

import httpx


def main():
    headers = (
        {"Authorization": f"Bearer {os.environ['API_TOKEN']}"} if os.getenv("API_TOKEN") else {}
    )
    with httpx.Client(base_url="http://127.0.0.1:8000/api", timeout=30, headers=headers) as api:
        projects = api.get("/projects").raise_for_status().json()
        project = next((p for p in projects if p["nombre"] == "TechRetail"), None)
        if project is None:
            project = (
                api.post(
                    "/projects",
                    json={
                        "nombre": "TechRetail",
                        "descripcion": "Descubrimiento funcional con políticas, manuales y FAQ de TechRetail.",
                        "modo": "supervisado",
                    },
                )
                .raise_for_status()
                .json()
            )
        base = f"/projects/{project['id_proyecto']}"
        run = api.post(base + "/knowledge/import").raise_for_status().json()
        print(f"Proyecto {project['id_proyecto']} · {run['documentos']} documentos", flush=True)
        while True:
            result = api.get(base + f"/executions/{run['id_ejecucion']}").raise_for_status().json()
            if result["estado"] not in {"pendiente", "ejecutando"}:
                break
            time.sleep(2)
        print(
            json.dumps(
                {"estado": result["estado"], "resultado": result["resultado"]}, ensure_ascii=False
            ),
            flush=True,
        )
        docs = api.get(base + "/documents").raise_for_status().json()
        print(
            f"Documentos: {len(docs)} · Fragmentos: {sum(d['fragmentos'] for d in docs)}",
            flush=True,
        )
        query = (
            api.post(
                base + "/knowledge/search",
                json={
                    "contenido": "¿Cómo restablecer mi contraseña corporativa?",
                    "id_solicitud": str(uuid4()),
                },
            )
            .raise_for_status()
            .json()
        )
        while True:
            rag = api.get(base + f"/executions/{query['id_ejecucion']}").raise_for_status().json()
            if rag["estado"] not in {"pendiente", "ejecutando"}:
                break
            time.sleep(2)
        summary = {
            "id_proyecto": project["id_proyecto"],
            "ingesta": result,
            "documentos": len(docs),
            "fragmentos": sum(d["fragmentos"] for d in docs),
            "rag": rag,
        }
        output = Path(__file__).resolve().parents[2] / "output"
        output.mkdir(exist_ok=True)
        (output / "verificacion_real.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), "utf-8"
        )
        print(f"RAG: {rag['estado']}", flush=True)
        if rag["estado"] == "completado":
            print("Degradaciones:", rag["resultado"].get("degradaciones"), flush=True)
            for source in rag["resultado"]["seleccionados"]:
                print(source["documento"], "p.", source["pagina"], flush=True)
        if result["estado"] != "completado" or rag["estado"] != "completado":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
