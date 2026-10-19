"""Shared MCP tool error handling."""

import functools
from collections.abc import Callable
from typing import Any, TypeVar

from fastmcp.exceptions import ToolError

F = TypeVar("F", bound=Callable[..., Any])


def raises_tool_error(fn: F) -> F:
    """Turn a service ``ValueError`` into a ``ToolError``.

    The client sees ``isError`` with the message, and ``DBSessionToolMiddleware``
    rolls the write back; returning an ``"Error: ..."`` string would commit it.
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except ValueError as e:
            raise ToolError(str(e)) from e

    return wrapper  # type: ignore[return-value]
