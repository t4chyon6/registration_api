"""Transaction adapters for application services."""

from types import TracebackType
from typing import Any

import asyncpg

from registration.repositories import activation_codes, users
from registration.services import ports


class AsyncpgActivationTransaction:
    """Create repositories bound to one asyncpg transaction."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        """Create the transaction adapter."""
        self._pool = pool
        self._connection: asyncpg.Connection | None = None
        self._transaction: Any | None = None

    async def __aenter__(
        self,
    ) -> tuple[ports.UserRepositoryPort, ports.ActivationCodeRepositoryPort]:
        """Acquire a connection, start a transaction, and return repositories."""
        connection = await self._pool.acquire()
        transaction = connection.transaction()
        await transaction.start()
        self._connection = connection
        self._transaction = transaction
        return (
            users.UserRepository(connection),
            activation_codes.ActivationCodeRepository(connection),
        )

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Commit or roll back, then release the connection."""
        if self._transaction is None or self._connection is None:
            return
        try:
            if exc_type is None:
                await self._transaction.commit()
            else:
                await self._transaction.rollback()
        finally:
            await self._pool.release(self._connection)


class AsyncpgActivationTransactionFactory:
    """Factory for asyncpg activation transactions."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        """Create the transaction factory."""
        self._pool = pool

    def __call__(self) -> AsyncpgActivationTransaction:
        """Create a transaction context."""
        return AsyncpgActivationTransaction(self._pool)
