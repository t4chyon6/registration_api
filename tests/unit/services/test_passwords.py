from registration.services.passwords import PasswordHasher


async def test_password_hasher_hashes_and_verifies_password_with_real_bcrypt() -> None:
    hasher = PasswordHasher(bcrypt_rounds=4)

    password_hash = await hasher.hash_password("correct horse battery staple")

    assert password_hash.startswith("$2b$")
    assert await hasher.verify_password("correct horse battery staple", password_hash)
    assert not await hasher.verify_password("wrong password", password_hash)
