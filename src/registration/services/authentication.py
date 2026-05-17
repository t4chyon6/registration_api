"""Shared authentication helpers for application services."""

from registration.domain import exceptions, models
from registration.services import ports


async def authenticate_user(
    *,
    user_repository: ports.UserRepositoryPort,
    password_hasher: ports.PasswordHasherPort,
    email: str,
    password: str,
) -> models.User:
    """Return the authenticated user or raise InvalidCredentialsError."""
    user = await user_repository.get_by_email(email)
    if user is None:
        raise exceptions.InvalidCredentialsError

    password_matches = await password_hasher.verify_password(
        password,
        user.password_hash,
    )
    if not password_matches:
        raise exceptions.InvalidCredentialsError
    return user
