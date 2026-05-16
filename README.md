# registration-api

FastAPI service for **user registration** and **email-based account activation** with a time-limited numeric code. The stack targets production-style Python: **async I/O**, **dependency injection**, **Pydantic** for validation, **PostgreSQL** via **asyncpg** (no ORM), and **layered** package layout.

**Status:** project scaffold is in place (uv, Ruff, ty, pre-commit, CI); the HTTP API, persistence, and Docker wiring are implemented in follow-up work.

## Features (target)

- Register with email and password; issue a **4-digit** activation code and send it through an **unreliable HTTP email API** client (retries via **tenacity**).
- Activate the account with **HTTP Basic** auth (email + password) and the code; activation and code consumption run in a **database transaction**; codes expire after a configurable TTL.
- **Resend** activation codes with Basic auth, subject to cooldown and a maximum number of codes per user.

See [docs/architecture.md](docs/architecture.md) for diagrams and design decisions (added with the implementation).

## Requirements

### Day-to-day development

- **Python 3.12** (see `.python-version` and `requires-python` in `pyproject.toml`)
- **[uv](https://docs.astral.sh/uv/)** for environments and lockfiles

### Running in containers (once `Dockerfile` / `docker-compose.yml` exist)

- **Docker** and **Docker Compose** only — no local Python or Postgres install required for that path.

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
uv run pytest
```

Or activate the venv:

```bash
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

## Configuration (environment variables)

Values are loaded via **pydantic-settings** (see `src/registration/config.py` when present). Planned variables:

| Variable | Purpose |
| -------- | ------- |
| `DATABASE_URL` | PostgreSQL URL for **asyncpg** (required at runtime) |
| `DATABASE_POOL_MIN_SIZE` / `DATABASE_POOL_MAX_SIZE` | Connection pool bounds |
| `ACTIVATION_CODE_TTL_SECONDS` | Code validity window (default **60**) |
| `EMAIL_SERVICE_URL` | Base URL of the third-party email HTTP API (required) |
| `EMAIL_SERVICE_TIMEOUT` | Per-request timeout (seconds) |
| `EMAIL_SERVICE_MAX_RETRIES` | **tenacity** retry cap |
| `EMAIL_SERVICE_RETRY_MAX_WAIT` | Max wait between retries (seconds) |
| `BCRYPT_ROUNDS` | bcrypt cost (lower in tests for speed) |
| `MAX_RESEND_ATTEMPTS` | Cap on activation codes issued per user |
| `RESEND_COOLDOWN_SECONDS` | Minimum delay between resend requests |
| `LOG_LEVEL` | Logging level |
| `DEBUG` | FastAPI debug flag |

Copy `.env.example` to `.env` and adjust when that file is added to the repo.

## API (planned)

| Method | Path | Description |
| ------ | ---- | ----------- |
| `POST` | `/v1/users` | Create user (pending); triggers email with code |
| `POST` | `/v1/users/{user_id}/activation-code` | Resend code (Basic auth) |
| `POST` | `/v1/users/{user_id}/activate` | Activate with code (Basic auth) |

Rate limiting is intended to be enforced at the **edge** (API gateway / reverse proxy), not inside the app.

## Pre-commit

Hooks live in `.pre-commit-config.yaml` and use **`language: system`** so they run in the same environment as `uv sync`.

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

## Continuous integration

GitHub Actions (`.github/workflows/ci.yml`) runs on push and pull requests:

1. **Lint** — `uv sync --frozen --dev` then `pre-commit run --all-files` (Ruff + ty).
2. **Test** — `uv sync --frozen --dev` then `pytest` with coverage (uses Docker on the runner for **testcontainers**).

## Repository layout

```
src/registration/   application package (API, services, repositories, infrastructure)
tests/             unit and integration tests
migrations/        SQL migrations (PostgreSQL)
docs/              architecture notes and mermaid diagrams
```

## Conventions

Application structure follows a **layered** layout (interface → services → repositories → infrastructure). Python style aligns with [Kraken public conventions](https://github.com/octoenergy/public-conventions) where practical (explicit APIs, thin HTTP layer, module imports).

## License

Closed source. All rights reserved.
