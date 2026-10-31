"""MCP tool handlers for career accomplishment management."""

from typing import Any

from fastmcp import FastMCP

from pktx.accomplishment_service import AccomplishmentService
from pktx.auth import require_user_id
from pktx.tools.errors import raises_tool_error


def register_accomplishment_tools(mcp: FastMCP, get_service: Any) -> None:
    """Register accomplishment MCP tools on the given FastMCP instance."""

    @mcp.tool()
    @raises_tool_error
    def list_accomplishments(
        tag: str | None = None, q: str | None = None
    ) -> list[dict[str, Any]]:
        """List career accomplishments as summaries (no STAR body fields).

        Args:
            tag: Filter by exact tag (e.g., "leadership"). Returns only
                accomplishments that include this tag.
            q: Case-insensitive substring search across title and STAR fields.
        """
        user_id = require_user_id()
        service: AccomplishmentService = get_service()
        tags = [tag] if tag else None
        return service.list_accomplishments(tags=tags, q=q, user_id=user_id)

    @mcp.tool()
    @raises_tool_error
    def get_accomplishment(id: int) -> dict[str, Any]:
        """Get full STAR detail for a specific accomplishment.

        Args:
            id: Accomplishment ID.
        """
        user_id = require_user_id()
        service: AccomplishmentService = get_service()
        return service.get_accomplishment(id, user_id=user_id)

    @mcp.tool()
    @raises_tool_error
    def create_accomplishment(
        title: str,
        situation: str = "",
        task: str = "",
        action: str = "",
        result: str = "",
        accomplishment_date: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new career accomplishment in STAR format.

        Args:
            title: Brief title of the accomplishment (required).
            situation: Context or background of the achievement.
            task: Your specific responsibility or goal.
            action: Steps you took to address the situation.
            result: Outcome or impact, ideally with metrics.
            accomplishment_date: Date of the achievement (YYYY-MM-DD).
            tags: Category tags (e.g., ["leadership", "technical"]).
        """
        user_id = require_user_id()
        service: AccomplishmentService = get_service()
        return service.create_accomplishment(
            {
                "title": title,
                "situation": situation,
                "task": task,
                "action": action,
                "result": result,
                "accomplishment_date": accomplishment_date,
                "tags": tags or [],
            },
            user_id=user_id,
        )

    @mcp.tool()
    @raises_tool_error
    def update_accomplishment(
        id: int,
        title: str | None = None,
        situation: str | None = None,
        task: str | None = None,
        action: str | None = None,
        result: str | None = None,
        accomplishment_date: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update fields of an existing accomplishment (partial update).

        Only provided fields are changed; omitted fields retain their current values.

        Args:
            id: Accomplishment ID.
            title: New title (must not be blank if provided).
            situation: Updated situation/context.
            task: Updated task/responsibility.
            action: Updated action/steps taken.
            result: Updated result/outcome.
            accomplishment_date: Updated date (YYYY-MM-DD) or None to clear.
            tags: Updated tag list (replaces existing tags).
        """
        user_id = require_user_id()
        service: AccomplishmentService = get_service()
        data: dict[str, Any] = {}
        for field, value in [
            ("title", title),
            ("situation", situation),
            ("task", task),
            ("action", action),
            ("result", result),
            ("accomplishment_date", accomplishment_date),
            ("tags", tags),
        ]:
            if value is not None:
                data[field] = value
        return service.update_accomplishment(id, data, user_id=user_id)

    @mcp.tool()
    @raises_tool_error
    def delete_accomplishment(id: int) -> dict[str, Any]:
        """Delete a career accomplishment by ID.

        Args:
            id: Accomplishment ID.

        Returns the deleted `{id, title}`.
        """
        user_id = require_user_id()
        service: AccomplishmentService = get_service()
        acc = service.delete_accomplishment(id, user_id=user_id)
        return {"id": acc["id"], "title": acc["title"]}
