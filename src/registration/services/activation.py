"""Account activation service."""

from uuid import UUID

from registration.domain import exceptions, models
from registration.services import authentication, ports


class ActivationService:
    """Activate pending users with a valid activation code."""

    def __init__(
        self,
        *,
        user_repository: ports.UserRepositoryPort,
        password_hasher: ports.PasswordHasherPort,
        transaction_factory: ports.ActivationTransactionFactoryPort,
        clock: ports.Clock,
    ) -> None:
        """Create the activation service."""
        self._user_repository = user_repository
        self._password_hasher = password_hasher
        self._transaction_factory = transaction_factory
        self._clock = clock

    async def activate_user(
        self,
        *,
        user_id: UUID,
        email: str,
        password: str,
        code: str,
    ) -> models.User:
        """Activate a user after authenticating and validating their code."""
        user = await authentication.authenticate_user(
            user_repository=self._user_repository,
            password_hasher=self._password_hasher,
            email=email,
            password=password,
        )
        if user.id != user_id:
            raise exceptions.InvalidCredentialsError
        if user.is_active:
            raise exceptions.UserAlreadyActiveError

        now = self._clock()
        async with self._transaction_factory() as (
            user_repository,
            activation_code_repository,
        ):
            activation_code = await activation_code_repository.get_latest_unused_code(
                user.id,
            )
            if activation_code is None:
                raise exceptions.ActivationCodeNotFoundError
            if not activation_code.matches(code):
                raise exceptions.InvalidActivationCodeError
            if activation_code.is_expired(now):
                raise exceptions.ActivationCodeExpiredError

            await activation_code_repository.mark_code_used(
                code_id=activation_code.id,
                used_at=now,
            )
            await user_repository.activate_user(user_id=user.id, activated_at=now)

        return user.model_copy(update={"is_active": True, "activated_at": now})
