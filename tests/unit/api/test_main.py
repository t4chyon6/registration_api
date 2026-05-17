import importlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import ModuleType

import pytest
from fastapi import FastAPI

from tests.unit.services import fakes


@pytest.fixture
def main_module(monkeypatch) -> ModuleType:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:password@localhost:5432/registration_api",
    )
    monkeypatch.setenv("EMAIL_SERVICE_URL", "http://email-service.local")

    config_module = importlib.import_module("registration.config")
    config_module.get_settings.cache_clear()
    loaded_main = importlib.import_module("registration.main")
    return importlib.reload(loaded_main)


async def test_lifespan_sets_and_closes_process_resources(
    main_module: ModuleType,
    monkeypatch,
) -> None:
    settings = fakes.settings()
    pool = object()
    events: list[str] = []

    @asynccontextmanager
    async def fake_lifespan_pool(received_settings) -> AsyncIterator[object]:
        assert received_settings is settings
        events.append("pool_entered")
        try:
            yield pool
        finally:
            events.append("pool_closed")

    class FakeEmailService:
        def __init__(self, received_settings) -> None:
            assert received_settings is settings

        async def __aenter__(self):
            events.append("email_entered")
            return self

        async def __aexit__(self, _exc_type, _exc, _traceback) -> None:
            events.append("email_closed")

    monkeypatch.setattr(main_module.config, "get_settings", lambda: settings)
    monkeypatch.setattr(main_module.database, "lifespan_pool", fake_lifespan_pool)
    monkeypatch.setattr(main_module.email, "EmailService", FakeEmailService)

    app = FastAPI()

    async with main_module.lifespan(app):
        assert app.state.settings is settings
        assert app.state.pool is pool
        assert isinstance(app.state.email_service, FakeEmailService)

    assert events == [
        "pool_entered",
        "email_entered",
        "email_closed",
        "pool_closed",
    ]


def test_create_app_registers_user_routes_and_exception_handlers(
    main_module: ModuleType,
    monkeypatch,
) -> None:
    monkeypatch.setattr(main_module.config, "get_settings", fakes.settings)

    app = main_module.create_app()

    route_paths = {route.path for route in app.routes}
    assert "/v1/users" in route_paths
    assert "/v1/users/{user_id}/activation-code" in route_paths
    assert "/v1/users/{user_id}/activate" in route_paths
    assert app.exception_handlers
