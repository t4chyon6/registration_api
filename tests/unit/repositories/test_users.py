from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from registration.domain import exceptions, models
from registration.repositories import users


class _FakeExecutor:
    def __init__(
        self,
        *,
        fetchrow_result: dict[str, Any] | None = None,
        fetchrow_error: Exception | None = None,
    ) -> None:
        self.fetchrow_result = fetchrow_result
        self.fetchrow_error = fetchrow_error
        self.fetchrow_calls: list[tuple[str, tuple[object, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[object, ...]]] = []

    async def fetchrow(self, query: str, *args: object) -> dict[str, Any] | None:
        self.fetchrow_calls.append((query, args))
        if self.fetchrow_error is not None:
            raise self.fetchrow_error
        return self.fetchrow_result

    async def execute(self, query: str, *args: object) -> str:
        self.execute_calls.append((query, args))
        return "UPDATE 1"


def _now() -> datetime:
    # Repository tests pass timestamps explicitly; reserve time-machine for code
    # that reads the current clock itself.
    return datetime(2026, 5, 17, 9, 30, tzinfo=UTC)


def _user_row(
    *,
    user_id: UUID | None = None,
    is_active: bool = False,
    activated_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "id": user_id or uuid4(),
        "email": "user@example.com",
        "password_hash": "not-a-secret-test-hash",
        "is_active": is_active,
        "created_at": _now(),
        "activated_at": activated_at,
    }


async def test_create_user_inserts_pending_user() -> None:
    executor = _FakeExecutor(fetchrow_result=_user_row())
    repository = users.UserRepository(executor)

    user = await repository.create_user(
        email="user@example.com",
        password_hash="not-a-secret-test-hash",  # noqa: S106
    )

    query, args = executor.fetchrow_calls[0]
    assert "INSERT INTO users" in query
    assert args == ("user@example.com", "not-a-secret-test-hash")
    assert isinstance(user, models.User)
    assert user.status is models.UserStatus.PENDING


async def test_create_user_converts_unique_violation_to_domain_error() -> None:
    executor = _FakeExecutor(fetchrow_error=asyncpg.UniqueViolationError())
    repository = users.UserRepository(executor)

    with pytest.raises(exceptions.EmailAlreadyExistsError):
        await repository.create_user(
            email="user@example.com",
            password_hash="not-a-secret-test-hash",  # noqa: S106
        )


async def test_get_by_email_returns_user_when_found() -> None:
    executor = _FakeExecutor(fetchrow_result=_user_row())
    repository = users.UserRepository(executor)

    user = await repository.get_by_email("user@example.com")

    query, args = executor.fetchrow_calls[0]
    assert "WHERE email = $1" in query
    assert args == ("user@example.com",)
    assert user is not None
    assert user.email == "user@example.com"


async def test_get_by_email_returns_none_when_missing() -> None:
    executor = _FakeExecutor(fetchrow_result=None)
    repository = users.UserRepository(executor)

    assert await repository.get_by_email("missing@example.com") is None


async def test_activate_user_sets_active_status() -> None:
    user_id = uuid4()
    activated_at = _now()
    executor = _FakeExecutor()
    repository = users.UserRepository(executor)

    await repository.activate_user(user_id=user_id, activated_at=activated_at)

    query, args = executor.execute_calls[0]
    assert "UPDATE users" in query
    assert "SET is_active = TRUE" in query
    assert args == (user_id, activated_at)
