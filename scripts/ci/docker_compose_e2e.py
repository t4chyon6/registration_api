"""Docker Compose end-to-end checks for the built API image."""
# ruff: noqa: INP001, S608

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from http import HTTPStatus
from typing import Final

import httpx

API_BASE: Final = "http://localhost:8000"
DB_NAME: Final = "registration_api"
DB_USER: Final = "registration_api"
PASSWORD: Final = "correct horse battery staple"  # noqa: S105
WRONG_PASSWORD: Final = "wrong password"  # noqa: S105


class _ApiClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=5)

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, str] | None = None,
        auth: tuple[str, str] | None = None,
    ) -> httpx.Response:
        return self._client.request(
            method,
            path,
            auth=auth,
            json=body,
        )

    def close(self) -> None:
        self._client.close()


def _docker() -> str:
    docker = shutil.which("docker")
    if docker is None:
        message = "docker executable was not found"
        raise SystemExit(message)
    return docker


def _compose() -> list[str]:
    return [_docker(), "compose", "--profile", "app"]


def _e2e_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "BCRYPT_ROUNDS": "4",
            "EMAIL_SERVICE_MAX_RETRIES": "1",
            "EMAIL_SERVICE_RETRY_MAX_WAIT": "0.0",
            "MAX_RESEND_ATTEMPTS": "5",
            "RESEND_COOLDOWN_SECONDS": "60",
        },
    )
    return env


