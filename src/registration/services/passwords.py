"""Password hashing helpers."""

import asyncio

from passlib.context import CryptContext


class PasswordHasher:
    """Hash and verify passwords with bcrypt."""

    def __init__(self, bcrypt_rounds: int) -> None:
        """Create a hasher with a configured bcrypt work factor."""
        self._context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=bcrypt_rounds,
        )

    async def hash_password(self, password: str) -> str:
        """Hash a plaintext password without blocking the event loop."""
        return await asyncio.to_thread(self._context.hash, password)

    async def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a plaintext password without blocking the event loop."""
        return await asyncio.to_thread(self._context.verify, password, password_hash)
