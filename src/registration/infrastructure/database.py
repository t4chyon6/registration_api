"""PostgreSQL connection-pool helpers."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from registration import config


async def create_pool(settings: config.Settings) -> asyncpg.Pool:
    """Create an asyncpg connection pool from application settings."""
    return await asyncpg.create_pool(
        dsn=settings.database_dsn,
        min_size=settings.database_pool_min_size,
        max_size=settings.database_pool_max_size,
    )


@asynccontextmanager
async def lifespan_pool(settings: config.Settings) -> AsyncIterator[asyncpg.Pool]:
    """Yield an asyncpg pool and close it when the lifespan exits."""
    pool = await create_pool(settings)
    try:
        yield pool
    finally:
        await pool.close()
