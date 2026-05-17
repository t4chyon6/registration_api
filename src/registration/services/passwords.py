"""Password hashing helpers."""

import asyncio

from argon2 import PasswordHasher as Argon2PasswordHasher
from argon2 import Type
from argon2.exceptions import InvalidHashError, VerificationError


class PasswordHasher:
    """Hash and verify passwords with Argon2id."""

    def __init__(
        self,
        *,
        memory_cost: int,
        time_cost: int,
        parallelism: int,
        hash_len: int,
        salt_len: int,
    ) -> None:
        """Create a hasher with configured Argon2id parameters."""
        self._hasher = Argon2PasswordHasher(
            memory_cost=memory_cost,
            time_cost=time_cost,
            parallelism=parallelism,
            hash_len=hash_len,
            salt_len=salt_len,
            type=Type.ID,
        )

    async def hash_password(self, password: str) -> str:
        """Hash a plaintext password without blocking the event loop."""
        return await asyncio.to_thread(self._hasher.hash, password)

    async def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a plaintext password without blocking the event loop."""
        try:
            return await asyncio.to_thread(self._hasher.verify, password_hash, password)
        except (InvalidHashError, VerificationError):
            return False
