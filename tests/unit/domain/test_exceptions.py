from datetime import timedelta

from registration.domain import exceptions


def test_domain_exceptions_share_base_type() -> None:
    assert issubclass(
        exceptions.EmailAlreadyExistsError,
        exceptions.RegistrationError,
    )
    assert issubclass(
        exceptions.InvalidActivationCodeError,
        exceptions.RegistrationError,
    )
    assert issubclass(
        exceptions.ActivationCodeExpiredError,
        exceptions.RegistrationError,
    )


def test_resend_cooldown_error_carries_remaining_duration() -> None:
    remaining = timedelta(seconds=42)
    error = exceptions.ResendCooldownNotElapsedError(remaining=remaining)

    assert error.remaining == remaining
