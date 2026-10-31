"""MCP tool handlers for job application management."""

from typing import Any

from fastmcp import FastMCP

from pktx.application_service import ApplicationService
from pktx.auth import require_user_id
from pktx.tools.errors import raises_tool_error


def register_application_tools(mcp: FastMCP, get_service: Any) -> None:
    """Register application MCP tools on the given FastMCP instance."""

    @mcp.tool()
    @raises_tool_error
    def list_applications(
        status: str | None = None,
        tag: str | None = None,
        q: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all job applications with optional filtering.

        Args:
            status: Filter by status (exact match).
            tag: Filter by tag (single tag, case-insensitive).
            q: Search company/position (case-insensitive substring).
        """
        user_id = require_user_id()
        service: ApplicationService = get_service()
        tags = [tag] if tag else None
        return service.list_applications(status=status, tags=tags, q=q, user_id=user_id)

    @mcp.tool()
    @raises_tool_error
    def get_application(id: int) -> dict[str, Any]:
        """Get full details for a specific application.

        Args:
            id: Application ID.
        """
        user_id = require_user_id()
        service: ApplicationService = get_service()
        return service.get_application(id, user_id=user_id)

    @mcp.tool()
    @raises_tool_error
    def create_application(
        company: str,
        position: str,
        description: str = "",
        status: str = "Interested",
        url: str | None = None,
        notes: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new job application.

        Args:
            company: Company name.
            position: Position title.
            description: Job description text.
            status: Initial status (default: Interested).
            url: Job posting URL.
            notes: Free-text notes.
            tags: Tags for categorizing the application.
        """
        user_id = require_user_id()
        service: ApplicationService = get_service()
        return service.create_application(
            {
                "company": company,
                "position": position,
                "description": description,
                "status": status,
                "url": url,
                "notes": notes,
                "tags": tags or [],
            },
            user_id=user_id,
        )

    @mcp.tool()
    @raises_tool_error
    def update_application(
        id: int,
        company: str | None = None,
        position: str | None = None,
        description: str | None = None,
        status: str | None = None,
        url: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update an existing application's fields.

        Args:
            id: Application ID.
            company: Updated company name.
            position: Updated position title.
            description: Updated job description.
            status: Updated status.
            url: Updated URL.
            notes: Updated notes.
            tags: Updated tags.
        """
        user_id = require_user_id()
        service: ApplicationService = get_service()
        data: dict[str, Any] = {}
        for field, value in [
            ("company", company),
            ("position", position),
            ("description", description),
            ("status", status),
            ("url", url),
            ("notes", notes),
            ("tags", tags),
        ]:
            if value is not None:
                data[field] = value
        return service.update_application(id, data, user_id=user_id)

    @mcp.tool()
    @raises_tool_error
    def delete_application(id: int) -> dict[str, Any]:
        """Delete an application and all associated data (cascade).

        Args:
            id: Application ID.

        Returns the deleted `{id, company, position}`.
        """
        user_id = require_user_id()
        service: ApplicationService = get_service()
        app = service.delete_application(id, user_id=user_id)
        return {"id": app["id"], "company": app["company"], "position": app["position"]}

    @mcp.tool()
    @raises_tool_error
    def get_application_context(id: int) -> dict[str, Any]:
        """Get complete context for AI-assisted operations on an application.

        Returns the application plus everything linked to it (notes,
        contacts, accomplishments, resumes) grouped by resource type.

        Args:
            id: Application ID.
        """
        user_id = require_user_id()
        service: ApplicationService = get_service()
        return service.get_application_context(id, user_id=user_id)
