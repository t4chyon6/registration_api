"""Anticipated domain exceptions for registration workflows."""

from datetime import timedelta


class RegistrationError(Exception):
    """Base class for anticipated registration-domain failures."""


class EmailAlreadyExistsError(RegistrationError):
    """Raised when a registration email already belongs to a user."""


class UserNotFoundError(RegistrationError):
    """Raised when a user cannot be found."""


class InvalidCredentialsError(RegistrationError):
    """Raised when Basic auth credentials do not match the target user."""


class UserAlreadyActiveError(RegistrationError):
    """Raised when an activation-only action is requested for an active user."""


class ActivationCodeNotFoundError(RegistrationError):
    """Raised when no unused activation code exists for a user."""


class InvalidActivationCodeError(RegistrationError):
    """Raised when the submitted activation code does not match."""


class ActivationCodeExpiredError(RegistrationError):
    """Raised when the submitted activation code is expired."""


class ResendCooldownNotElapsedError(RegistrationError):
    """Raised when a resend request arrives before the cooldown expires."""

    def __init__(self, remaining: timedelta) -> None:
        """Create the error with the remaining cooldown duration."""
        self.remaining = remaining
        super().__init__()


class TooManyActivationCodeRequestsError(RegistrationError):
    """Raised when a user has reached the activation-code issue limit."""
