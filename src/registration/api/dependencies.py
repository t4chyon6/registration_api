"""FastAPI dependency wiring."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, NamedTuple, cast

import asyncpg
from fastapi import Depends, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from registration import config
from registration.infrastructure import email as email_infrastructure
from registration.repositories import activation_codes, users
from registration.services import activation, codes, passwords, registration
from registration.services import transactions as service_transactions

security = HTTPBasic()


def get_pool(request: Request) -> asyncpg.Pool:
    """Return the application database pool."""
    return cast("asyncpg.Pool", request.app.state.pool)


def get_email_service(request: Request) -> email_infrastructure.EmailService:
    """Return the application email service."""
    return cast("email_infrastructure.EmailService", request.app.state.email_service)


SettingsDep = Annotated[config.Settings, Depends(config.get_settings)]
PoolDep = Annotated[asyncpg.Pool, Depends(get_pool)]
EmailServiceDep = Annotated[
    email_infrastructure.EmailService,
    Depends(get_email_service),
]
BasicCredentialsDep = Annotated[HTTPBasicCredentials, Depends(security)]


class RepositoryDependencies(NamedTuple):
    """Repositories used by activation-code issuing services."""

    user_repository: users.UserRepository
    activation_code_repository: activation_codes.ActivationCodeRepository


def get_clock() -> Callable[[], datetime]:
    """Return the application clock."""
    return lambda: datetime.now(UTC)


def get_password_hasher(settings: SettingsDep) -> passwords.PasswordHasher:
    """Return a password hasher configured from settings."""
    return passwords.PasswordHasher(settings.bcrypt_rounds)


def get_user_repository(pool: PoolDep) -> users.UserRepository:
    """Return a user repository bound to the database pool."""
    return users.UserRepository(pool)


def get_activation_code_repository(
    pool: PoolDep,
) -> activation_codes.ActivationCodeRepository:
    """Return an activation-code repository bound to the database pool."""
    return activation_codes.ActivationCodeRepository(pool)


def get_repository_dependencies(
    user_repository: Annotated[
        users.UserRepository,
        Depends(get_user_repository),
    ],
    activation_code_repository: Annotated[
        activation_codes.ActivationCodeRepository,
        Depends(get_activation_code_repository),
    ],
) -> RepositoryDependencies:
    """Return repositories used for issuing activation codes."""
    return RepositoryDependencies(
        user_repository=user_repository,
        activation_code_repository=activation_code_repository,
    )


def get_activation_code_issue_dependencies(
    settings: SettingsDep,
    repositories: Annotated[
        RepositoryDependencies,
        Depends(get_repository_dependencies),
    ],
    email_service: EmailServiceDep,
    password_hasher: Annotated[
        passwords.PasswordHasher,
        Depends(get_password_hasher),
    ],
    clock: Annotated[Callable[[], datetime], Depends(get_clock)],
) -> registration.ActivationCodeIssueDependencies:
    """Return shared dependencies for activation-code issuing services."""
    return registration.ActivationCodeIssueDependencies(
        settings=settings,
        user_repository=repositories.user_repository,
        activation_code_repository=repositories.activation_code_repository,
        email_service=email_service,
        password_hasher=password_hasher,
        clock=clock,
        code_generator=codes.generate_activation_code,
    )


def get_registration_service(
    dependencies: Annotated[
        registration.ActivationCodeIssueDependencies,
        Depends(get_activation_code_issue_dependencies),
    ],
) -> registration.RegistrationService:
    """Return the registration service."""
    return registration.RegistrationService(dependencies)


def get_resend_activation_code_service(
    dependencies: Annotated[
        registration.ActivationCodeIssueDependencies,
        Depends(get_activation_code_issue_dependencies),
    ],
) -> registration.ResendActivationCodeService:
    """Return the activation-code resend service."""
    return registration.ResendActivationCodeService(dependencies)


def get_activation_transaction_factory(
    pool: PoolDep,
) -> service_transactions.AsyncpgActivationTransactionFactory:
    """Return a transaction factory for account activation."""
    return service_transactions.AsyncpgActivationTransactionFactory(pool)


def get_activation_service(
    user_repository: Annotated[
        users.UserRepository,
        Depends(get_user_repository),
    ],
    password_hasher: Annotated[
        passwords.PasswordHasher,
        Depends(get_password_hasher),
    ],
    transaction_factory: Annotated[
        service_transactions.AsyncpgActivationTransactionFactory,
        Depends(get_activation_transaction_factory),
    ],
    clock: Annotated[Callable[[], datetime], Depends(get_clock)],
) -> activation.ActivationService:
    """Return the activation service."""
    return activation.ActivationService(
        user_repository=user_repository,
        password_hasher=password_hasher,
        transaction_factory=transaction_factory,
        clock=clock,
    )
