import pytest

from registration.services.passwords import PasswordHasher


@pytest.fixture
def fast_argon2_hasher() -> PasswordHasher:
    return PasswordHasher(
        memory_cost=1024,
        time_cost=1,
        parallelism=1,
        hash_len=16,
        salt_len=16,
    )


async def test_password_hasher_hashes_and_verifies_password_with_argon2id(
    fast_argon2_hasher: PasswordHasher,
) -> None:
    password_hash = await fast_argon2_hasher.hash_password(
        "correct horse battery staple"
    )

    assert password_hash.startswith("$argon2id$")
    assert await fast_argon2_hasher.verify_password(
        "correct horse battery staple", password_hash
    )
    assert not await fast_argon2_hasher.verify_password("wrong password", password_hash)


async def test_password_hasher_supports_passwords_longer_than_72_bytes(
    fast_argon2_hasher: PasswordHasher,
) -> None:
    long_password = "p" * 100

    password_hash = await fast_argon2_hasher.hash_password(long_password)

    assert await fast_argon2_hasher.verify_password(long_password, password_hash)
    assert not await fast_argon2_hasher.verify_password(
        f"{long_password}x", password_hash
    )


async def test_password_hasher_returns_false_for_invalid_hash(
    fast_argon2_hasher: PasswordHasher,
) -> None:
    assert not await fast_argon2_hasher.verify_password(
        "correct horse battery staple",
        "not-a-hash",
    )
