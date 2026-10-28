"""Adaptadores de inferencia remota. No cargan ni ejecutan modelos en el equipo."""

import asyncio
import json
import math
from collections.abc import AsyncIterator
from copy import deepcopy

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Settings


def strict_json_schema(schema):
    """Responses exige campos explícitos y objetos cerrados, incluidos los anidados."""
    result = deepcopy(schema)

    def visit(value):
        if isinstance(value, dict):
            value.pop("default", None)
            if "properties" in value:
                value["additionalProperties"] = False
                value["required"] = list(value["properties"])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(result)
    return result


def response_text(data):
    if data.get("status") not in {None, "completed"}:
        raise ProviderError("La API no completó la respuesta estructurada.")
    return "".join(
        part.get("text", "")
        for output in data.get("output", [])
        for part in output.get("content", [])
        if part.get("type") == "output_text"
    )


class ProviderError(RuntimeError):
    def __init__(self, message, validation_errors=None, status=None):
        super().__init__(message)
        self.validation_errors = validation_errors or []
        self.status = status


# Fallos transitorios del proveedor: se reintentan con espera creciente en lugar de abortar
# una ejecución larga. Los errores de cliente (400, 401, 403...) no se reintentan.
RETRY_STATUS = {408, 429, 500, 502, 503, 504}
RETRY_ATTEMPTS = 4
RETRY_BASE_SECONDS = 2.0
RETRY_MAX_SECONDS = 30.0


def retry_delay(attempt, response=None):
    if response is not None:
        header = response.headers.get("retry-after", "")
        if header.replace(".", "", 1).isdigit():
            return min(float(header), RETRY_MAX_SECONDS)
    return min(RETRY_BASE_SECONDS * 2**attempt, RETRY_MAX_SECONDS)


