# Registration API Architecture

This document records the application shape as it is built incrementally. The
implementation follows a layered architecture: HTTP code translates requests,
services hold application use cases, repositories isolate SQL, and
infrastructure adapters own third-party concerns.

## Current System View

```mermaid
flowchart TD
    Client["HTTP Client"]

    subgraph apiLayer [Interface Layer]
        Router["FastAPI Routers"]
        Dependencies["FastAPI Depends"]
        ExceptionHandlers["Exception Handlers"]
    end

    subgraph serviceLayer [Service Layer]
        RegistrationService["Registration Service"]
        ResendService["Resend Service"]
        ActivationService["Activation Service"]
    end

    subgraph domainLayer [Domain Layer]
        DomainModels["Pydantic Domain Models"]
        DomainExceptions["Domain Exceptions"]
    end

    subgraph repositoryLayer [Repository Layer]
        UserRepository["User Repository"]
    end

    subgraph infrastructureLayer [Infrastructure Layer]
        Settings["Settings"]
        DatabasePool["asyncpg Pool"]
        EmailService["Email Service"]
    end

    Client --> Router
    Router --> Dependencies
    Dependencies --> RegistrationService
    Dependencies --> ResendService
    Dependencies --> ActivationService
    RegistrationService --> UserRepository
    ResendService --> UserRepository
    ActivationService --> UserRepository
    RegistrationService --> EmailService
    ResendService --> EmailService
    UserRepository --> DatabasePool
    Settings --> DatabasePool
    Settings --> EmailService
    ExceptionHandlers --> DomainExceptions
    RegistrationService --> DomainModels
    ActivationService --> DomainModels
```

## Infrastructure Layer

The infrastructure layer currently contains:

- `registration.config.Settings`: all runtime configuration loaded through
  environment variables with `pydantic-settings`.
- `registration.infrastructure.database`: asyncpg pool creation and a lifespan
  context manager for startup/shutdown.
- `registration.infrastructure.email.EmailService`: an HTTP adapter for the
  third-party email service using `httpx` and bounded retries with `tenacity`.

The email adapter is deliberately isolated from services. Business code should
depend on a service/port abstraction in later phases, while this adapter owns
transport details such as URLs, timeouts, status handling, and retry policy.

## Domain Layer

The domain layer currently contains:

- `registration.domain.models.User`: an immutable Pydantic model for registered
  user accounts with a derived `status` property.
- `registration.domain.models.ActivationCode`: an immutable Pydantic model for
  issued activation codes, including code-format, timestamp, expiry, usage, and
  matching predicates.
- `registration.domain.exceptions`: anticipated workflow failures, grouped under
  `RegistrationError`, ready for service-layer handling and later HTTP exception
  mapping.

The models are intentionally small and behavior-focused. They encode invariants
that are true regardless of storage or transport, such as "active users have an
activation timestamp" and "activation codes expire after creation."

## Repository Layer

The repository layer currently contains:

- `registration.repositories.users.UserRepository`: raw SQL access for users and
  account state.
- `registration.repositories.activation_codes.ActivationCodeRepository`: raw SQL
  access for activation-code lifecycle operations.

Repositories map asyncpg rows into immutable domain models at the persistence
boundary. This keeps SQL details out of services while still avoiding an ORM.
Services can instantiate repositories with either an asyncpg pool or a
transaction-bound connection, which lets activation later wrap code consumption
and account activation in one database transaction.

## Service Layer

The service layer currently contains:

- `registration.services.registration.RegistrationService`: hashes a password,
  creates a pending user, issues the first activation code, and requests email
  delivery.
- `registration.services.registration.ResendActivationCodeService`: verifies the
  user's Basic Auth credentials, enforces resend cooldown/attempt limits, and
  issues another activation code for pending users.
- `registration.services.activation.ActivationService`: verifies Basic Auth
  credentials, validates the latest unused activation code, marks the code as
  used, and activates the user inside one transaction.

Services depend on protocols rather than concrete repositories or email
adapters. This keeps application rules testable with fakes while allowing the
API layer to inject real asyncpg repositories and infrastructure adapters later.

## Activation Code Lifecycle

```mermaid
flowchart LR
    Issued["Issued"]
    Usable["Usable"]
    Used["Used"]
    Expired["Expired"]

    Issued --> Usable
    Usable -->|"submitted correctly before expiry"| Used
    Usable -->|"current time reaches expires_at"| Expired
```

## Configuration Flow

```mermaid
flowchart LR
    Env["Environment Variables"]
    Settings["Settings"]
    FastApiDepends["FastAPI Depends"]
    DbAdapter["Database Adapter"]
    EmailAdapter["Email Adapter"]

    Env --> Settings
    Settings --> FastApiDepends
    FastApiDepends --> DbAdapter
    FastApiDepends --> EmailAdapter
```

Settings are loaded once through `get_settings()` and then injected. This keeps
application code testable because tests can construct `Settings` directly or
override the dependency when the FastAPI app is added.

## Decisions

Detailed decision records live in `docs/decisions/`.
