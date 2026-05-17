import pytest
from pydantic import ValidationError

from registration import config


def test_settings_loads_argon2_tuning_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:password@localhost:5432/registration_api",
    )
    monkeypatch.setenv("EMAIL_SERVICE_URL", "http://email-service.local")
    monkeypatch.setenv("ARGON2_MEMORY_COST", "1024")
    monkeypatch.setenv("ARGON2_TIME_COST", "1")
    monkeypatch.setenv("ARGON2_PARALLELISM", "1")
    monkeypatch.setenv("ARGON2_HASH_LEN", "16")
    monkeypatch.setenv("ARGON2_SALT_LEN", "16")

    settings = config.Settings()

    assert settings.argon2_memory_cost == 1024
    assert settings.argon2_time_cost == 1
    assert settings.argon2_parallelism == 1
    assert settings.argon2_hash_len == 16
    assert settings.argon2_salt_len == 16


def test_settings_exposes_string_urls_for_clients() -> None:
    settings = config.Settings(
        database_url="postgresql://user:password@localhost:5432/registration_api",
        email_service_url="http://email-service.local",
    )

    assert settings.database_dsn == (
        "postgresql://user:password@localhost:5432/registration_api"
    )
    assert settings.email_base_url == "http://email-service.local/"


def test_settings_rejects_incoherent_database_pool_bounds() -> None:
    with pytest.raises(ValidationError, match="DATABASE_POOL_MIN_SIZE"):
        config.Settings(
            database_url="postgresql://user:password@localhost:5432/registration_api",
            database_pool_min_size=5,
            database_pool_max_size=2,
            email_service_url="http://email-service.local",
        )
