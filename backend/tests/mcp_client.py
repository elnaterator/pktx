"""Sync in-memory FastMCP client for tool tests."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp import Client, FastMCP

from pktx.auth import current_user_id_var


class Mcp:
    """Sync helper: ``call`` returns structured data or raises ``RuntimeError``."""

    def __init__(self, server: FastMCP, user: str) -> None:
        self.server = server
        self.user = user

    def _run(self, fn: Callable[[Client], Awaitable[Any]]) -> Any:
        async def go() -> Any:
            token = current_user_id_var.set(self.user)
            try:
                async with Client(self.server) as client:
                    return await fn(client)
            finally:
                current_user_id_var.reset(token)

        return asyncio.run(go())

    def call(self, name: str, /, **args: Any) -> Any:
        result = self._run(
            lambda c: c.call_tool(name, args, raise_on_error=False)  # type: ignore[arg-type]
        )
        if result.is_error:
            raise RuntimeError(result.content[0].text)  # type: ignore[union-attr]
        data = result.structured_content
        if data is None:  # untyped return (Any): JSON in the text content
            return json.loads(result.content[0].text)  # type: ignore[union-attr]
        return data["result"] if set(data) == {"result"} else data

    def tools(self) -> dict[str, Any]:
        return {t.name: t for t in self._run(lambda c: c.list_tools())}