def _run(args: list[str], *, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(  # noqa: S603
        args,
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )
    if completed.returncode != 0:
        command = " ".join(args)
        message = (
            f"Command failed with exit code {completed.returncode}: {command}\n"
            f"{completed.stdout}{completed.stderr}"
        )
        raise SystemExit(message)
    return completed.stdout


def _run_without_check(args: list[str]) -> str:
    completed = subprocess.run(  # noqa: S603
        args,
        check=False,
        capture_output=True,
        text=True,
    )
    return f"{completed.stdout}{completed.stderr}"


def _cleanup() -> None:
    _run_without_check([*_compose(), "down", "-v", "--remove-orphans"])


def _wait_for_api(client: _ApiClient) -> None:
    for _ in range(60):
        try:
            response = client.request("GET", "/openapi.json")
        except httpx.HTTPError:
            time.sleep(1)
            continue

        if response.status_code == HTTPStatus.OK:
            return
        time.sleep(1)

    sys.stderr.write(_run_without_check([*_compose(), "logs"]))
    message = "API did not become ready"
    raise SystemExit(message)


def _sql(statement: str) -> str:
    return _run(
        [
            _docker(),
            "compose",
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            DB_USER,
            "-d",
            DB_NAME,
            "-tA",
            "-c",
            statement,
        ],
    ).strip()


def _activation_code_for(user_id: object) -> str:
    return _sql(
        "SELECT trim(code) FROM activation_codes "
        f"WHERE user_id = '{user_id}' ORDER BY created_at DESC LIMIT 1;",
    )


def _register_user(client: _ApiClient, email: str) -> httpx.Response:
    return client.request(
        "POST",
        "/v1/users",
        body={"email": email, "password": PASSWORD},
    )


def _assert_status(response: httpx.Response, expected: HTTPStatus, label: str) -> None:
    if response.status_code != expected:
        message = (
            f"{label}: expected HTTP {expected.value}, got {response.status_code}\n"
            f"{response.text}"
        )
        raise AssertionError(message)


def _assert_problem_code(response: httpx.Response, expected: str) -> None:
    actual = response.json().get("code")
    if actual != expected:
        message = f"expected problem code {expected!r}, got {actual!r}"
        raise AssertionError(message)


def _exercise_primary_user_flow(client: _ApiClient) -> None:
    registration = _register_user(client, "user@example.com")
    _assert_status(registration, HTTPStatus.CREATED, "register user")
    user_id = registration.json()["id"]

    duplicate = _register_user(client, "user@example.com")
    _assert_status(duplicate, HTTPStatus.CONFLICT, "duplicate email")
    _assert_problem_code(duplicate, "email_already_exists")

    wrong_auth = client.request(
        "POST",
        f"/v1/users/{user_id}/activate",
        body={"code": "0000"},
        auth=("user@example.com", WRONG_PASSWORD),
    )
    _assert_status(wrong_auth, HTTPStatus.UNAUTHORIZED, "wrong credentials")
    _assert_problem_code(wrong_auth, "invalid_credentials")

    invalid_code = client.request(
        "POST",
        f"/v1/users/{user_id}/activate",
        body={"code": "0000"},
        auth=("user@example.com", PASSWORD),
    )
    _assert_status(invalid_code, HTTPStatus.BAD_REQUEST, "invalid activation code")
    _assert_problem_code(invalid_code, "invalid_activation_code")

    cooldown = client.request(
        "POST",
        f"/v1/users/{user_id}/activation-code",
        auth=("user@example.com", PASSWORD),
    )
    _assert_status(cooldown, HTTPStatus.TOO_MANY_REQUESTS, "resend cooldown")
    _assert_problem_code(cooldown, "resend_cooldown_not_elapsed")

    activation_code = _activation_code_for(user_id)
    activation = client.request(
        "POST",
        f"/v1/users/{user_id}/activate",
        body={"code": activation_code},
        auth=("user@example.com", PASSWORD),
    )
    _assert_status(activation, HTTPStatus.OK, "activate user")

    active = client.request(
        "POST",
        f"/v1/users/{user_id}/activate",
        body={"code": activation_code},
        auth=("user@example.com", PASSWORD),
    )
    _assert_status(active, HTTPStatus.CONFLICT, "activate active user")
    _assert_problem_code(active, "user_already_active")

    active_resend = client.request(
        "POST",
        f"/v1/users/{user_id}/activation-code",
        auth=("user@example.com", PASSWORD),
    )
    _assert_status(active_resend, HTTPStatus.CONFLICT, "resend active user")
    _assert_problem_code(active_resend, "user_already_active")


def _exercise_expired_activation_code(client: _ApiClient) -> None:
    registration = _register_user(client, "expired@example.com")
    _assert_status(registration, HTTPStatus.CREATED, "register expiring user")
    user_id = registration.json()["id"]
    activation_code = _activation_code_for(user_id)

    _sql(
        "UPDATE activation_codes "
        "SET created_at = NOW() - INTERVAL '2 minutes', "
        "expires_at = NOW() - INTERVAL '1 minute' "
        f"WHERE user_id = '{user_id}';",
    )

    expired = client.request(
        "POST",
        f"/v1/users/{user_id}/activate",
        body={"code": activation_code},
        auth=("expired@example.com", PASSWORD),
    )
    _assert_status(expired, HTTPStatus.GONE, "expired activation code")
    _assert_problem_code(expired, "activation_code_expired")


def _exercise_missing_activation_code(client: _ApiClient) -> None:
    registration = _register_user(client, "missing-code@example.com")
    _assert_status(registration, HTTPStatus.CREATED, "register missing-code user")
    user_id = registration.json()["id"]
    activation_code = _activation_code_for(user_id)

    _sql(f"UPDATE activation_codes SET used_at = NOW() WHERE user_id = '{user_id}';")

    missing = client.request(
        "POST",
        f"/v1/users/{user_id}/activate",
        body={"code": activation_code},
        auth=("missing-code@example.com", PASSWORD),
    )
    _assert_status(missing, HTTPStatus.BAD_REQUEST, "missing activation code")
    _assert_problem_code(missing, "activation_code_not_found")


def _exercise_too_many_activation_code_requests(client: _ApiClient) -> None:
    registration = _register_user(client, "too-many@example.com")
    _assert_status(registration, HTTPStatus.CREATED, "register too-many user")
    user_id = registration.json()["id"]

    _sql(
        "INSERT INTO activation_codes (user_id, code, created_at, expires_at) "
        f"SELECT '{user_id}', '0001', NOW() - INTERVAL '2 minutes', "
        "NOW() + INTERVAL '1 minute' FROM generate_series(1, 4);",
    )

    too_many = client.request(
        "POST",
        f"/v1/users/{user_id}/activation-code",
        auth=("too-many@example.com", PASSWORD),
    )
    _assert_status(
        too_many,
        HTTPStatus.TOO_MANY_REQUESTS,
        "too many activation code requests",
    )
    _assert_problem_code(too_many, "too_many_activation_code_requests")


def main() -> None:
    """Run the Docker Compose E2E scenario."""
    client = _ApiClient(API_BASE)
    env = _e2e_env()

    _cleanup()
    try:
        _run([*_compose(), "up", "-d", "--no-build"], env=env)
        _wait_for_api(client)

        _exercise_primary_user_flow(client)
        _exercise_expired_activation_code(client)
        _exercise_missing_activation_code(client)
        _exercise_too_many_activation_code_requests(client)
    finally:
        client.close()
        _cleanup()

    sys.stdout.write("Docker Compose E2E checks passed.\n")


if __name__ == "__main__":
    main()
