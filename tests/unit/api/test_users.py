from base64 import b64encode
from datetime import timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI

from registration.api import dependencies
from registration.api.exception_handlers import register_exception_handlers
from registration.api.routes import users
from registration.domain import exceptions, models
from tests.unit.services import fakes


def _user(*, is_active: bool = False) -> models.User:
    return fakes.user(
        user_id=UUID("11111111-1111-1111-1111-111111111111"),
        is_active=is_active,
    )


def _basic_auth(username: str = "user@example.com", password: str = "secret") -> str:
    token = b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


class _RegistrationService:
    def __init__(
        self,
        *,
        returned_user: models.User | None = None,
        raised: Exception | None = None,
    ) -> None:
        self.returned_user = returned_user or _user()
        self.raised = raised
        self.calls: list[tuple[str, str]] = []

    async def register_user(self, *, email: str, password: str) -> models.User:
        self.calls.append((email, password))
        if self.raised is not None:
            raise self.raised
        return self.returned_user


class _ResendActivationCodeService:
    def __init__(self, raised: Exception | None = None) -> None:
        self.raised = raised
        self.calls: list[tuple[UUID, str, str]] = []

    async def resend_activation_code(
        self,
        *,
        user_id: UUID,
        email: str,
        password: str,
    ) -> None:
        self.calls.append((user_id, email, password))
        if self.raised is not None:
            raise self.raised


class _ActivationService:
    def __init__(
        self,
        *,
        returned_user: models.User | None = None,
        raised: Exception | None = None,
    ) -> None:
        self.returned_user = returned_user or _user(is_active=True)
        self.raised = raised
        self.calls: list[tuple[UUID, str, str, str]] = []

    async def activate_user(
        self,
        *,
        user_id: UUID,
        email: str,
        password: str,
        code: str,
    ) -> models.User:
        self.calls.append((user_id, email, password, code))
        if self.raised is not None:
            raise self.raised
        return self.returned_user


@pytest.fixture
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(users.router)
    register_exception_handlers(test_app)
    return test_app


@pytest.fixture
async def client(app: FastAPI):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as http_client:
        yield http_client


async def test_register_user_returns_created_user(
    app: FastAPI,
    client: httpx.AsyncClient,
) -> None:
    service = _RegistrationService()
    app.dependency_overrides[dependencies.get_registration_service] = lambda: service

    response = await client.post(
        "/v1/users",
        json={"email": "user@example.com", "password": "password123"},
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "user@example.com",
        "status": "pending",
        "created_at": "2026-05-17T10:15:00Z",
        "activated_at": None,
    }
    assert service.calls == [("user@example.com", "password123")]


async def test_register_user_maps_duplicate_email(
    app: FastAPI,
    client: httpx.AsyncClient,
) -> None:
    service = _RegistrationService(raised=exceptions.EmailAlreadyExistsError())
    app.dependency_overrides[dependencies.get_registration_service] = lambda: service

    response = await client.post(
        "/v1/users",
        json={"email": "user@example.com", "password": "password123"},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "email_already_exists"


async def test_resend_activation_code_passes_basic_auth_credentials(
    app: FastAPI,
    client: httpx.AsyncClient,
) -> None:
    service = _ResendActivationCodeService()
    resend_dependency = dependencies.get_resend_activation_code_service
    app.dependency_overrides[resend_dependency] = lambda: service

    response = await client.post(
        "/v1/users/11111111-1111-1111-1111-111111111111/activation-code",
        headers={"Authorization": _basic_auth()},
    )

    assert response.status_code == 202
    assert response.content == b""
    assert service.calls == [
        (
            UUID("11111111-1111-1111-1111-111111111111"),
            "user@example.com",
            "secret",
        ),
    ]


async def test_resend_activation_code_maps_cooldown(
    app: FastAPI,
    client: httpx.AsyncClient,
) -> None:
    service = _ResendActivationCodeService(
        raised=exceptions.ResendCooldownNotElapsedError(
            remaining=timedelta(seconds=12),
        ),
    )
    resend_dependency = dependencies.get_resend_activation_code_service
    app.dependency_overrides[resend_dependency] = lambda: service

    response = await client.post(
        "/v1/users/11111111-1111-1111-1111-111111111111/activation-code",
        headers={"Authorization": _basic_auth()},
    )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "12"
    assert response.json()["code"] == "resend_cooldown_not_elapsed"


async def test_activate_user_passes_basic_auth_and_code(
    app: FastAPI,
    client: httpx.AsyncClient,
) -> None:
    service = _ActivationService()
    app.dependency_overrides[dependencies.get_activation_service] = lambda: service

    response = await client.post(
        "/v1/users/11111111-1111-1111-1111-111111111111/activate",
        headers={"Authorization": _basic_auth()},
        json={"code": "1234"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "active"
    assert service.calls == [
        (
            UUID("11111111-1111-1111-1111-111111111111"),
            "user@example.com",
            "secret",
            "1234",
        ),
    ]


@pytest.mark.parametrize(
    ("raised", "expected_status", "expected_code"),
    [
        (
            exceptions.InvalidCredentialsError(),
            401,
            "invalid_credentials",
        ),
        (
            exceptions.ActivationCodeExpiredError(),
            410,
            "activation_code_expired",
        ),
        (
            exceptions.InvalidActivationCodeError(),
            400,
            "invalid_activation_code",
        ),
    ],
)
async def test_activate_user_maps_domain_errors(
    app: FastAPI,
    client: httpx.AsyncClient,
    raised: Exception,
    expected_status: int,
    expected_code: str,
) -> None:
    service = _ActivationService(raised=raised)
    app.dependency_overrides[dependencies.get_activation_service] = lambda: service

    response = await client.post(
        f"/v1/users/{uuid4()}/activate",
        headers={"Authorization": _basic_auth()},
        json={"code": "1234"},
    )

    assert response.status_code == expected_status
    assert response.json()["code"] == expected_code
