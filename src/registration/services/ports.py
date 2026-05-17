"""Protocols consumed by application services."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from types import TracebackType
from typing import Protocol
from uuid import UUID

from registration.domain import models


class UserRepositoryPort(Protocol):
    """Persistence operations required by user services."""

    async def create_user(self, *, email: str, password_hash: str) -> models.User:
        """Create a pending user."""

    async def get_by_email(self, email: str) -> models.User | None:
        """Return a user by email."""

    async def activate_user(self, *, user_id: UUID, activated_at: datetime) -> None:
        """Mark a user as active."""


class ActivationCodeRepositoryPort(Protocol):
    """Persistence operations required by activation-code services."""

    async def create_activation_code(
        self,
        *,
        user_id: UUID,
        code: str,
        expires_at: datetime,
    ) -> models.ActivationCode:
        """Create an activation code."""

    async def get_latest_activation_code(
        self,
        user_id: UUID,
    ) -> models.ActivationCode | None:
        """Return the latest activation code for a user."""

    async def get_latest_unused_code(
        self,
        user_id: UUID,
    ) -> models.ActivationCode | None:
        """Return the latest unused activation code for a user."""

    async def count_activation_codes(self, user_id: UUID) -> int:
        """Return how many activation codes a user has received."""

    async def mark_code_used(self, *, code_id: UUID, used_at: datetime) -> None:
        """Mark an activation code as used."""


class EmailServicePort(Protocol):
    """Email operations required by registration services."""

    async def send_activation_code(self, email: str, code: str) -> None:
        """Send an activation code to a user."""


class PasswordHasherPort(Protocol):
    """Password operations required by registration services."""

    async def hash_password(self, password: str) -> str:
        """Hash a plaintext password."""

    async def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a plaintext password against a password hash."""


class ActivationTransactionPort(Protocol):
    """Transaction context for activation-code consumption."""

    async def __aenter__(
        self,
    ) -> tuple[
        UserRepositoryPort,
        ActivationCodeRepositoryPort,
    ]:
        """Return repositories bound to one transaction."""

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit the transaction context."""


class ActivationTransactionFactoryPort(Protocol):
    """Factory for activation transaction contexts."""

    def __call__(self) -> ActivationTransactionPort:
        """Create an activation transaction context."""


Clock = Callable[[], datetime]
CodeGenerator = Callable[[], str]
AsyncVoidCallback = Callable[[], Awaitable[None]]
