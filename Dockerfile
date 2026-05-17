FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /build

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --frozen --no-dev --no-cache


FROM python:3.12-slim-bookworm AS runtime

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system registration \
    && useradd --system --gid registration --home-dir /app registration

COPY --from=builder --chown=registration:registration /build/.venv ./.venv
COPY --from=builder --chown=registration:registration /build/src ./src
COPY --from=builder --chown=registration:registration /build/pyproject.toml ./pyproject.toml

USER registration

EXPOSE 8000

CMD ["uvicorn", "registration.main:app", "--host", "0.0.0.0", "--port", "8000"]
