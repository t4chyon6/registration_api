"""Raw SQL repository for activation codes."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from registration.domain import models


class _SqlExecutor(Protocol):
    async def fetchrow(self, query: str, *args: object) -> Mapping[str, Any] | None:
        """Return a single database row."""

    async def execute(self, query: str, *args: object) -> str:
        """Execute a SQL statement."""


class ActivationCodeRepository:
    """Persist and retrieve activation codes with explicit SQL."""

    def __init__(self, executor: _SqlExecutor) -> None:
        """Create a repository backed by an asyncpg pool or connection."""
        self._executor = executor

    async def create_activation_code(
        self,
        *,
        user_id: UUID,
        code: str,
        expires_at: datetime,
    ) -> models.ActivationCode:
        """Create an activation code for a user."""
        row = await self._executor.fetchrow(
            """
            INSERT INTO activation_codes (user_id, code, expires_at)
            VALUES ($1, $2, $3)
            RETURNING id, user_id, code, expires_at, used_at, created_at
            """,
            user_id,
            code,
            expires_at,
        )
        if row is None:
            msg = "activation code insert did not return a row"
            raise RuntimeError(msg)
        return _map_activation_code(row)

    async def get_latest_activation_code(
        self,
        user_id: UUID,
    ) -> models.ActivationCode | None:
        """Return the latest activation code issued to a user."""
        row = await self._executor.fetchrow(
            """
            SELECT id, user_id, code, expires_at, used_at, created_at
            FROM activation_codes
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id,
        )
        if row is None:
            return None
        return _map_activation_code(row)

    async def get_latest_unused_code(
        self,
        user_id: UUID,
    ) -> models.ActivationCode | None:
        """Return the latest unused activation code issued to a user."""
        row = await self._executor.fetchrow(
            """
            SELECT id, user_id, code, expires_at, used_at, created_at
            FROM activation_codes
            WHERE user_id = $1
              AND used_at IS NULL
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id,
        )
        if row is None:
            return None
        return _map_activation_code(row)

    async def count_activation_codes(self, user_id: UUID) -> int:
        """Return how many activation codes have been issued to a user."""
        row = await self._executor.fetchrow(
            """
            SELECT COUNT(*) AS count
            FROM activation_codes
            WHERE user_id = $1
            """,
            user_id,
        )
        if row is None:
            return 0
        return int(row["count"])

    async def mark_code_used(
        self,
        *,
        code_id: UUID,
        used_at: datetime,
    ) -> None:
        """Mark an activation code as consumed."""
        await self._executor.execute(
            """
            UPDATE activation_codes
            SET used_at = $2
            WHERE id = $1
              AND used_at IS NULL
            """,
            code_id,
            used_at,
        )


def _map_activation_code(row: Mapping[str, Any]) -> models.ActivationCode:
    return models.ActivationCode(
        id=row["id"],
        user_id=row["user_id"],
        code=row["code"],
        expires_at=row["expires_at"],
        used_at=row["used_at"],
        created_at=row["created_at"],
    )
