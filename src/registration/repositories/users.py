"""Raw SQL repository for users."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

import asyncpg

from registration.domain import exceptions, models


class _SqlExecutor(Protocol):
    async def fetchrow(self, query: str, *args: object) -> Mapping[str, Any] | None:
        """Return a single database row."""

    async def execute(self, query: str, *args: object) -> str:
        """Execute a SQL statement."""


class UserRepository:
    """Persist and retrieve users with explicit SQL."""

    def __init__(self, executor: _SqlExecutor) -> None:
        """Create a repository backed by an asyncpg pool or connection."""
        self._executor = executor

    async def create_user(self, *, email: str, password_hash: str) -> models.User:
        """Create a pending user.

        :raises EmailAlreadyExistsError: if the email is already registered
        """
        try:
            row = await self._executor.fetchrow(
                """
                INSERT INTO users (email, password_hash)
                VALUES ($1, $2)
                RETURNING id, email, password_hash, is_active, created_at, activated_at
                """,
                email,
                password_hash,
            )
        except asyncpg.UniqueViolationError as exc:
            raise exceptions.EmailAlreadyExistsError from exc

        if row is None:
            msg = "user insert did not return a row"
            raise RuntimeError(msg)
        return _map_user(row)

    async def get_by_email(self, email: str) -> models.User | None:
        """Return a user by email, or None if no matching user exists."""
        row = await self._executor.fetchrow(
            """
            SELECT id, email, password_hash, is_active, created_at, activated_at
            FROM users
            WHERE email = $1
            """,
            email,
        )
        if row is None:
            return None
        return _map_user(row)

    async def activate_user(self, *, user_id: UUID, activated_at: datetime) -> None:
        """Mark a user as active."""
        await self._executor.execute(
            """
            UPDATE users
            SET is_active = TRUE,
                activated_at = $2
            WHERE id = $1
            """,
            user_id,
            activated_at,
        )


def _map_user(row: Mapping[str, Any]) -> models.User:
    return models.User(
        id=row["id"],
        email=row["email"],
        password_hash=row["password_hash"],
        is_active=row["is_active"],
        created_at=row["created_at"],
        activated_at=row["activated_at"],
    )
