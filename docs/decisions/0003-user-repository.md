# 0003. Repositories With Raw SQL

## Status

Accepted

## Context

The project intentionally avoids ORMs. Registration services still need a stable
boundary for persistence so SQL, row mapping, and database-specific exceptions do
not leak into application use cases.

## Decision

Create raw SQL repositories backed by objects that implement asyncpg-style
`fetchrow` and `execute` methods:

- `registration.repositories.users.UserRepository` owns user account rows.
- `registration.repositories.activation_codes.ActivationCodeRepository` owns
  activation-code rows.

The repository itself remains a plain Python object. Pydantic is used for data
objects that need validation and serialization, such as `User`, `ActivationCode`,
settings, and future API schemas. A repository is a behaviorful adapter around a
live dependency, not data, so making it a Pydantic model would add little value
and make dependency injection less direct.

Repositories map rows into immutable domain models:

- `User`
- `ActivationCode`

`UserRepository` also converts duplicate-email database errors into
`EmailAlreadyExistsError`, keeping anticipated registration failures in the
domain exception hierarchy.

## Consequences

Services can use the same repository classes with either an asyncpg pool or an
explicit transaction connection. That keeps the future activation flow
straightforward: open one transaction, instantiate `UserRepository` and
`ActivationCodeRepository` with the same connection, load the latest unused code,
mark it used, and activate the user.

Repository unit tests use lightweight async fakes. Real PostgreSQL coverage is
deferred to integration tests once the service/API layer exists.
