from pathlib import Path

from pgvector.psycopg import register_vector_async
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


class Database:
    def __init__(self, url: str):
        self.url = url
        self.pool = AsyncConnectionPool(
            url,
            min_size=1,
            max_size=12,
            open=False,
            kwargs={"autocommit": True, "row_factory": dict_row, "prepare_threshold": 0},
            configure=register_vector_async,
        )

    async def open(self):
        async with await AsyncConnection.connect(self.url, autocommit=True) as conn:
            await conn.execute(Path(__file__).with_name("schema.sql").read_text("utf-8"))
        await self.pool.open(wait=True)

    async def close(self):
        await self.pool.close()

    async def fetch(self, query: str, params=()):
        async with self.pool.connection() as conn:
            return await (await conn.execute(query, params)).fetchall()

    async def one(self, query: str, params=()):
        rows = await self.fetch(query, params)
        return rows[0] if rows else None

    async def execute(self, query: str, params=()):
        async with self.pool.connection() as conn:
            await conn.execute(query, params)
