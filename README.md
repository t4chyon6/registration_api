# registration-api

FastAPI service for **user registration** and **email-based account activation** with a time-limited numeric code. The stack targets production-style Python: **async I/O**, **dependency injection**, **Pydantic** for validation, **PostgreSQL** via **asyncpg** (no ORM), and **layered** package layout.

**Status:** registration, activation, resend, Argon2id password hashing, Docker
Compose local runs, CI, unit tests, integration tests, and Docker Compose E2E
checks are in place.

## Features

- Register with email and password; passwords are hashed with **Argon2id** before
  storage.
- Issue a **4-digit** activation code and send it through an **unreliable HTTP
  email API** client (retries via **tenacity**).
- Activate the account with **HTTP Basic** auth (email + password) and the code; activation and code consumption run in a **database transaction**; codes expire after a configurable TTL.
- **Resend** activation codes with Basic auth, subject to cooldown and a maximum number of codes per user.

See [docs/architecture.md](docs/architecture.md) for diagrams and design decisions.

## Requirements

### Day-to-day development

- **Python 3.12** (see `.python-version` and `requires-python` in `pyproject.toml`)
- **[uv](https://docs.astral.sh/uv/)** for environments and lockfiles

### Running in containers

- **Docker** and **Docker Compose** only - no local Python or Postgres install
  required for that path.

## Setup (uv)

From the repository root:

```bash
uv sync --dev
```

This creates `.venv` and installs runtime and dev dependencies from `uv.lock`.

Run tools without activating the venv:

```bash
uv run ruff check .
uv run ruff format .
uv run ty check src/
uv run pytest tests/unit
uv run pytest tests/integration
```

Or activate the venv:

```bash
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

## Configuration (environment variables)

Values are loaded via **pydantic-settings** (see `src/registration/config.py`):

| Variable | Purpose |
| -------- | ------- |
| `DATABASE_URL` | PostgreSQL URL for **asyncpg** (required at runtime) |
| `DATABASE_POOL_MIN_SIZE` / `DATABASE_POOL_MAX_SIZE` | Connection pool bounds |
| `ACTIVATION_CODE_TTL_SECONDS` | Code validity window (default **60**) |
| `EMAIL_SERVICE_URL` | Base URL of the third-party email HTTP API (required) |
| `EMAIL_SERVICE_TIMEOUT` | Per-request timeout (seconds) |
| `EMAIL_SERVICE_MAX_RETRIES` | **tenacity** retry cap |
| `EMAIL_SERVICE_RETRY_MAX_WAIT` | Max wait between retries (seconds) |
| `ARGON2_MEMORY_COST` / `ARGON2_TIME_COST` / `ARGON2_PARALLELISM` | Argon2id work factors (lower in tests for speed) |
| `ARGON2_HASH_LEN` / `ARGON2_SALT_LEN` | Argon2id output and salt lengths |
| `MAX_RESEND_ATTEMPTS` | Cap on activation codes issued per user |
| `RESEND_COOLDOWN_SECONDS` | Minimum delay between resend requests |
| `LOG_LEVEL` | Logging level |
| `DEBUG` | FastAPI debug flag |

For local shell runs, provide these variables in the environment or an ignored
`.env` file. Docker Compose supplies database, API, and MockServer email-service
defaults for the `app` profile.

Minimal local shell environment:

```bash
export DATABASE_URL="postgresql://registration_api:registration_api@localhost:5432/registration_api"
export EMAIL_SERVICE_URL="http://localhost:8080"
```

## Docker Compose

The Compose stack contains PostgreSQL, the FastAPI app, and a MockServer email
stub. The `postgres` service mounts `migrations/001_init.sql` into Docker's
standard init directory, so a fresh database is created with the required
extensions, tables, constraints, and indexes.

Use this path to test the service from scratch with only Docker installed.

First remove any old containers and volumes:

```bash
docker compose --profile app down -v --remove-orphans
```

Optionally remove the local app image too, which forces the next build to start
from the Dockerfile and lockfile:

```bash
docker image rm registration-api:ci 2>/dev/null || true
```

Confirm the required container tooling is available:

```bash
docker --version
docker compose version
```

Argon2id support is installed from `argon2-cffi`. Docker Compose uses the
`ARGON2_*` defaults from `src/registration/config.py`. For faster manual test
runs, export lower Argon2 settings before starting the app, such as
`ARGON2_MEMORY_COST=1024 ARGON2_TIME_COST=1 ARGON2_PARALLELISM=1`.

Build the FastAPI app image:

```bash
docker compose --profile app build app
```

Start the full stack and wait for health checks:

```bash
docker compose --profile app up -d --wait --no-build
```

The API listens on `http://localhost:8000` in the Compose setup. The mock email
API listens on `http://localhost:1080` and accepts `POST /activation-codes`.

Register a user:

```bash
curl -sS -X POST http://localhost:8000/v1/users \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"correct horse battery staple"}'
```

Copy the returned `id`, then fetch the latest activation code from PostgreSQL:

```bash
docker compose exec -T postgres psql \
  -U registration_api \
  -d registration_api \
  -tA \
  -c "SELECT trim(code) FROM activation_codes WHERE user_id = '<user-id>' ORDER BY created_at DESC LIMIT 1;"
```

Activation codes expire after `ACTIVATION_CODE_TTL_SECONDS`, which defaults to
60 seconds. Complete the manual activation promptly. If you need a longer window
while stepping through the flow, add a temporary Compose override:

```bash
cat > /tmp/registration-api-ttl.yml <<'YAML'
services:
  app:
    environment:
      ACTIVATION_CODE_TTL_SECONDS: "300"
YAML

docker compose \
  -f docker-compose.yml \
  -f /tmp/registration-api-ttl.yml \
  --profile app up -d --wait --no-build
```

Activate the user immediately with HTTP Basic auth:

```bash
curl -sS -X POST http://localhost:8000/v1/users/<user-id>/activate \
  -u "user@example.com:correct horse battery staple" \
  -H "Content-Type: application/json" \
  -d '{"code":"<activation-code>"}'
```

The activation response should include `"status":"active"` and a non-null
`activated_at` timestamp for the same user ID.

MockServer logs received activation-code requests, which is useful when
debugging delivery:

```bash
docker compose logs email-service
```

Clean up when finished:

```bash
docker compose --profile app down -v --remove-orphans
```

## API

| Method | Path | Description |
| ------ | ---- | ----------- |
| `POST` | `/v1/users` | Create user (pending); triggers email with code |
| `POST` | `/v1/users/{user_id}/activation-code` | Resend code (Basic auth) |
| `POST` | `/v1/users/{user_id}/activate` | Activate with code (Basic auth) |

Rate limiting is intended to be enforced at the **edge** (API gateway / reverse proxy), not inside the app.

Example registration request:

```bash
curl -X POST http://localhost:8000/v1/users \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"correct horse battery staple"}'
```

Example resend request:

```bash
curl -X POST http://localhost:8000/v1/users/<user-id>/activation-code \
  -u "user@example.com:correct horse battery staple"
```

Example activation request:

```bash
curl -X POST http://localhost:8000/v1/users/<user-id>/activate \
  -u "user@example.com:correct horse battery staple" \
  -H "Content-Type: application/json" \
  -d '{"code":"1234"}'
```

## Tests

The test suite is split by feedback loop:

- Unit tests cover domain models, settings, infrastructure adapters,
  repositories, services, FastAPI routes, exception handlers, and lifespan
  wiring with fakes and dependency overrides.
- Integration tests exercise repositories against PostgreSQL through
  `testcontainers`.
- Docker Compose E2E checks use a built image, start PostgreSQL, the API, and
  MockServer, then exercise registration, activation, error handling, expiry,
  and resend limits through HTTP.

Run unit tests:

```bash
uv run pytest tests/unit -q
```

Run integration tests:

```bash
uv run pytest tests/integration -q
```

Integration tests and Docker Compose E2E checks require a reachable Docker
daemon. Integration tests skip cleanly when Docker is unavailable locally; CI
runs them where Docker is available on the runner.

## Pre-commit

Hooks live in `.pre-commit-config.yaml` and use **`language: system`** so they run in the same environment as `uv sync`.

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

## Continuous integration

GitHub Actions (`.github/workflows/ci.yml`) runs on push and pull requests:

1. **Lint** — Ruff and `ty` through pre-commit.
2. **Unit test** — `pytest tests/unit` with coverage and faster test-specific environment overrides.
3. **Integration test** — `pytest tests/integration` after lint passes.
4. **Docker Compose lint** — conditional on Docker/migration file changes.
5. **Docker build and E2E** — builds `registration-api:ci`, smoke-tests the
   runtime command, then runs the Docker Compose E2E script with the CI-built
   image after lint, unit tests, integration tests, and Docker Compose lint pass
   or skip successfully. The E2E script starts Compose with
   `--wait --no-build`, relying on service health checks instead of rebuilding
   inside the E2E step.
6. **Markdown lint** — conditional on Markdown file changes.

The workflow opts JavaScript GitHub Actions into Node 24 with
`FORCE_JAVASCRIPT_ACTIONS_TO_NODE24`.

## Repository layout

```text
src/registration/   application package (API, services, repositories, infrastructure)
tests/             unit and integration tests
migrations/        SQL migrations (PostgreSQL)
docker/            MockServer configuration for Compose
scripts/ci/        CI helper scripts, including Docker Compose E2E checks
docs/              architecture notes and mermaid diagrams
```

## Conventions

Application structure follows a **layered** layout (interface → services → repositories → infrastructure). Python style aligns with [Kraken public conventions](https://github.com/octoenergy/public-conventions) where practical (explicit APIs, thin HTTP layer, module imports).

## License

Closed source. All rights reserved.
