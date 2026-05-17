"""User registration and activation routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from registration.api import dependencies, schemas
from registration.services import activation, registration

router = APIRouter(prefix="/v1/users", tags=["users"])


@router.post(
    "",
    response_model=schemas.UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    payload: schemas.RegisterUserRequest,
    service: Annotated[
        registration.RegistrationService,
        Depends(dependencies.get_registration_service),
    ],
) -> schemas.UserResponse:
    """Register a user and send their first activation code."""
    user = await service.register_user(
        email=str(payload.email),
        password=payload.password,
    )
    return schemas.UserResponse.from_domain(user)


@router.post(
    "/{user_id}/activation-code",
    status_code=status.HTTP_202_ACCEPTED,
)
async def resend_activation_code(
    user_id: UUID,
    credentials: dependencies.BasicCredentialsDep,
    service: Annotated[
        registration.ResendActivationCodeService,
        Depends(dependencies.get_resend_activation_code_service),
    ],
) -> Response:
    """Resend an activation code for a pending user."""
    await service.resend_activation_code(
        user_id=user_id,
        email=credentials.username,
        password=credentials.password,
    )
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post(
    "/{user_id}/activate",
    response_model=schemas.UserResponse,
)
async def activate_user(
    user_id: UUID,
    payload: schemas.ActivateUserRequest,
    credentials: dependencies.BasicCredentialsDep,
    service: Annotated[
        activation.ActivationService,
        Depends(dependencies.get_activation_service),
    ],
) -> schemas.UserResponse:
    """Activate a pending user with Basic auth and an activation code."""
    user = await service.activate_user(
        user_id=user_id,
        email=credentials.username,
        password=credentials.password,
        code=payload.code,
    )
    return schemas.UserResponse.from_domain(user)
