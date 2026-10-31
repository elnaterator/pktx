"""MCP tool handlers for resource linking."""

from collections.abc import Callable
from typing import Literal, get_args

from fastmcp import FastMCP

from pktx.auth import require_user_id
from pktx.link_service import RESOURCE_TYPES, LinkService
from pktx.tools.errors import raises_tool_error

ResourceType = Literal["application", "accomplishment", "resume", "note", "contact"]
if get_args(ResourceType) != RESOURCE_TYPES:
    raise RuntimeError("ResourceType is out of sync with link_service.RESOURCE_TYPES")


def register_link_tools(
    mcp: FastMCP,
    get_link_service: Callable[[], LinkService],
) -> None:
    """Register link_resources and unlink_resources MCP tools."""

    @mcp.tool()
    @raises_tool_error
    def link_resources(
        a_type: ResourceType,
        a_id: int,
        b_type: ResourceType,
        b_id: int,
    ) -> dict[str, str | int]:
        """Link two resources together.

        Args:
            a_type: Type of first resource
            a_id: ID of first resource
            b_type: Type of second resource
            b_id: ID of second resource

        Returns the link `{a_type, a_id, b_type, b_id}`.
        """
        get_link_service().link(a_type, a_id, b_type, b_id, require_user_id())
        return {"a_type": a_type, "a_id": a_id, "b_type": b_type, "b_id": b_id}

    @mcp.tool()
    @raises_tool_error
    def unlink_resources(
        a_type: ResourceType,
        a_id: int,
        b_type: ResourceType,
        b_id: int,
    ) -> dict[str, str | int]:
        """Remove a link between two resources.

        Args:
            a_type: Type of first resource
            a_id: ID of first resource
            b_type: Type of second resource
            b_id: ID of second resource

        Returns the removed link `{a_type, a_id, b_type, b_id}`.
        """
        get_link_service().unlink(a_type, a_id, b_type, b_id, require_user_id())
        return {"a_type": a_type, "a_id": a_id, "b_type": b_type, "b_id": b_id}
