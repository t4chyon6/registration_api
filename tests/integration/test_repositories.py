from datetime import UTC, datetime, timedelta

from registration.domain import models
from registration.repositories.activation_codes import ActivationCodeRepository
from registration.repositories.users import UserRepository


async def test_user_and_activation_code_repositories_round_trip(db_connection) -> None:
    users = UserRepository(db_connection)
    activation_codes = ActivationCodeRepository(db_connection)

    user = await users.create_user(
        email="user@example.com",
        password_hash="not-a-secret-test-hash",
    )

    assert user.email == "user@example.com"
    assert user.status is models.UserStatus.PENDING

    expires_at = datetime.now(UTC) + timedelta(minutes=1)
    activation_code = await activation_codes.create_activation_code(
        user_id=user.id,
        code="1234",
        expires_at=expires_at,
    )

    assert activation_code.user_id == user.id
    assert activation_code.code == "1234"
    assert await activation_codes.count_activation_codes(user.id) == 1
    assert await activation_codes.get_latest_activation_code(user.id) == activation_code
    assert await activation_codes.get_latest_unused_code(user.id) == activation_code

    used_at = datetime.now(UTC)
    await activation_codes.mark_code_used(code_id=activation_code.id, used_at=used_at)
    assert await activation_codes.get_latest_unused_code(user.id) is None

    await users.activate_user(user_id=user.id, activated_at=used_at)
    activated_user = await users.get_by_email("USER@example.com")

    assert activated_user is not None
    assert activated_user.status is models.UserStatus.ACTIVE
    assert activated_user.activated_at == used_at
