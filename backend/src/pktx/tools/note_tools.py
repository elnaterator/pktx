"""MCP tool handlers for personal context note management."""

from typing import Any

from fastmcp import FastMCP

from pktx.auth import require_user_id
from pktx.note_service import NoteService
from pktx.tools.errors import raises_tool_error


def register_note_tools(mcp: FastMCP, get_service: Any) -> None:
    """Register note MCP tools on the given FastMCP instance."""

    @mcp.tool()
    @raises_tool_error
    def list_notes(
        tag: str | None = None, q: str | None = None
    ) -> list[dict[str, Any]]:
        """List personal context notes as summaries (content omitted).

        Args:
            tag: Filter by exact tag (e.g., "python"). Returns only
                notes that include this tag.
            q: Case-insensitive substring search across title and content.
                Multiple words are AND-matched.
        """
        user_id = require_user_id()
        service: NoteService = get_service()
        return service.list_notes(tags=[tag] if tag else None, q=q, user_id=user_id)

    @mcp.tool()
    @raises_tool_error
    def get_note(id: int) -> dict[str, Any]:
        """Get full detail for a specific note including content.

        Args:
            id: Note ID.
        """
        user_id = require_user_id()
        service: NoteService = get_service()
        return service.get_note(id, user_id=user_id)

    @mcp.tool()
    @raises_tool_error
    def create_note(
        title: str,
        content: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new personal context note.

        Args:
            title: Short title for the note (required).
            content: Note body text (optional).
            tags: Category tags (e.g., ["python", "async"]).
        """
        user_id = require_user_id()
        service: NoteService = get_service()
        return service.create_note(
            {
                "title": title,
                "content": content,
                "tags": tags or [],
            },
            user_id=user_id,
        )

    @mcp.tool()
    @raises_tool_error
    def update_note(
        id: int,
        title: str | None = None,
        content: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update fields of an existing note (partial update).

        Only provided fields are changed; omitted fields retain their current values.

        Args:
            id: Note ID.
            title: New title (must not be blank if provided).
            content: Updated body text.
            tags: Updated tag list (replaces existing tags).
        """
        user_id = require_user_id()
        service: NoteService = get_service()
        data: dict[str, Any] = {}
        for field, value in [
            ("title", title),
            ("content", content),
            ("tags", tags),
        ]:
            if value is not None:
                data[field] = value
        return service.update_note(id, data, user_id=user_id)

    @mcp.tool()
    @raises_tool_error
    def delete_note(id: int) -> dict[str, Any]:
        """Delete a personal context note by ID.

        Args:
            id: Note ID.

        Returns the deleted `{id, title}`.
        """
        user_id = require_user_id()
        service: NoteService = get_service()
        note = service.delete_note(id, user_id=user_id)
        return {"id": note["id"], "title": note["title"]}
