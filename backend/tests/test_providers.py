import json

import httpx
from test_persistence import run

from app.config import Settings
from app.models.schemas import Interpretation
from app.providers import Models


def test_compatible_provider_contract_stream_and_embedding_order():
    async def scenario():
        settings = Settings(
            llm_provider="openai_compatible",
            llm_api_style="chat_completions",
            llm_auth_style="bearer",
            llm_base_url="https://proveedor.invalid/v1",
            llm_model="modelo-configurado",
            llm_api_key="clave-solo-de-prueba",
            embedding_provider="openai_compatible",
            embedding_base_url="https://proveedor.invalid/v1",
            embedding_model="embeddings-de-prueba",
            embedding_dimensions=2,
        )
        models = Models(settings)
        await models.client.aclose()
        observed = []

        def respond(request):
            body = json.loads(request.content)
            observed.append((request.url.path, body))
            if request.url.path.endswith("/embeddings"):
                return httpx.Response(
                    200,
                    json={
                        "data": [
                            {"index": 1, "embedding": [0.0, 1.0]},
                            {"index": 0, "embedding": [1.0, 0.0]},
                        ]
                    },
                )
            assert request.headers["Authorization"] == "Bearer clave-solo-de-prueba"
            if body["stream"]:
                return httpx.Response(
                    200, text='data: {"choices":[{"delta":{"content":"Hola"}}]}\n\ndata: [DONE]\n\n'
                )
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {"consultar_conocimiento": False, "actualizar_estado": False}
                                )
                            }
                        }
                    ]
                },
            )

        models.client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        try:
            result = await models.json([{"role": "user", "content": "Hola"}], Interpretation)
            assert result.actualizar_estado is False
            text = "".join(
                [token async for token in models.stream([{"role": "user", "content": "Hola"}])]
            )
            assert text == "Hola"
            assert await models.embed(["a", "b"]) == [[1.0, 0.0], [0.0, 1.0]]
            assert observed[0][1]["model"] == "modelo-configurado"
        finally:
            await models.close()

    run(scenario())


def test_responses_api_uses_strict_json_and_visible_text_events():
    async def scenario():
        settings = Settings(
            llm_base_url="https://azure.invalid/openai/v1",
            llm_model="implementacion-prueba",
            llm_api_style="responses",
            llm_auth_style="api-key",
            llm_api_key="clave-ficticia",
        )
        models = Models(settings)
        await models.client.aclose()

        def respond(request):
            assert request.headers["api-key"] == "clave-ficticia"
            assert request.url.path == "/openai/v1/responses"
            body = json.loads(request.content)
            assert body["store"] is False
            if body["stream"]:
                return httpx.Response(
                    200,
                    text='data: {"type":"response.output_text.delta","delta":"Visible"}\n\n'
                    'data: {"type":"response.completed"}\n\n',
                )
            schema = body["text"]["format"]["schema"]
            assert schema["additionalProperties"] is False
            assert set(schema["required"]) == set(schema["properties"])
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": '{"consultar_conocimiento":false,"actualizar_estado":true}',
                                }
                            ],
                        }
                    ],
                },
            )

        models.client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        try:
            result = await models.json([{"role": "user", "content": "Requisito"}], Interpretation)
            assert result.actualizar_estado is True
            assert (
                "".join([x async for x in models.stream([{"role": "user", "content": "Hola"}])])
                == "Visible"
            )
        finally:
            await models.close()

    run(scenario())


def responses_settings():
    return Settings(
        llm_base_url="https://azure.invalid/openai/v1",
        llm_model="implementacion-prueba",
        llm_api_style="responses",
        llm_auth_style="api-key",
        llm_api_key="clave-ficticia",
    )


def completed(text):
    return httpx.Response(
        200,
        json={
            "status": "completed",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
    )


def test_transient_errors_are_retried_and_schema_is_sent_only_once(monkeypatch):
    import app.providers as providers

    async def no_wait(_):
        return None

    monkeypatch.setattr(providers.asyncio, "sleep", no_wait)
    calls = []

    async def scenario():
        models = Models(responses_settings())
        await models.client.aclose()

        def respond(request):
            body = json.loads(request.content)
            calls.append(body)
            if len(calls) < 3:
                return httpx.Response(429 if len(calls) == 1 else 503, headers={"retry-after": "1"})
            return completed('{"consultar_conocimiento":false,"actualizar_estado":true}')

        models.client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        try:
            usage = {}
            result = await models.json(
                [{"role": "user", "content": "Requisito"}], Interpretation, usage=usage
            )
            assert result.actualizar_estado is True and usage == {"entrada": 10, "salida": 5}
        finally:
            await models.close()

    run(scenario())
    assert len(calls) == 3
    # En modo responses el esquema va solo en text.format: no se repite como mensaje.
    assert not any("esquema" in str(m.get("content", "")) for m in calls[-1]["input"])


def test_client_errors_are_not_retried(monkeypatch):
    import app.providers as providers

    async def no_wait(_):
        return None

    monkeypatch.setattr(providers.asyncio, "sleep", no_wait)
    calls = []

    async def scenario():
        models = Models(responses_settings())
        await models.client.aclose()

        def respond(request):
            calls.append(1)
            return httpx.Response(400, json={"error": "bad request"})

        models.client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        try:
            await models.json([{"role": "user", "content": "x"}], Interpretation)
        except providers.ProviderError as exc:
            assert exc.status == 400
        else:
            raise AssertionError("Debía fallar")
        finally:
            await models.close()

    run(scenario())
    assert calls == [1]


def test_chat_completions_still_receives_the_schema_as_text():
    calls = []

    async def scenario():
        models = Models(
            Settings(
                llm_base_url="https://api.invalid/v1",
                llm_model="m",
                llm_api_style="chat_completions",
            )
        )
        await models.client.aclose()

        def respond(request):
            calls.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": '{"consultar_conocimiento":true,"actualizar_estado":false}'
                            }
                        }
                    ]
                },
            )

        models.client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        try:
            await models.json([{"role": "user", "content": "x"}], Interpretation)
        finally:
            await models.close()

    run(scenario())
    assert any("esquema" in m["content"] for m in calls[0]["messages"] if m["role"] == "system")
