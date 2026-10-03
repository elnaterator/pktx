"""NoteService — business logic for personal context note CRUD."""

from typing import Any

from pktx.database import (
    create_note,
    delete_note,
    load_note,
    load_note_tags,
    load_notes,
    unlink_all_for,
    update_note,
)
from pktx.db import DBConnection
from pktx.link_service import LinkService
from pktx.validation import MAX_LONG, MAX_NAME, check_len, normalize_tags


def _clean_title(title: Any, *, required: bool) -> str:
    if not title or not str(title).strip():
        raise ValueError(
            "Title is required and must not be blank"
            if required
            else "Title must not be blank"
        )
    title = str(title).strip()
    check_len("Title", title, MAX_NAME)
    return title


class NoteService:
    """Note CRUD operations with constructor-injected DB connection."""

    def __init__(self, conn: DBConnection) -> None:
        self._conn = conn
        self._links = LinkService(conn)

    def list_notes(
        self,
        tags: list[str] | None = None,
        q: str | None = None,
        *,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """Return NoteSummary dicts, ordered by updated_at DESC."""
        normalized = [t.strip().lower() for t in (tags or []) if t.strip()]
        notes = load_notes(self._conn, tags=normalized, q=q, user_id=user_id)
        if notes:
            ids = [n["id"] for n in notes]
            counts = self._links.count_links("note", ids, user_id)
            for n in notes:
                n["link_count"] = counts.get(n["id"], 0)
        return notes

    def list_tags(self, user_id: str) -> list[str]:
        """Return sorted unique tag list for autocomplete."""
        return load_note_tags(self._conn, user_id=user_id)

    def get_note(self, note_id: int, *, user_id: str) -> dict[str, Any]:
        """Return full Note dict. Raises ValueError if not found."""
        note = load_note(self._conn, note_id, user_id=user_id)
        note["links"] = self._links.list_links("note", note_id, user_id)
        return note

    def create_note(self, data: dict[str, Any], *, user_id: str) -> dict[str, Any]:
        """Validate and persist a new note.

        Raises:
            ValueError: If title is missing/blank, or length limits exceeded.
        """
        title = _clean_title(data.get("title", ""), required=True)
        content = data.get("content", "")
        check_len("Content", content, MAX_LONG)

        cleaned: dict[str, Any] = {
            "title": title,
            "content": content,
            "tags": normalize_tags(data.get("tags")),
        }
        return create_note(self._conn, cleaned, user_id=user_id)

    def update_note(
        self, note_id: int, data: dict[str, Any], *, user_id: str
    ) -> dict[str, Any]:
        """Patch fields. Raises ValueError if not found or title would become empty."""
        if "title" in data:
            data = {**data, "title": _clean_title(data["title"], required=False)}
        if "content" in data:
            check_len("Content", data["content"], MAX_LONG)
        if "tags" in data:
            data = {**data, "tags": normalize_tags(data["tags"])}

        return update_note(self._conn, note_id, data, user_id=user_id)

    def delete_note(self, note_id: int, *, user_id: str) -> dict[str, Any]:
        """Delete with links, atomically. Raises ValueError if not found."""
        load_note(self._conn, note_id, user_id=user_id)
        with self._conn.transaction():
            unlink_all_for(self._conn, "note", note_id, user_id)
            return delete_note(self._conn, note_id, user_id=user_id)
