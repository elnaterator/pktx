"""AccomplishmentService — business logic for career accomplishment CRUD."""

import re
from typing import Any

from pktx.database import (
    create_accomplishment,
    delete_accomplishment,
    load_accomplishment,
    load_accomplishment_tags,
    load_accomplishments,
    unlink_all_for,
    update_accomplishment,
)
from pktx.db import DBConnection
from pktx.link_service import LinkService
from pktx.validation import MAX_LONG, MAX_NAME, check_lengths, normalize_tags

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_date(value: str) -> None:
    """Raise ValueError if value is not a YYYY-MM-DD date string."""
    if not _DATE_RE.match(value):
        raise ValueError(
            f"Invalid accomplishment_date '{value}'. Expected format: YYYY-MM-DD"
        )


_LIMITS = {
    "title": MAX_NAME,
    "situation": MAX_LONG,
    "task": MAX_LONG,
    "action": MAX_LONG,
    "result": MAX_LONG,
}


class AccomplishmentService:
    """Accomplishment CRUD operations with constructor-injected DB connection."""

    def __init__(self, conn: DBConnection) -> None:
        self._conn = conn
        self._links = LinkService(conn)

    def list_accomplishments(
        self,
        tags: list[str] | None = None,
        q: str | None = None,
        *,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """Return AccomplishmentSummary dicts, ordered reverse-chronologically."""
        accs = load_accomplishments(self._conn, tags=tags or [], q=q, user_id=user_id)
        if accs:
            ids = [a["id"] for a in accs]
            counts = self._links.count_links("accomplishment", ids, user_id)
            for a in accs:
                a["link_count"] = counts.get(a["id"], 0)
        return accs

    def list_tags(self, user_id: str) -> list[str]:
        """Return sorted unique tag list for autocomplete."""
        return load_accomplishment_tags(self._conn, user_id=user_id)

    def get_accomplishment(self, acc_id: int, *, user_id: str) -> dict[str, Any]:
        """Return full Accomplishment dict. Raises ValueError if not found."""
        acc = load_accomplishment(self._conn, acc_id, user_id=user_id)
        acc["links"] = self._links.list_links("accomplishment", acc_id, user_id)
        return acc

    def create_accomplishment(
        self, data: dict[str, Any], *, user_id: str
    ) -> dict[str, Any]:
        """Validate and persist a new accomplishment.

        Raises:
            ValueError: If title is missing or blank, or date format is invalid.
        """
        title = data.get("title", "")
        if not title or not str(title).strip():
            raise ValueError("Title is required and must not be blank")

        acc_date = data.get("accomplishment_date")
        if acc_date is not None:
            _validate_date(str(acc_date))

        check_lengths({**data, "title": str(title).strip()}, _LIMITS)
        tags = normalize_tags(data.get("tags"))

        cleaned: dict[str, Any] = {
            "title": str(title).strip(),
            "situation": data.get("situation", ""),
            "task": data.get("task", ""),
            "action": data.get("action", ""),
            "result": data.get("result", ""),
            "accomplishment_date": acc_date,
            "tags": tags,
        }
        return create_accomplishment(self._conn, cleaned, user_id=user_id)

    def update_accomplishment(
        self, acc_id: int, data: dict[str, Any], *, user_id: str
    ) -> dict[str, Any]:
        """Patch fields. Raises ValueError if not found or title would become empty.

        Only fields present in data are updated. Absent keys are left unchanged.
        """
        if "title" in data:
            title = data["title"]
            if not str(title).strip():
                raise ValueError("Title must not be blank")
            data = {**data, "title": str(title).strip()}

        if "accomplishment_date" in data and data["accomplishment_date"] is not None:
            _validate_date(str(data["accomplishment_date"]))

        check_lengths(data, _LIMITS)
        if "tags" in data:
            data = {**data, "tags": normalize_tags(data["tags"])}

        return update_accomplishment(self._conn, acc_id, data, user_id=user_id)

    def delete_accomplishment(self, acc_id: int, *, user_id: str) -> dict[str, Any]:
        """Delete with links, atomically. Raises ValueError if not found."""
        load_accomplishment(self._conn, acc_id, user_id=user_id)
        with self._conn.transaction():
            unlink_all_for(self._conn, "accomplishment", acc_id, user_id)
            return delete_accomplishment(self._conn, acc_id, user_id=user_id)
