# 0002. Domain Models and Anticipated Exceptions

## Status

Accepted

## Context

Registration behavior depends on stable domain concepts: users, activation
codes, user status, and anticipated failures such as duplicate emails or expired
codes. These concepts should not live in FastAPI route handlers or repository
rows because they are business rules rather than transport or persistence
details.

## Decision

Represent `User` and `ActivationCode` as frozen Pydantic models in
`registration.domain.models`.

Use Pydantic rather than `attrs` so the project has a single validation/modeling
library across domain and API schemas. Domain models are immutable with
`ConfigDict(frozen=True)` to keep service behavior predictable.

Represent anticipated workflow failures as explicit exception classes under
`registration.domain.exceptions.RegistrationError`.

## Consequences

Services can express business behavior in terms of immutable domain objects and
specific anticipated failures. The future API layer can map these exceptions to
HTTP responses without putting application logic in route handlers.

The repository layer will convert asyncpg rows into domain models. Any invalid
database row will fail model validation at that boundary instead of leaking
inconsistent data into services.
