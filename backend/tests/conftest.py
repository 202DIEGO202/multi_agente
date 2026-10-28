import asyncio
import sys


def pytest_asyncio_loop_factories(config, item):
    factory = asyncio.SelectorEventLoop if sys.platform == "win32" else asyncio.new_event_loop
    return {"compatible": factory}
