from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from registration.domain import models


def _now() -> datetime:
    return datetime(2026, 5, 17, 9, 30, tzinfo=UTC)


def _user(
    *,
    is_active: bool,
    activated_at: datetime | None = None,
) -> models.User:
    return models.User(
        id=uuid4(),
        email="user@example.com",
        password_hash="not-a-secret-test-hash",  # noqa: S106
        is_active=is_active,
        created_at=_now(),
        activated_at=activated_at,
    )


def test_user_status_is_pending_for_inactive_user() -> None:
    user = _user(is_active=False)

    assert user.status is models.UserStatus.PENDING


def test_user_status_is_active_for_active_user() -> None:
    user = _user(is_active=True, activated_at=_now())

    assert user.status is models.UserStatus.ACTIVE


def test_user_requires_activation_timestamp_for_active_accounts() -> None:
    with pytest.raises(ValidationError, match="active users"):
        _user(is_active=True)


def test_user_rejects_activation_timestamp_for_pending_accounts() -> None:
    with pytest.raises(ValidationError, match="pending users"):
        _user(is_active=False, activated_at=_now())


def test_activation_code_validates_code_format() -> None:
    with pytest.raises(ValidationError, match="String should match pattern"):
        models.ActivationCode(
            id=uuid4(),
            user_id=uuid4(),
            code="12345",
            created_at=_now(),
            expires_at=_now() + timedelta(minutes=1),
        )


def test_activation_code_validates_expiry_after_creation() -> None:
    with pytest.raises(ValidationError, match="expiry must be after creation"):
        models.ActivationCode(
            id=uuid4(),
            user_id=uuid4(),
            code="1234",
            created_at=_now(),
            expires_at=_now(),
        )


def test_activation_code_validates_used_after_creation() -> None:
    with pytest.raises(ValidationError, match="cannot be used before creation"):
        models.ActivationCode(
            id=uuid4(),
            user_id=uuid4(),
            code="1234",
            created_at=_now(),
            expires_at=_now() + timedelta(minutes=1),
            used_at=_now() - timedelta(seconds=1),
        )


def test_activation_code_predicates() -> None:
    created_at = _now()
    code = models.ActivationCode(
        id=uuid4(),
        user_id=uuid4(),
        code="1234",
        created_at=created_at,
        expires_at=created_at + timedelta(minutes=1),
    )

    assert code.matches("1234")
    assert not code.matches("9999")
    assert not code.is_used()
    assert code.is_usable_at(created_at + timedelta(seconds=59))
    assert code.is_expired(created_at + timedelta(minutes=1))
    assert not code.is_usable_at(created_at + timedelta(minutes=1))


def test_activation_code_is_not_usable_after_consumption() -> None:
    created_at = _now()
    code = models.ActivationCode(
        id=uuid4(),
        user_id=uuid4(),
        code="1234",
        created_at=created_at,
        expires_at=created_at + timedelta(minutes=1),
        used_at=created_at + timedelta(seconds=30),
    )

    assert code.is_used()
    assert not code.is_usable_at(created_at + timedelta(seconds=31))
