"""Punto de entrada compatible con psycopg asíncrono en Windows."""

import asyncio
import sys

import uvicorn

from app.config import get_settings

if __name__ == "__main__":
    factory = asyncio.SelectorEventLoop if sys.platform == "win32" else asyncio.new_event_loop
    settings = get_settings()
    server = uvicorn.Server(
        uvicorn.Config(
            "app.main:app",
            host=settings.api_host,
            port=settings.api_port,
            access_log=False,
        )
    )
    with asyncio.Runner(loop_factory=factory) as runner:
        runner.run(server.serve())
