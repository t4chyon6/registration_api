"""HTTP exception handlers for anticipated domain failures."""

import math
from http import HTTPStatus

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from registration.domain import exceptions

_BASIC_AUTH_HEADERS = {"WWW-Authenticate": "Basic"}


def register_exception_handlers(app: FastAPI) -> None:
    """Register application exception handlers."""
    app.add_exception_handler(
        exceptions.EmailAlreadyExistsError,
        _email_already_exists,
    )
    app.add_exception_handler(
        exceptions.InvalidCredentialsError,
        _invalid_credentials,
    )
    app.add_exception_handler(
        exceptions.UserAlreadyActiveError,
        _user_already_active,
    )
    app.add_exception_handler(
        exceptions.ActivationCodeNotFoundError,
        _activation_code_not_found,
    )
    app.add_exception_handler(
        exceptions.InvalidActivationCodeError,
        _invalid_activation_code,
    )
    app.add_exception_handler(
        exceptions.ActivationCodeExpiredError,
        _activation_code_expired,
    )
    app.add_exception_handler(
        exceptions.ResendCooldownNotElapsedError,
        _resend_cooldown_not_elapsed,
    )
    app.add_exception_handler(
        exceptions.TooManyActivationCodeRequestsError,
        _too_many_activation_code_requests,
    )
    app.add_exception_handler(exceptions.RegistrationError, _registration_error)


async def _email_already_exists(
    request: Request,
    _exc: Exception,
) -> JSONResponse:
    return _problem(
        request=request,
        status_code=status.HTTP_409_CONFLICT,
        code="email_already_exists",
        detail="A user with this email already exists.",
    )


async def _invalid_credentials(
    request: Request,
    _exc: Exception,
) -> JSONResponse:
    return _problem(
        request=request,
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="invalid_credentials",
        detail="Authentication failed.",
        headers=_BASIC_AUTH_HEADERS,
    )


async def _user_already_active(
    request: Request,
    _exc: Exception,
) -> JSONResponse:
    return _problem(
        request=request,
        status_code=status.HTTP_409_CONFLICT,
        code="user_already_active",
        detail="The user is already active.",
    )


async def _activation_code_not_found(
    request: Request,
    _exc: Exception,
) -> JSONResponse:
    return _problem(
        request=request,
        status_code=status.HTTP_400_BAD_REQUEST,
        code="activation_code_not_found",
        detail="No unused activation code is available for this user.",
    )


async def _invalid_activation_code(
    request: Request,
    _exc: Exception,
) -> JSONResponse:
    return _problem(
        request=request,
        status_code=status.HTTP_400_BAD_REQUEST,
        code="invalid_activation_code",
        detail="The activation code is invalid.",
    )


async def _activation_code_expired(
    request: Request,
    _exc: Exception,
) -> JSONResponse:
    return _problem(
        request=request,
        status_code=status.HTTP_410_GONE,
        code="activation_code_expired",
        detail="The activation code has expired.",
    )


async def _resend_cooldown_not_elapsed(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if not isinstance(exc, exceptions.ResendCooldownNotElapsedError):
        return await _registration_error(request, exc)
    retry_after = max(1, math.ceil(exc.remaining.total_seconds()))
    return _problem(
        request=request,
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        code="resend_cooldown_not_elapsed",
        detail="Activation-code resend cooldown has not elapsed.",
        headers={"Retry-After": str(retry_after)},
    )


async def _too_many_activation_code_requests(
    request: Request,
    _exc: Exception,
) -> JSONResponse:
    return _problem(
        request=request,
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        code="too_many_activation_code_requests",
        detail="The activation-code request limit has been reached.",
    )


async def _registration_error(
    request: Request,
    _exc: Exception,
) -> JSONResponse:
    return _problem(
        request=request,
        status_code=status.HTTP_400_BAD_REQUEST,
        code="registration_error",
        detail=HTTPStatus(status.HTTP_400_BAD_REQUEST).phrase,
    )


def _problem(
    *,
    request: Request,
    status_code: int,
    code: str,
    detail: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "type": f"https://registration-api.local/problems/{code}",
            "title": HTTPStatus(status_code).phrase,
            "status": status_code,
            "detail": detail,
            "instance": str(request.url),
            "code": code,
        },
        headers=headers,
    )
