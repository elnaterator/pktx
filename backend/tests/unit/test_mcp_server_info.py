"""MCP initialize reports the deployed release as serverInfo.version."""

import asyncio

import pytest
from fastmcp import Client

from pktx.server import _build_mcp


def _server_version() -> str:
    async def go() -> str:
        async with Client(_build_mcp(production=False)) as client:
            return client.initialize_result.serverInfo.version  # type: ignore[union-attr]

    return asyncio.run(go())


def test_server_info_version_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PKTX_VERSION", "v2026.11.24")
    assert _server_version() == "v2026.11.24"


def test_server_info_version_defaults_to_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PKTX_VERSION", raising=False)
    assert _server_version() == "local"
