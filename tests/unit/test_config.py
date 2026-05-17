import pytest
from pydantic import ValidationError

from registration import config


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
