"""ContactService — business logic for networking contact CRUD."""

import re
from typing import Any

from pktx.database import (
    create_contact,
    delete_contact,
    load_contact,
    load_contact_tags,
    load_contacts,
    unlink_all_for,
    update_contact,
)
from pktx.db import DBConnection
from pktx.link_service import LinkService
from pktx.validation import (
    MAX_LONG,
    MAX_NAME,
    MAX_SHORT,
    check_len,
    check_lengths,
    normalize_tags,
    validate_http_url,
)

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_LIMITS = {
    "email": MAX_SHORT,
    "phone": MAX_SHORT,
    "company": MAX_NAME,
    "title": MAX_SHORT,
    "relationship": MAX_SHORT,
    "location": MAX_SHORT,
    "notes": MAX_LONG,
}

_OPTIONAL_FIELDS = (
    "email",
    "phone",
    "company",
    "title",
    "relationship",
    "linkedin_url",
    "location",
)


def _validate_date(value: str | None, field: str) -> str | None:
    if value is not None and value != "" and not _ISO_DATE_RE.match(value):
        raise ValueError(f"{field} must be in YYYY-MM-DD format, got: '{value}'")
    return value or None


def _clean_name(name: Any, *, required: bool) -> str:
    if not name or not str(name).strip():
        raise ValueError(
            "Name is required and must not be blank"
            if required
            else "Name must not be blank"
        )
    name = str(name).strip()
    check_len("Name", name, MAX_NAME)
    return name


class ContactService:
    """Contact CRUD operations with constructor-injected DB connection."""

    def __init__(self, conn: DBConnection) -> None:
        self._conn = conn
        self._links = LinkService(conn)

    def list_contacts(
        self,
        tags: list[str] | None = None,
        q: str | None = None,
        *,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """Return ContactSummary dicts, ordered by updated_at DESC."""
        normalized = [t.strip().lower() for t in (tags or []) if t.strip()]
        contacts = load_contacts(self._conn, tags=normalized, q=q, user_id=user_id)
        if contacts:
            ids = [c["id"] for c in contacts]
            counts = self._links.count_links("contact", ids, user_id)
            for c in contacts:
                c["link_count"] = counts.get(c["id"], 0)
        return contacts

    def list_tags(self, user_id: str) -> list[str]:
        """Return sorted unique tag list for autocomplete."""
        return load_contact_tags(self._conn, user_id=user_id)

    def get_contact(self, contact_id: int, *, user_id: str) -> dict[str, Any]:
        """Return full Contact dict. Raises ValueError if not found."""
        contact = load_contact(self._conn, contact_id, user_id=user_id)
        contact["links"] = self._links.list_links("contact", contact_id, user_id)
        return contact

    def create_contact(self, data: dict[str, Any], *, user_id: str) -> dict[str, Any]:
        """Validate and persist a new contact.

        Raises:
            ValueError: If name is missing/blank, or length/format limits exceeded.
        """
        check_lengths(data, _LIMITS)
        cleaned: dict[str, Any] = {
            "name": _clean_name(data.get("name", ""), required=True),
            "notes": data.get("notes", ""),
            "tags": normalize_tags(data.get("tags")),
        }
        for field in _OPTIONAL_FIELDS:
            cleaned[field] = data.get(field)
        cleaned["linkedin_url"] = validate_http_url(
            data.get("linkedin_url"), "linkedin_url"
        )
        cleaned["last_contacted_date"] = _validate_date(
            data.get("last_contacted_date"), "last_contacted_date"
        )
        cleaned["followup_date"] = _validate_date(
            data.get("followup_date"), "followup_date"
        )

        return create_contact(self._conn, cleaned, user_id=user_id)

    def update_contact(
        self, contact_id: int, data: dict[str, Any], *, user_id: str
    ) -> dict[str, Any]:
        """Patch fields. Raises ValueError if not found or name would become blank."""
        check_lengths(data, _LIMITS)
        data = dict(data)
        if "name" in data:
            data["name"] = _clean_name(data["name"], required=False)
        if "linkedin_url" in data:
            data["linkedin_url"] = validate_http_url(
                data["linkedin_url"], "linkedin_url"
            )
        if "tags" in data:
            data["tags"] = normalize_tags(data["tags"])
        for date_field in ("last_contacted_date", "followup_date"):
            if date_field in data:
                data[date_field] = _validate_date(data[date_field], date_field)

        return update_contact(self._conn, contact_id, data, user_id=user_id)

    def delete_contact(self, contact_id: int, *, user_id: str) -> dict[str, Any]:
        """Delete with links, atomically. Raises ValueError if not found."""
        load_contact(self._conn, contact_id, user_id=user_id)
        with self._conn.transaction():
            unlink_all_for(self._conn, "contact", contact_id, user_id)
            return delete_contact(self._conn, contact_id, user_id=user_id)