class Models:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=settings.llm_timeout)

    async def _post(self, url, body, headers):
        """POST con reintentos ante errores transitorios. Nunca reintenta errores del cliente."""
        for attempt in range(RETRY_ATTEMPTS):
            try:
                response = await self.client.post(url, json=body, headers=headers)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt + 1 >= RETRY_ATTEMPTS:
                    raise ProviderError(f"La API no respondió ({type(exc).__name__}).") from exc
                await asyncio.sleep(retry_delay(attempt))
                continue
            if response.status_code in RETRY_STATUS and attempt + 1 < RETRY_ATTEMPTS:
                await asyncio.sleep(retry_delay(attempt, response))
                continue
            if response.status_code >= 400:
                raise ProviderError(
                    f"La API respondió con el estado {response.status_code}.",
                    status=response.status_code,
                )
            return response
        raise ProviderError("La API no respondió tras varios intentos.")

    def _config(self, rewrite=False):
        s = self.settings
        if rewrite:
            return (
                s.rewrite_base_url or s.llm_base_url,
                s.rewrite_model or s.llm_model,
                s.rewrite_api_key if s.rewrite_api_key.get_secret_value() else s.llm_api_key,
            )
        return s.llm_base_url, s.llm_model, s.llm_api_key

    @staticmethod
    def _require(base, model):
        if not base or not model:
            raise ProviderError(
                "Configura la URL y el modelo de la API en .env antes de ejecutar IA."
            )

    @staticmethod
    def _headers(key, style="bearer"):
        value = key.get_secret_value()
        if not value:
            return {}
        return {"api-key": value} if style == "api-key" else {"Authorization": f"Bearer {value}"}

    async def json(
        self,
        messages: list[dict],
        schema: type[BaseModel],
        rewrite=False,
        max_tokens=None,
        max_attempts=2,
        usage: dict | None = None,
    ):
        """usage, si se entrega, acumula los tokens reales que informa la API."""
        if max_attempts not in (1, 2):
            raise ValueError("El límite de intentos debe ser 1 o 2")
        base, model, key = self._config(rewrite)
        self._require(base, model)
        style = (
            (self.settings.rewrite_api_style or self.settings.llm_api_style)
            if rewrite
            else self.settings.llm_api_style
        )
        # En "responses" el esquema viaja como formato estricto y la API lo impone; repetirlo como
        # texto solo añadía cientos o miles de tokens por llamada.
        messages = [*messages]
        if style != "responses":
            messages.append(
                {
                    "role": "system",
                    "content": "Devuelve exclusivamente JSON válido conforme a este esquema: "
                    + json.dumps(schema.model_json_schema(), ensure_ascii=False),
                }
            )
        body = {
            "model": model,
            "messages": messages,
            "stream": False,
            "temperature": 0,
            "max_tokens": max_tokens or self.settings.llm_max_tokens,
            "response_format": {"type": "json_object"},
        }
        auth = (
            (self.settings.rewrite_auth_style or self.settings.llm_auth_style)
            if rewrite
            else self.settings.llm_auth_style
        )
        path = "/chat/completions"
        if style == "responses":
            path = "/responses"
            body = {
                "model": model,
                "input": messages,
                "stream": False,
                "store": False,
                "temperature": 0,
                "max_output_tokens": max_tokens or self.settings.llm_max_tokens,
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": schema.__name__,
                        "strict": True,
                        "schema": strict_json_schema(schema.model_json_schema()),
                    }
                },
            }
        try:
            for attempt in range(max_attempts):
                response = await self._post(base.rstrip("/") + path, body, self._headers(key, auth))
                data = response.json()
                if usage is not None:
                    reported = data.get("usage") or {}
                    usage["entrada"] = usage.get("entrada", 0) + int(
                        reported.get("input_tokens", reported.get("prompt_tokens", 0)) or 0
                    )
                    usage["salida"] = usage.get("salida", 0) + int(
                        reported.get("output_tokens", reported.get("completion_tokens", 0)) or 0
                    )
                text = (
                    response_text(data)
                    if style == "responses"
                    else data["choices"][0]["message"]["content"]
                )
                try:
                    return schema.model_validate_json(text)
                except ValidationError as validation:
                    if attempt + 1 >= max_attempts:
                        raise
                    errors = validation.errors(
                        include_input=False, include_url=False, include_context=False
                    )
                    messages.extend(
                        [
                            {"role": "assistant", "content": text},
                            {
                                "role": "user",
                                "content": "Corrige el contrato anterior sin agregar información. "
                                "Errores: " + json.dumps(errors, ensure_ascii=False),
                            },
                        ]
                    )
        except ValidationError as exc:
            raise ProviderError(
                "El contrato del modelo no superó la validación Pydantic.",
                exc.errors(include_input=False, include_url=False, include_context=False),
            ) from exc
        except (httpx.HTTPError, KeyError, ValueError, IndexError, TypeError) as exc:
            raise ProviderError("La API no respondió con un contrato JSON válido.") from exc

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        base, model, key = self._config()
        self._require(base, model)
        body = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": self.settings.llm_temperature,
            "max_tokens": self.settings.llm_max_tokens,
        }
        responses = self.settings.llm_api_style == "responses"
        path = "/responses" if responses else "/chat/completions"
        if responses:
            body = {
                "model": model,
                "input": messages,
                "stream": True,
                "store": False,
                "temperature": self.settings.llm_temperature,
                "max_output_tokens": self.settings.llm_max_tokens,
            }
        completed = False
        try:
            async with self.client.stream(
                "POST",
                base.rstrip("/") + path,
                json=body,
                headers=self._headers(key, self.settings.llm_auth_style),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        completed = True
                        break
                    data = json.loads(payload)
                    if data.get("error"):
                        raise ProviderError("La API interrumpió la respuesta.")
                    if responses:
                        if data.get("type") in {"response.failed", "response.incomplete", "error"}:
                            raise ProviderError("La API no completó la respuesta.")
                        if data.get("type") == "response.completed":
                            completed = True
                        token = (
                            data.get("delta", "")
                            if data.get("type") == "response.output_text.delta"
                            else ""
                        )
                    else:
                        choices = data.get("choices", [])
                        token = choices[0].get("delta", {}).get("content", "") if choices else ""
                    if token:
                        yield token
                if not completed:
                    raise ProviderError("La conexión terminó antes de completar la respuesta.")
        except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
            raise ProviderError("No fue posible completar la respuesta de la API.") from exc

    async def embed(self, texts: list[str]) -> list[list[float]]:
        s = self.settings
        base = s.embedding_base_url or s.llm_base_url
        key = s.embedding_api_key if s.embedding_api_key.get_secret_value() else s.llm_api_key
        self._require(base, s.embedding_model)
        try:
            response = await self._post(
                base.rstrip("/") + "/embeddings",
                {"model": s.embedding_model, "input": texts},
                self._headers(key, s.embedding_auth_style or s.llm_auth_style),
            )
            data = response.json()
            vectors = [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]
            if len(vectors) != len(texts) or any(
                len(v) != s.embedding_dimensions
                or not all(math.isfinite(x) for x in v)
                or not any(v)
                for v in vectors
            ):
                raise ValueError("Embeddings incompatibles")
            return vectors
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ProviderError(
                "La API no devolvió embeddings con la dimensión configurada."
            ) from exc

    async def close(self):
        await self.client.aclose()
