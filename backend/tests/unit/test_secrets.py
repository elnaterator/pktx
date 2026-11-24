"""Startup secret loading from SSM (pktx.secrets)."""

import os
import re
from pathlib import Path
from typing import Any

import pytest

from pktx.secrets import PREFIX_ENV, SECRET_PARAMETERS, SecretsError, load_ssm_secrets

PREFIX = "/pktx/test"
REPO = Path(__file__).resolve().parents[3]


class FakeSsm:
    def __init__(
        self, values: dict[str, str] | None = None, error: Exception | None = None
    ) -> None:
        self.values = values or {}
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def get_parameters(
        self, *, Names: list[str], WithDecryption: bool
    ) -> dict[str, Any]:  # noqa: N803 — boto3 kwargs
        self.calls.append({"Names": Names, "WithDecryption": WithDecryption})
        if self.error:
            raise self.error
        return {
            "Parameters": [
                {"Name": n, "Value": self.values[n]} for n in Names if n in self.values
            ],
            "InvalidParameters": [n for n in Names if n not in self.values],
        }


def _all_values(value: str = "s3cret") -> dict[str, str]:
    return {f"{PREFIX}/{name}": f"{value}-{name}" for name in SECRET_PARAMETERS}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PREFIX_ENV, raising=False)
    for env in SECRET_PARAMETERS.values():
        monkeypatch.delenv(env, raising=False)


def _never() -> Any:
    raise AssertionError("no AWS client may be built without the prefix")


def test_no_prefix_builds_no_client() -> None:
    load_ssm_secrets(client_factory=_never)


def test_fills_env_from_ssm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PREFIX_ENV, PREFIX + "/")
    fake = FakeSsm(_all_values())
    load_ssm_secrets(client_factory=lambda: fake)

    assert fake.calls == [
        {"Names": [f"{PREFIX}/{n}" for n in SECRET_PARAMETERS], "WithDecryption": True}
    ]
    for name, env in SECRET_PARAMETERS.items():
        assert os.environ[env] == f"s3cret-{name}"


def test_explicit_env_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PREFIX_ENV, PREFIX)
    monkeypatch.setenv("PKTX_DB_URL", "postgresql://local")
    fake = FakeSsm(_all_values())
    load_ssm_secrets(client_factory=lambda: fake)

    assert os.environ["PKTX_DB_URL"] == "postgresql://local"
    assert f"{PREFIX}/database_url" not in fake.calls[0]["Names"]


def test_all_set_skips_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PREFIX_ENV, PREFIX)
    for env in SECRET_PARAMETERS.values():
        monkeypatch.setenv(env, "x")
    load_ssm_secrets(client_factory=_never)


def test_missing_and_placeholder_fail_by_name_not_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(PREFIX_ENV, PREFIX)
    values = _all_values()
    del values[f"{PREFIX}/clerk_secret_key"]
    values[f"{PREFIX}/clerk_webhook_secret"] = "TO_BE_SET"
    with pytest.raises(SecretsError) as exc:
        load_ssm_secrets(client_factory=lambda: FakeSsm(values))

    msg = str(exc.value)
    assert f"{PREFIX}/clerk_secret_key (missing)" in msg
    assert f"{PREFIX}/clerk_webhook_secret (not set)" in msg
    assert "s3cret" not in msg


def test_client_error_fails_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PREFIX_ENV, PREFIX)
    with pytest.raises(SecretsError, match=f"could not read secrets under {PREFIX}"):
        load_ssm_secrets(
            client_factory=lambda: FakeSsm(error=ConnectionError("unreachable"))
        )


@pytest.mark.parametrize("env", ["dev", "prod"])
def test_terraform_secret_names_match(env: str) -> None:
    """infra/<env> grants the exec role exactly these parameters."""
    main_tf = (REPO / "infra" / env / "main.tf").read_text()
    block = re.search(r"secret_names\s*=\s*\[(.*?)\]", main_tf, re.S)
    assert block, f"secret_names not found in infra/{env}/main.tf"
    assert sorted(re.findall(r'"([a-z_]+)"', block.group(1))) == sorted(
        SECRET_PARAMETERS
    )
