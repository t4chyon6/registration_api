from datetime import UTC, datetime, timedelta
from types import TracebackType
from uuid import UUID, uuid4

from registration import config
from registration.domain import exceptions, models
from registration.services import ports


def now() -> datetime:
    return datetime(2026, 5, 17, 10, 15, tzinfo=UTC)


def settings(**overrides) -> config.Settings:
    values = {
        "database_url": "postgresql://user:password@localhost:5432/registration_api",
        "email_service_url": "http://email-service.local",
        "activation_code_ttl_seconds": 60,
        "max_resend_attempts": 5,
        "resend_cooldown_seconds": 60,
    }
    values.update(overrides)
    return config.Settings(**values)


def user(
    *,
    user_id: UUID | None = None,
    email: str = "user@example.com",
    password_hash: str = "hashed-password",
    is_active: bool = False,
) -> models.User:
    activated_at = now() if is_active else None
    return models.User(
        id=user_id or uuid4(),
        email=email,
        password_hash=password_hash,
        is_active=is_active,
        created_at=now(),
        activated_at=activated_at,
    )


def activation_code(
    *,
    code_id: UUID | None = None,
    user_id: UUID | None = None,
    code: str = "1234",
    created_at: datetime | None = None,
    expires_at: datetime | None = None,
    used_at: datetime | None = None,
) -> models.ActivationCode:
    issued_at = created_at or now()
    return models.ActivationCode(
        id=code_id or uuid4(),
        user_id=user_id or uuid4(),
        code=code,
        created_at=issued_at,
        expires_at=expires_at or issued_at + timedelta(minutes=1),
        used_at=used_at,
    )


class FakeUserRepository:
    def __init__(self, existing_user: models.User | None = None) -> None:
        self.existing_user = existing_user
        self.created_users: list[tuple[str, str]] = []
        self.activated_users: list[tuple[UUID, datetime]] = []

    async def create_user(self, *, email: str, password_hash: str) -> models.User:
        if self.existing_user is not None:
            raise exceptions.EmailAlreadyExistsError
        self.created_users.append((email, password_hash))
        self.existing_user = user(email=email, password_hash=password_hash)
        return self.existing_user

    async def get_by_email(self, email: str) -> models.User | None:
        if self.existing_user is None or self.existing_user.email != email:
            return None
        return self.existing_user

    async def activate_user(self, *, user_id: UUID, activated_at: datetime) -> None:
        self.activated_users.append((user_id, activated_at))


class FakeActivationCodeRepository:
    def __init__(
        self,
        *,
        latest_code: models.ActivationCode | None = None,
        issued_count: int = 0,
    ) -> None:
        self.latest_code = latest_code
        self.issued_count = issued_count
        self.created_codes: list[tuple[UUID, str, datetime]] = []
        self.used_codes: list[tuple[UUID, datetime]] = []

    async def create_activation_code(
        self,
        *,
        user_id: UUID,
        code: str,
        expires_at: datetime,
    ) -> models.ActivationCode:
        self.created_codes.append((user_id, code, expires_at))
        created = activation_code(user_id=user_id, code=code, expires_at=expires_at)
        self.latest_code = created
        self.issued_count += 1
        return created

    async def get_latest_activation_code(
        self,
        user_id: UUID,
    ) -> models.ActivationCode | None:
        if self.latest_code is None or self.latest_code.user_id != user_id:
            return None
        return self.latest_code

    async def get_latest_unused_code(
        self,
        user_id: UUID,
    ) -> models.ActivationCode | None:
        if self.latest_code is None or self.latest_code.user_id != user_id:
            return None
        return None if self.latest_code.is_used() else self.latest_code

    async def count_activation_codes(self, user_id: UUID) -> int:
        _ = user_id
        return self.issued_count

    async def mark_code_used(self, *, code_id: UUID, used_at: datetime) -> None:
        self.used_codes.append((code_id, used_at))


class FakeEmailService:
    def __init__(self) -> None:
        self.sent_codes: list[tuple[str, str]] = []

    async def send_activation_code(self, email: str, code: str) -> None:
        self.sent_codes.append((email, code))


class FakePasswordHasher:
    def __init__(self, *, verifies: bool = True) -> None:
        self.verifies = verifies
        self.hashed_passwords: list[str] = []

    async def hash_password(self, password: str) -> str:
        self.hashed_passwords.append(password)
        return f"hashed:{password}"

    async def verify_password(self, password: str, password_hash: str) -> bool:
        return self.verifies and password_hash == f"hashed:{password}"


class FakeActivationTransaction:
    def __init__(
        self,
        user_repository: ports.UserRepositoryPort,
        activation_code_repository: ports.ActivationCodeRepositoryPort,
    ) -> None:
        self.user_repository = user_repository
        self.activation_code_repository = activation_code_repository
        self.entered = False
        self.exited = False

    async def __aenter__(
        self,
    ) -> tuple[ports.UserRepositoryPort, ports.ActivationCodeRepositoryPort]:
        self.entered = True
        return self.user_repository, self.activation_code_repository

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.exited = True


class FakeActivationTransactionFactory:
    def __init__(self, transaction: FakeActivationTransaction) -> None:
        self.transaction = transaction

    def __call__(self) -> FakeActivationTransaction:
        return self.transaction
