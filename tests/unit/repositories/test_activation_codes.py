from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from registration.repositories import activation_codes


class _FakeExecutor:
    def __init__(self, fetchrow_result: dict[str, Any] | None = None) -> None:
        self.fetchrow_result = fetchrow_result
        self.fetchrow_calls: list[tuple[str, tuple[object, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[object, ...]]] = []

    async def fetchrow(self, query: str, *args: object) -> dict[str, Any] | None:
        self.fetchrow_calls.append((query, args))
        return self.fetchrow_result

    async def execute(self, query: str, *args: object) -> str:
        self.execute_calls.append((query, args))
        return "UPDATE 1"


def _now() -> datetime:
    # Repository tests pass timestamps explicitly; reserve time-machine for code
    # that reads the current clock itself.
    return datetime(2026, 5, 17, 9, 30, tzinfo=UTC)


def _activation_code_row(
    *,
    code_id: UUID | None = None,
    user_id: UUID | None = None,
    used_at: datetime | None = None,
) -> dict[str, Any]:
    created_at = _now()
    return {
        "id": code_id or uuid4(),
        "user_id": user_id or uuid4(),
        "code": "1234",
        "expires_at": created_at + timedelta(minutes=1),
        "used_at": used_at,
        "created_at": created_at,
    }


async def test_create_activation_code_inserts_code() -> None:
    user_id = uuid4()
    expires_at = _now() + timedelta(minutes=1)
    executor = _FakeExecutor(fetchrow_result=_activation_code_row(user_id=user_id))
    repository = activation_codes.ActivationCodeRepository(executor)

    activation_code = await repository.create_activation_code(
        user_id=user_id,
        code="1234",
        expires_at=expires_at,
    )

    query, args = executor.fetchrow_calls[0]
    assert "INSERT INTO activation_codes" in query
    assert args == (user_id, "1234", expires_at)
    assert activation_code.user_id == user_id
    assert activation_code.matches("1234")


@pytest.mark.parametrize(
    ("method_name", "expected_where_clause"),
    [
        ("get_latest_activation_code", "WHERE user_id = $1"),
        ("get_latest_unused_code", "AND used_at IS NULL"),
    ],
)
async def test_activation_code_lookup_methods_return_latest_code(
    method_name: str,
    expected_where_clause: str,
) -> None:
    user_id = uuid4()
    executor = _FakeExecutor(fetchrow_result=_activation_code_row(user_id=user_id))
    repository = activation_codes.ActivationCodeRepository(executor)

    method = getattr(repository, method_name)
    activation_code = await method(user_id)

    query, args = executor.fetchrow_calls[0]
    assert expected_where_clause in query
    assert "ORDER BY created_at DESC" in query
    assert args == (user_id,)
    assert activation_code is not None
    assert activation_code.user_id == user_id


async def test_activation_code_lookup_returns_none_when_missing() -> None:
    executor = _FakeExecutor(fetchrow_result=None)
    repository = activation_codes.ActivationCodeRepository(executor)

    assert await repository.get_latest_unused_code(uuid4()) is None


async def test_count_activation_codes_returns_row_count() -> None:
    user_id = uuid4()
    executor = _FakeExecutor(fetchrow_result={"count": 3})
    repository = activation_codes.ActivationCodeRepository(executor)

    count = await repository.count_activation_codes(user_id)

    query, args = executor.fetchrow_calls[0]
    assert "COUNT(*) AS count" in query
    assert args == (user_id,)
    assert count == 3


async def test_count_activation_codes_returns_zero_without_row() -> None:
    executor = _FakeExecutor(fetchrow_result=None)
    repository = activation_codes.ActivationCodeRepository(executor)

    assert await repository.count_activation_codes(uuid4()) == 0


async def test_mark_code_used_updates_unused_code() -> None:
    code_id = uuid4()
    used_at = _now()
    executor = _FakeExecutor()
    repository = activation_codes.ActivationCodeRepository(executor)

    await repository.mark_code_used(code_id=code_id, used_at=used_at)

    query, args = executor.execute_calls[0]
    assert "UPDATE activation_codes" in query
    assert "AND used_at IS NULL" in query
    assert args == (code_id, used_at)
