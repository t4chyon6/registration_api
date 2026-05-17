# 0006. Test and CI Strategy

## Status

Accepted

## Context

The project has fast business-rule coverage and slower database-dependent
coverage. Keeping those feedback loops separate makes failures easier to
diagnose and avoids making every local test run depend on Docker.

CI also validates the Docker image, Docker Compose configuration, and an
end-to-end registration flow through the Compose stack. The image build and E2E
checks should not run when lint, tests, or Docker Compose validation fail.
Password hashing uses Argon2id, so automated tests need explicit lower work
factors where speed matters without changing production defaults.

## Decision

Split tests into two groups:

- Unit tests in `tests/unit`, covering domain rules, adapters, services, API
  routes, exception handlers, and FastAPI lifespan wiring with fakes and
  dependency overrides.
- Integration tests in `tests/integration`, using `testcontainers` PostgreSQL,
  applying `migrations/001_init.sql`, and rolling back each test transaction.
- Docker Compose E2E checks in `scripts/ci/docker_compose_e2e.py`, using the
  CI-built image with PostgreSQL and the MockServer email stub.

Use lower Argon2id settings in unit, integration, and E2E jobs to keep feedback
fast while still exercising the same password-hashing implementation.

Split CI test execution into `unit-test` and `integration-test` jobs. Both jobs
depend on `lint`. The Docker job is named `Docker build and E2E`; it builds
`registration-api:ci`, smoke-tests the runtime command, and runs the Compose E2E
script with that CI-built image. It depends on `lint`, both test jobs, and Docker
Compose lint. Docker Compose lint remains conditional on Docker/migration file
changes; a skipped Docker Compose lint job does not block the Docker job.
The E2E script starts the Compose stack with `--wait --no-build`, relying on
the app health check and the CI-built image instead of rebuilding during E2E.

The workflow sets `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` so JavaScript GitHub
Actions run on Node 24.

## Consequences

Unit failures and database/infrastructure failures are reported independently.
Developers can run the unit suite without Docker, while integration and Compose
E2E checks run where Docker is available.

The Docker image and E2E checks run only after the Python checks and relevant
Compose validation have passed, so CI does not spend time exercising images from
broken source or invalid local orchestration configuration.

The E2E job covers the real container wiring: PostgreSQL schema initialization,
FastAPI startup, MockServer email delivery, Argon2id credential checks, activation
expiry, and resend limits.
