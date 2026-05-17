"""HTTP request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from registration.domain import models


class RegisterUserRequest(BaseModel):
    """Request body for user registration."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class ActivateUserRequest(BaseModel):
    """Request body for account activation."""

    code: str = Field(pattern=r"^\d{4}$")


class UserResponse(BaseModel):
    """Externally visible user representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    status: models.UserStatus
    created_at: datetime
    activated_at: datetime | None

    @classmethod
    def from_domain(cls, user: models.User) -> "UserResponse":
        """Build a response schema from a domain user."""
        return cls(
            id=user.id,
            email=user.email,
            status=user.status,
            created_at=user.created_at,
            activated_at=user.activated_at,
        )
