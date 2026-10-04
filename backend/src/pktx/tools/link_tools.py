"""MCP tool handlers for resource linking."""

from collections.abc import Callable

from fastmcp import FastMCP

from pktx.auth import require_user_id
from pktx.link_service import RESOURCE_TYPES, LinkService

_VALID_TYPES = ", ".join(RESOURCE_TYPES)


def register_link_tools(
    mcp: FastMCP,
    get_link_service: Callable[[], LinkService],
) -> None:
    """Register link_resources and unlink_resources MCP tools."""

    @mcp.tool()
    def link_resources(
        a_type: str,
        a_id: int,
        b_type: str,
        b_id: int,
    ) -> str:
        """Link two resources together.

        Args:
            a_type: Resource type (application|accomplishment|resume|note|contact)
            a_id: ID of first resource
            b_type: Resource type (application|accomplishment|resume|note|contact)
            b_id: ID of second resource

        Returns:
            Confirmation message
        """
        if a_type not in RESOURCE_TYPES:
            return f"Error: invalid type '{a_type}'. Must be one of: {_VALID_TYPES}"
        if b_type not in RESOURCE_TYPES:
            return f"Error: invalid type '{b_type}'. Must be one of: {_VALID_TYPES}"

        uid = require_user_id()
        svc = get_link_service()
        try:
            svc.link(a_type, a_id, b_type, b_id, uid)
        except ValueError as e:
            return f"Error: {e}"
        return f"Linked {a_type}/{a_id} ↔ {b_type}/{b_id}"

    @mcp.tool()
    def unlink_resources(
        a_type: str,
        a_id: int,
        b_type: str,
        b_id: int,
    ) -> str:
        """Remove a link between two resources.

        Args:
            a_type: Type of first resource
            a_id: ID of first resource
            b_type: Type of second resource
            b_id: ID of second resource

        Returns:
            Confirmation message
        """
        if a_type not in RESOURCE_TYPES:
            return f"Error: invalid type '{a_type}'. Must be one of: {_VALID_TYPES}"
        if b_type not in RESOURCE_TYPES:
            return f"Error: invalid type '{b_type}'. Must be one of: {_VALID_TYPES}"

        uid = require_user_id()
        svc = get_link_service()
        try:
            svc.unlink(a_type, a_id, b_type, b_id, uid)
        except ValueError as e:
            return f"Error: {e}"
        return f"Unlinked {a_type}/{a_id} ↔ {b_type}/{b_id}"
