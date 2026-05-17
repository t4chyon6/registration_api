from registration import config
from registration.infrastructure import database


class _FakePool:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def _settings() -> config.Settings:
    return config.Settings(
        database_url="postgresql://user:password@localhost:5432/registration_api",
        database_pool_min_size=1,
        database_pool_max_size=2,
        email_service_url="http://email-service.local",
    )


async def test_create_pool_uses_configured_database_settings(monkeypatch) -> None:
    calls = {}
    fake_pool = _FakePool()

    async def fake_create_pool(**kwargs):
        calls.update(kwargs)
        return fake_pool

    monkeypatch.setattr(database.asyncpg, "create_pool", fake_create_pool)

    pool = await database.create_pool(_settings())

    assert pool is fake_pool
    assert calls == {
        "dsn": "postgresql://user:password@localhost:5432/registration_api",
        "min_size": 1,
        "max_size": 2,
    }


async def test_lifespan_pool_closes_created_pool(monkeypatch) -> None:
    fake_pool = _FakePool()

    async def fake_create_pool(settings: config.Settings):
        assert settings == _settings()
        return fake_pool

    monkeypatch.setattr(database, "create_pool", fake_create_pool)

    async with database.lifespan_pool(_settings()) as pool:
        assert pool is fake_pool
        assert not fake_pool.closed

    assert fake_pool.closed
