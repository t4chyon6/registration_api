import json

import httpx
import pytest

from registration import config
from registration.infrastructure import email


def _settings(**overrides) -> config.Settings:
    values = {
        "database_url": "postgresql://user:password@localhost:5432/registration_api",
        "email_service_url": "http://email-service.local",
        "email_service_max_retries": 2,
        "email_service_retry_max_wait": 0.0,
    }
    values.update(overrides)
    return config.Settings(**values)


async def test_send_activation_code_retries_transient_failures() -> None:
    settings = _settings()
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            msg = "temporary outage"
            raise httpx.ConnectError(msg, request=request)
        return httpx.Response(status_code=202, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url=settings.email_base_url,
        transport=transport,
    ) as client:
        service = email.EmailService(settings=settings, client=client)

        await service.send_activation_code(
            email="user@example.com",
            code="1234",
        )

    assert len(requests) == 2
    assert requests[1].url.path == "/activation-codes"
    assert json.loads(requests[1].content) == {
        "email": "user@example.com",
        "code": "1234",
    }


async def test_send_activation_code_raises_delivery_error_after_retries() -> None:
    settings = _settings(email_service_max_retries=1)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=503, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url=settings.email_base_url,
        transport=transport,
    ) as client:
        service = email.EmailService(settings=settings, client=client)

        with pytest.raises(
            email.EmailDeliveryError,
            match="Unable to deliver activation code email",
        ):
            await service.send_activation_code(
                email="user@example.com",
                code="1234",
            )
