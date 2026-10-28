"""Verificación breve y explícita de la API configurada. Consume unos pocos tokens."""

import asyncio
import json
from pathlib import Path

from app.config import Settings
from app.models.schemas import Interpretation
from app.providers import Models


async def check():
    models = Models(Settings())
    try:
        contract = await models.json(
            [
                {
                    "role": "user",
                    "content": "Hola. Solo estoy saludando; no solicito cambios funcionales ni documentación.",
                }
            ],
            Interpretation,
        )
        chunks = [
            token
            async for token in models.stream(
                [{"role": "user", "content": "Responde únicamente: Conexión Azure correcta."}]
            )
        ]
        report = {
            "modelo": models.settings.llm_model,
            "api": models.settings.llm_api_style,
            "contrato": contract.model_dump(),
            "streaming": "".join(chunks),
        }
        print(json.dumps(report, ensure_ascii=False))
        output = Path(__file__).resolve().parents[2] / "output"
        output.mkdir(exist_ok=True)
        (output / "verificacion_api.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), "utf-8"
        )
    finally:
        await models.close()


if __name__ == "__main__":
    asyncio.run(check())
