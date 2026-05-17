# 0005. FastAPI Interface Layer

## Status

Accepted

## Context

The API needs to expose registration, activation-code resend, and activation
workflows without moving application rules into route handlers. The service layer
already owns password hashing, activation-code issuing, Basic Auth credential
verification, resend limits, and activation transaction consistency.

The HTTP layer should therefore handle transport concerns only: request/response
schemas, dependency wiring, FastAPI lifespan resources, and mapping anticipated
domain failures to HTTP responses.

## Decision

Add a FastAPI interface layer:

- `registration.main` creates the application, registers routes and exception
  handlers, and owns process resources in the lifespan.
- `registration.api.schemas` defines request and response schemas.
- `registration.api.dependencies` wires settings, asyncpg repositories, the
  email adapter, password hashing, code generation, and activation transactions
  into services.
- `registration.api.exception_handlers` maps domain exceptions into problem-style
  JSON responses.
- `registration.api.routes.users` exposes registration, activation-code resend,
  and activation endpoints under `/v1/users`.

## Consequences

Route handlers stay thin and transport-focused. Application behavior remains
testable through services, while API tests can override FastAPI dependencies
without constructing real network or database resources.

The lifespan is the ownership boundary for the asyncpg pool and HTTP email
client, which keeps startup/shutdown behavior explicit for local runs, Docker,
and future integration tests.
