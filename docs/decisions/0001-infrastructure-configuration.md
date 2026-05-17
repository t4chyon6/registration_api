# 0001. Infrastructure Configuration and Adapters

## Status

Accepted

## Context

The registration API needs to connect to PostgreSQL and call a third-party email
HTTP API. Both dependencies vary by environment and can fail independently of
the application. Configuration should therefore be explicit, validated at
startup, and kept out of business logic.

## Decision

Use `pydantic-settings` for runtime configuration and expose it through
`registration.config.Settings`.

Use a small asyncpg adapter in `registration.infrastructure.database` to create
and close the connection pool. The FastAPI lifespan will own this pool in a
later phase.

Use `registration.infrastructure.email.EmailService` as the HTTP adapter for the
third-party email service. It uses:

- `httpx.AsyncClient` for async HTTP calls and timeout enforcement.
- `tenacity.AsyncRetrying` for bounded retries on status, timeout, and transport
  failures.
- A local `EmailDeliveryError` to isolate callers from HTTP-library exceptions.

## Consequences

Application services can receive already-constructed dependencies and remain
free of environment parsing, pool construction, and HTTP retry details.

Tests can instantiate `Settings` directly and provide fake clients or monkeypatch
adapter construction without requiring a live database or network.

`ty` does not yet infer that `BaseSettings` can populate required values from
the environment, so the cached `get_settings()` factory carries a narrow
`ty: ignore[missing-argument]` on that construction only.
