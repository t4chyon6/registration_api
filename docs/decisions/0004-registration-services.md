# 0004. Registration Services and Transaction Boundary

## Status

Accepted

## Context

Registration workflows coordinate several dependencies: password hashing,
repositories, activation-code generation, email delivery, and time. Putting that
coordination in route handlers would violate the layered architecture and make
the business rules hard to test.

Activation also has one critical consistency requirement: consuming an activation
code and activating the user must happen in one database transaction.

## Decision

Add application services for registration, resend, and activation:

- `RegistrationService`
- `ResendActivationCodeService`
- `ActivationService`

Services depend on protocols for repositories, password hashing, email delivery,
clock access, activation-code generation, and the activation transaction. Tests
use fakes for those protocols.

`ActivationService` authenticates the user before opening the transaction, then
uses repositories bound to one transaction context to mark the code used and
activate the account.

## Consequences

The future FastAPI layer can stay thin: parse transport input, inject service
dependencies, call a service, and map domain exceptions to HTTP responses.

The transaction boundary is explicit and unit-testable. The concrete asyncpg
transaction adapter can be wired later without changing activation business
logic.
