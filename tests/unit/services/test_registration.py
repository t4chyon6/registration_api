from datetime import timedelta

import pytest

from registration.domain import exceptions
from registration.services import registration
from tests.unit.services import fakes


async def test_register_user_hashes_password_issues_code_and_sends_email() -> None:
    user_repository = fakes.FakeUserRepository()
    code_repository = fakes.FakeActivationCodeRepository()
    email_service = fakes.FakeEmailService()
    password_hasher = fakes.FakePasswordHasher()
    service = registration.RegistrationService(
        registration.ActivationCodeIssueDependencies(
            settings=fakes.settings(activation_code_ttl_seconds=90),
            user_repository=user_repository,
            activation_code_repository=code_repository,
            email_service=email_service,
            password_hasher=password_hasher,
            clock=fakes.now,
            code_generator=lambda: "1234",
        ),
    )

    user = await service.register_user(
        email="user@example.com",
        password="correct horse battery staple",
    )

    assert password_hasher.hashed_passwords == ["correct horse battery staple"]
    assert user_repository.created_users == [
        ("user@example.com", "hashed:correct horse battery staple"),
    ]
    assert code_repository.created_codes == [
        (user.id, "1234", fakes.now() + timedelta(seconds=90)),
    ]
    assert email_service.sent_codes == [("user@example.com", "1234")]


async def test_resend_activation_code_authenticates_and_issues_code() -> None:
    existing_user = fakes.user(password_hash="hashed:secret")
    user_repository = fakes.FakeUserRepository(existing_user=existing_user)
    code_repository = fakes.FakeActivationCodeRepository(issued_count=1)
    email_service = fakes.FakeEmailService()
    service = registration.ResendActivationCodeService(
        registration.ActivationCodeIssueDependencies(
            settings=fakes.settings(resend_cooldown_seconds=0),
            user_repository=user_repository,
            activation_code_repository=code_repository,
            email_service=email_service,
            password_hasher=fakes.FakePasswordHasher(),
            clock=fakes.now,
            code_generator=lambda: "5678",
        ),
    )

    await service.resend_activation_code(
        user_id=existing_user.id,
        email=existing_user.email,
        password="secret",
    )

    assert code_repository.created_codes == [
        (
            existing_user.id,
            "5678",
            fakes.now() + timedelta(seconds=60),
        ),
    ]
    assert email_service.sent_codes == [(existing_user.email, "5678")]


async def test_resend_activation_code_rejects_bad_credentials() -> None:
    service = registration.ResendActivationCodeService(
        registration.ActivationCodeIssueDependencies(
            settings=fakes.settings(),
            user_repository=fakes.FakeUserRepository(existing_user=None),
            activation_code_repository=fakes.FakeActivationCodeRepository(),
            email_service=fakes.FakeEmailService(),
            password_hasher=fakes.FakePasswordHasher(),
            clock=fakes.now,
            code_generator=lambda: "5678",
        ),
    )

    with pytest.raises(exceptions.InvalidCredentialsError):
        await service.resend_activation_code(
            user_id=fakes.user().id,
            email="missing@example.com",
            password="secret",
        )


async def test_resend_activation_code_rejects_active_user() -> None:
    existing_user = fakes.user(is_active=True, password_hash="hashed:secret")
    service = registration.ResendActivationCodeService(
        registration.ActivationCodeIssueDependencies(
            settings=fakes.settings(),
            user_repository=fakes.FakeUserRepository(existing_user=existing_user),
            activation_code_repository=fakes.FakeActivationCodeRepository(),
            email_service=fakes.FakeEmailService(),
            password_hasher=fakes.FakePasswordHasher(),
            clock=fakes.now,
            code_generator=lambda: "5678",
        ),
    )

    with pytest.raises(exceptions.UserAlreadyActiveError):
        await service.resend_activation_code(
            user_id=existing_user.id,
            email=existing_user.email,
            password="secret",
        )


async def test_resend_activation_code_enforces_attempt_cap() -> None:
    existing_user = fakes.user(password_hash="hashed:secret")
    service = registration.ResendActivationCodeService(
        registration.ActivationCodeIssueDependencies(
            settings=fakes.settings(max_resend_attempts=1),
            user_repository=fakes.FakeUserRepository(existing_user=existing_user),
            activation_code_repository=fakes.FakeActivationCodeRepository(
                issued_count=1,
            ),
            email_service=fakes.FakeEmailService(),
            password_hasher=fakes.FakePasswordHasher(),
            clock=fakes.now,
            code_generator=lambda: "5678",
        ),
    )

    with pytest.raises(exceptions.TooManyActivationCodeRequestsError):
        await service.resend_activation_code(
            user_id=existing_user.id,
            email=existing_user.email,
            password="secret",
        )


async def test_resend_activation_code_enforces_cooldown() -> None:
    existing_user = fakes.user(password_hash="hashed:secret")
    latest_code = fakes.activation_code(
        user_id=existing_user.id,
        created_at=fakes.now() - timedelta(seconds=30),
        expires_at=fakes.now() + timedelta(seconds=30),
    )
    service = registration.ResendActivationCodeService(
        registration.ActivationCodeIssueDependencies(
            settings=fakes.settings(resend_cooldown_seconds=60),
            user_repository=fakes.FakeUserRepository(existing_user=existing_user),
            activation_code_repository=fakes.FakeActivationCodeRepository(
                latest_code=latest_code,
                issued_count=1,
            ),
            email_service=fakes.FakeEmailService(),
            password_hasher=fakes.FakePasswordHasher(),
            clock=fakes.now,
            code_generator=lambda: "5678",
        ),
    )

    with pytest.raises(exceptions.ResendCooldownNotElapsedError) as exc_info:
        await service.resend_activation_code(
            user_id=existing_user.id,
            email=existing_user.email,
            password="secret",
        )

    assert exc_info.value.remaining == timedelta(seconds=30)


async def test_resend_activation_code_rejects_mismatched_user_id() -> None:
    existing_user = fakes.user(password_hash="hashed:secret")
    service = registration.ResendActivationCodeService(
        registration.ActivationCodeIssueDependencies(
            settings=fakes.settings(),
            user_repository=fakes.FakeUserRepository(existing_user=existing_user),
            activation_code_repository=fakes.FakeActivationCodeRepository(),
            email_service=fakes.FakeEmailService(),
            password_hasher=fakes.FakePasswordHasher(),
            clock=fakes.now,
            code_generator=lambda: "5678",
        ),
    )

    with pytest.raises(exceptions.InvalidCredentialsError):
        await service.resend_activation_code(
            user_id=fakes.user().id,
            email=existing_user.email,
            password="secret",
        )
