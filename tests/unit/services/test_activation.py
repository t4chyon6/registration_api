from datetime import timedelta
from uuid import uuid4

import pytest

from registration.domain import exceptions, models
from registration.services import activation
from tests.unit.services import fakes


def _service(
    *,
    existing_user: models.User,
    latest_code: models.ActivationCode | None,
    password_verifies: bool = True,
) -> tuple[
    activation.ActivationService,
    fakes.FakeUserRepository,
    fakes.FakeActivationCodeRepository,
    fakes.FakeActivationTransaction,
]:
    auth_user_repository = fakes.FakeUserRepository(existing_user=existing_user)
    tx_user_repository = fakes.FakeUserRepository(existing_user=existing_user)
    code_repository = fakes.FakeActivationCodeRepository(latest_code=latest_code)
    transaction = fakes.FakeActivationTransaction(
        user_repository=tx_user_repository,
        activation_code_repository=code_repository,
    )
    service = activation.ActivationService(
        user_repository=auth_user_repository,
        password_hasher=fakes.FakePasswordHasher(verifies=password_verifies),
        transaction_factory=fakes.FakeActivationTransactionFactory(transaction),
        clock=fakes.now,
    )
    return service, tx_user_repository, code_repository, transaction


async def test_activate_user_consumes_code_and_activates_user() -> None:
    existing_user = fakes.user(password_hash="hashed:secret")
    latest_code = fakes.activation_code(user_id=existing_user.id, code="1234")
    service, user_repository, code_repository, transaction = _service(
        existing_user=existing_user,
        latest_code=latest_code,
    )

    activated_user = await service.activate_user(
        user_id=existing_user.id,
        email=existing_user.email,
        password="secret",
        code="1234",
    )

    assert transaction.entered
    assert transaction.exited
    assert code_repository.used_codes == [(latest_code.id, fakes.now())]
    assert user_repository.activated_users == [(existing_user.id, fakes.now())]
    assert activated_user.status is models.UserStatus.ACTIVE
    assert activated_user.activated_at == fakes.now()


async def test_activate_user_rejects_wrong_password() -> None:
    existing_user = fakes.user(password_hash="hashed:secret")
    service, _, _, transaction = _service(
        existing_user=existing_user,
        latest_code=fakes.activation_code(user_id=existing_user.id),
        password_verifies=False,
    )

    with pytest.raises(exceptions.InvalidCredentialsError):
        await service.activate_user(
            user_id=existing_user.id,
            email=existing_user.email,
            password="wrong",
            code="1234",
        )

    assert not transaction.entered


async def test_activate_user_rejects_mismatched_user_id() -> None:
    existing_user = fakes.user(password_hash="hashed:secret")
    service, _, _, transaction = _service(
        existing_user=existing_user,
        latest_code=fakes.activation_code(user_id=existing_user.id),
    )

    with pytest.raises(exceptions.InvalidCredentialsError):
        await service.activate_user(
            user_id=uuid4(),
            email=existing_user.email,
            password="secret",
            code="1234",
        )

    assert not transaction.entered


async def test_activate_user_rejects_active_user() -> None:
    existing_user = fakes.user(is_active=True, password_hash="hashed:secret")
    service, _, _, transaction = _service(
        existing_user=existing_user,
        latest_code=fakes.activation_code(user_id=existing_user.id),
    )

    with pytest.raises(exceptions.UserAlreadyActiveError):
        await service.activate_user(
            user_id=existing_user.id,
            email=existing_user.email,
            password="secret",
            code="1234",
        )

    assert not transaction.entered


@pytest.mark.parametrize(
    ("latest_code", "submitted_code", "expected_exception"),
    [
        (None, "1234", exceptions.ActivationCodeNotFoundError),
        (
            fakes.activation_code(code="1234"),
            "9999",
            exceptions.InvalidActivationCodeError,
        ),
        (
            fakes.activation_code(
                code="1234",
                created_at=fakes.now() - timedelta(minutes=2),
                expires_at=fakes.now() - timedelta(minutes=1),
            ),
            "1234",
            exceptions.ActivationCodeExpiredError,
        ),
    ],
)
async def test_activate_user_rejects_unusable_codes(
    latest_code: models.ActivationCode | None,
    submitted_code: str,
    expected_exception: type[Exception],
) -> None:
    existing_user = fakes.user(password_hash="hashed:secret")
    if latest_code is not None:
        latest_code = latest_code.model_copy(update={"user_id": existing_user.id})
    service, _, code_repository, _ = _service(
        existing_user=existing_user,
        latest_code=latest_code,
    )

    with pytest.raises(expected_exception):
        await service.activate_user(
            user_id=existing_user.id,
            email=existing_user.email,
            password="secret",
            code=submitted_code,
        )

    assert code_repository.used_codes == []
