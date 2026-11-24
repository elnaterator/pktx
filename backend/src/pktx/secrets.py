"""Load runtime secrets from SSM Parameter Store at startup.

In AWS the Lambda environment carries only ``PKTX_SSM_PREFIX`` (e.g. ``/pktx/dev``);
the secrets themselves live as SecureStrings under that prefix and are fetched once
per cold start with the execution role. Values are copied into ``os.environ`` so the
``pktx.config`` resolvers stay unchanged. An env var that is already set wins (local
runs, tests, break-glass overrides). Without the prefix nothing happens and no AWS
client is built.

Keep ``SECRET_PARAMETERS`` in sync with ``secret_names`` in ``infra/dev`` and
``infra/prod`` (a unit test checks it).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("pktx")

PREFIX_ENV = "PKTX_SSM_PREFIX"

# SSM parameter name (under the prefix) -> environment variable it fills.
SECRET_PARAMETERS: dict[str, str] = {
    "database_url": "PKTX_DB_URL",
    "clerk_secret_key": "CLERK_SECRET_KEY",
    "clerk_webhook_secret": "CLERK_WEBHOOK_SECRET",
    "clerk_oauth_client_secret": "CLERK_OAUTH_CLIENT_SECRET",
}

PLACEHOLDER = "TO_BE_SET"


class SecretsError(RuntimeError):
    """Startup secrets could not be loaded. Message names parameters, never values."""


def _default_client() -> Any:
    import boto3  # noqa: PLC0415 — lazy: only AWS deployments pay the import

    return boto3.client("ssm")


def load_ssm_secrets(client_factory: Callable[[], Any] = _default_client) -> None:
    """Fill unset secret env vars from SSM when ``PKTX_SSM_PREFIX`` is set."""
    prefix = os.environ.get(PREFIX_ENV, "").strip().rstrip("/")
    if not prefix:
        return

    wanted = {
        f"{prefix}/{name}": env
        for name, env in SECRET_PARAMETERS.items()
        if not os.environ.get(env)
    }
    if not wanted:
        return

    try:
        resp = client_factory().get_parameters(Names=list(wanted), WithDecryption=True)
    except Exception as exc:  # botocore errors carry no secret material
        raise SecretsError(
            f"could not read secrets under {prefix}: {type(exc).__name__}: {exc}"
        ) from None

    missing = sorted(resp.get("InvalidParameters", []))
    unset = sorted(
        p["Name"]
        for p in resp.get("Parameters", [])
        if p.get("Value", "") in ("", PLACEHOLDER)
    )
    if missing or unset:
        problems = [f"{name} (missing)" for name in missing] + [
            f"{name} (not set)" for name in unset
        ]
        raise SecretsError(f"SSM secrets not ready: {', '.join(problems)}")

    for param in resp.get("Parameters", []):
        os.environ[wanted[param["Name"]]] = param["Value"]
    logger.info("loaded %d secret(s) from SSM under %s", len(wanted), prefix)
