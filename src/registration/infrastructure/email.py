"""Email-service adapter with retry handling."""

import logging
from types import TracebackType
from typing import Self

import httpx
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from registration import config

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """Represent a failure to deliver an activation code email."""


class EmailService:
    """Send activation-code emails through a third-party HTTP API."""

    def __init__(
        self,
        settings: config.Settings,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Create the email-service adapter."""
        self._settings = settings
        self._client = client or httpx.AsyncClient(
            base_url=settings.email_base_url,
            timeout=settings.email_service_timeout,
        )
        self._owns_client = client is None

    async def __aenter__(self) -> Self:
        """Return the email service for async context-manager usage."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the underlying HTTP client when owned by this service."""
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP client when owned by this service."""
        if self._owns_client:
            await self._client.aclose()

    async def send_activation_code(self, email: str, code: str) -> None:
        """Send an activation code email with bounded retries.

        :raises EmailDeliveryError: if the third-party email service fails
        """
        try:
            async for attempt in AsyncRetrying(
                before_sleep=before_sleep_log(logger, logging.WARNING),
                retry=retry_if_exception_type(
                    (
                        httpx.HTTPStatusError,
                        httpx.TimeoutException,
                        httpx.TransportError,
                    ),
                ),
                reraise=True,
                stop=stop_after_attempt(self._settings.email_service_max_retries),
                wait=wait_random_exponential(
                    multiplier=0.1,
                    max=self._settings.email_service_retry_max_wait,
                ),
            ):
                with attempt:
                    await self._post_activation_code(email=email, code=code)
        except httpx.HTTPError as exc:
            msg = "Unable to deliver activation code email"
            raise EmailDeliveryError(msg) from exc

    async def _post_activation_code(self, email: str, code: str) -> None:
        response = await self._client.post(
            "/activation-codes",
            json={"email": email, "code": code},
        )
        response.raise_for_status()
        logger.info("Activation code sent to %s", email)
