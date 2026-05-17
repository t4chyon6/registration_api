import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import asyncpg
import pytest
from docker.errors import DockerException
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres_dsn() -> Iterator[str]:
    try:
        with PostgresContainer("postgres:17-bookworm") as postgres:
            dsn = postgres.get_connection_url().replace(
                "postgresql+psycopg2://",
                "postgresql://",
            )
            migration = Path("migrations/001_init.sql").read_text()
            asyncio.run(_apply_migration(dsn, migration))
            yield dsn
    except DockerException as exc:
        pytest.skip(f"Docker is not available for integration tests: {exc}")


@pytest.fixture
async def db_connection(postgres_dsn: str) -> AsyncIterator[asyncpg.Connection]:
    connection = await asyncpg.connect(postgres_dsn)
    transaction = connection.transaction()
    await transaction.start()
    try:
        yield connection
    finally:
        await transaction.rollback()
        await connection.close()


async def _apply_migration(dsn: str, migration: str) -> None:
    connection = await asyncpg.connect(dsn)
    try:
        await connection.execute(migration)
    finally:
        await connection.close()
