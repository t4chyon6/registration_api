"""Registration and activation-code resend services."""

import logging
from datetime import datetime, timedelta
from typing import NamedTuple
from uuid import UUID

from registration import config
from registration.domain import exceptions, models
from registration.infrastructure import email as email_infrastructure
from registration.services import authentication, ports

logger = logging.getLogger(__name__)


class ActivationCodeIssueDependencies(NamedTuple):
    """Dependencies shared by services that issue activation codes."""

    settings: config.Settings
    user_repository: ports.UserRepositoryPort
    activation_code_repository: ports.ActivationCodeRepositoryPort
    email_service: ports.EmailServicePort
    password_hasher: ports.PasswordHasherPort
    clock: ports.Clock
    code_generator: ports.CodeGenerator


class RegistrationService:
    """Register users and issue their first activation code."""

    def __init__(self, dependencies: ActivationCodeIssueDependencies) -> None:
        """Create the registration service."""
        self._dependencies = dependencies

    async def register_user(self, *, email: str, password: str) -> models.User:
        """Create a pending user, issue a code, and send it by email."""
        password_hash = await self._dependencies.password_hasher.hash_password(password)
        user = await self._dependencies.user_repository.create_user(
            email=email,
            password_hash=password_hash,
        )
        code = await self._create_activation_code(user.id)
        await _send_activation_code(
            email_service=self._dependencies.email_service,
            email=user.email,
            code=code.code,
        )
        return user

    async def _create_activation_code(self, user_id: UUID) -> models.ActivationCode:
        now = self._dependencies.clock()
        code_repository = self._dependencies.activation_code_repository
        return await code_repository.create_activation_code(
            user_id=user_id,
            code=self._dependencies.code_generator(),
            expires_at=_activation_code_expires_at(
                now=now,
                settings=self._dependencies.settings,
            ),
        )


class ResendActivationCodeService:
    """Issue replacement activation codes for pending users."""

    def __init__(self, dependencies: ActivationCodeIssueDependencies) -> None:
        """Create the activation-code resend service."""
        self._dependencies = dependencies

    async def resend_activation_code(
        self,
        *,
        email: str,
        password: str,
    ) -> None:
        """Issue and send another activation code for a pending user."""
        user = await authentication.authenticate_user(
            user_repository=self._dependencies.user_repository,
            password_hasher=self._dependencies.password_hasher,
            email=email,
            password=password,
        )
        if user.is_active:
            raise exceptions.UserAlreadyActiveError

        issued_count = (
            await self._dependencies.activation_code_repository.count_activation_codes(
                user.id,
            )
        )
        if issued_count >= self._dependencies.settings.max_resend_attempts:
            raise exceptions.TooManyActivationCodeRequestsError

        await self._ensure_cooldown_elapsed(user.id)
        code = await self._create_activation_code(user.id)
        await _send_activation_code(
            email_service=self._dependencies.email_service,
            email=user.email,
            code=code.code,
        )

    async def _ensure_cooldown_elapsed(self, user_id: UUID) -> None:
        code_repository = self._dependencies.activation_code_repository
        latest_code = await code_repository.get_latest_activation_code(
            user_id,
        )
        if latest_code is None:
            return

        cooldown = timedelta(
            seconds=self._dependencies.settings.resend_cooldown_seconds,
        )
        next_allowed_at = latest_code.created_at + cooldown
        now = self._dependencies.clock()
        if now < next_allowed_at:
            raise exceptions.ResendCooldownNotElapsedError(
                remaining=next_allowed_at - now,
            )

    async def _create_activation_code(self, user_id: UUID) -> models.ActivationCode:
        now = self._dependencies.clock()
        code_repository = self._dependencies.activation_code_repository
        return await code_repository.create_activation_code(
            user_id=user_id,
            code=self._dependencies.code_generator(),
            expires_at=_activation_code_expires_at(
                now=now,
                settings=self._dependencies.settings,
            ),
        )


async def _send_activation_code(
    *,
    email_service: ports.EmailServicePort,
    email: str,
    code: str,
) -> None:
    try:
        await email_service.send_activation_code(email=email, code=code)
    except email_infrastructure.EmailDeliveryError:
        logger.exception("Unable to send activation code email")


def _activation_code_expires_at(
    *,
    now: datetime,
    settings: config.Settings,
) -> datetime:
    return now + timedelta(seconds=settings.activation_code_ttl_seconds)
