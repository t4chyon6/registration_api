"""Immutable domain models for registration and activation."""

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserStatus(StrEnum):
    """Represent the externally visible user activation status."""

    PENDING = "pending"
    ACTIVE = "active"


class User(BaseModel):
    """Represent a registered user account."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    email: EmailStr
    password_hash: str = Field(min_length=1)
    is_active: bool
    created_at: datetime
    activated_at: datetime | None = None

    @model_validator(mode="after")
    def validate_activation_consistency(self) -> Self:
        """Validate activation flags remain internally consistent."""
        if self.is_active and self.activated_at is None:
            msg = "active users must have an activation timestamp"
            raise ValueError(msg)
        if not self.is_active and self.activated_at is not None:
            msg = "pending users must not have an activation timestamp"
            raise ValueError(msg)
        return self

    @property
    def status(self) -> UserStatus:
        """Return the user activation status."""
        if self.is_active:
            return UserStatus.ACTIVE
        return UserStatus.PENDING


class ActivationCode(BaseModel):
    """Represent a single activation code issued to a user."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    user_id: UUID
    code: str = Field(pattern=r"^\d{4}$")
    expires_at: datetime
    created_at: datetime
    used_at: datetime | None = None

    @model_validator(mode="after")
    def validate_timestamps(self) -> Self:
        """Validate activation code timestamps are coherent."""
        if self.expires_at <= self.created_at:
            msg = "activation code expiry must be after creation"
            raise ValueError(msg)
        if self.used_at is not None and self.used_at < self.created_at:
            msg = "activation code cannot be used before creation"
            raise ValueError(msg)
        return self

    def is_expired(self, at: datetime) -> bool:
        """Test whether the code is expired at a specific time."""
        return at >= self.expires_at

    def is_used(self) -> bool:
        """Test whether the code has already been consumed."""
        return self.used_at is not None

    def is_usable_at(self, at: datetime) -> bool:
        """Test whether the code can be consumed at a specific time."""
        return not self.is_used() and not self.is_expired(at)

    def matches(self, code: str) -> bool:
        """Test whether a submitted code matches this activation code."""
        return self.code == code
