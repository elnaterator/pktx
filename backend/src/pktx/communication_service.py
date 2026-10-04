"""ContactCommunicationService — contact comm CRUD + cross-resource search."""

import re
from typing import Any

from pktx.database import (
    create_contact_communication,
    delete_communication_owned,
    load_communication_tags,
    load_contact,
    load_contact_communications,
    search_communications,
    update_communication,
)
from pktx.db import DBConnection
from pktx.models import (
    COMMUNICATION_DIRECTIONS,
    COMMUNICATION_STATUSES,
    COMMUNICATION_TYPES,
)
from pktx.validation import MAX_LONG, MAX_SHORT, check_lengths, normalize_tags

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_LIMITS = {"subject": MAX_SHORT, "body": MAX_LONG}


def _validate_comm_fields(data: dict[str, Any]) -> None:
    if not data.get("type"):
        raise ValueError("Communication type is required")
    if data["type"] not in COMMUNICATION_TYPES:
        valid = ", ".join(COMMUNICATION_TYPES)
        raise ValueError(f"Invalid type: '{data['type']}'. Must be one of: {valid}")
    if not data.get("direction"):
        raise ValueError("Communication direction is required")
    if data["direction"] not in COMMUNICATION_DIRECTIONS:
        raise ValueError(
            f"Invalid direction: '{data['direction']}'. "
            f"Must be one of: {', '.join(COMMUNICATION_DIRECTIONS)}"
        )
    if not data.get("body"):
        raise ValueError("Communication body is required")
    if not data.get("date"):
        raise ValueError("Communication date is required")
    date = data["date"]
    if not _ISO_DATE_RE.match(str(date)):
        raise ValueError(f"date must be in YYYY-MM-DD format, got: '{date}'")
    status = data.get("status", "sent")
    if status not in COMMUNICATION_STATUSES:
        valid_s = ", ".join(COMMUNICATION_STATUSES)
        raise ValueError(f"Invalid status: '{status}'. Must be one of: {valid_s}")
    check_lengths(data, _LIMITS)


def _validate_patch(data: dict[str, Any]) -> dict[str, Any]:
    if "type" in data and data["type"] not in COMMUNICATION_TYPES:
        raise ValueError(
            f"Invalid type: '{data['type']}'. "
            f"Must be one of: {', '.join(COMMUNICATION_TYPES)}"
        )
    if "direction" in data and data["direction"] not in COMMUNICATION_DIRECTIONS:
        raise ValueError(
            f"Invalid direction: '{data['direction']}'. "
            f"Must be one of: {', '.join(COMMUNICATION_DIRECTIONS)}"
        )
    if "status" in data and data["status"] not in COMMUNICATION_STATUSES:
        raise ValueError(
            f"Invalid status: '{data['status']}'. "
            f"Must be one of: {', '.join(COMMUNICATION_STATUSES)}"
        )
    if "date" in data and data["date"]:
        if not _ISO_DATE_RE.match(str(data["date"])):
            raise ValueError(
                f"date must be in YYYY-MM-DD format, got: '{data['date']}'"
            )
    check_lengths(data, _LIMITS)
    if "tags" in data:
        data = {**data, "tags": normalize_tags(data["tags"])}
    return data


class ContactCommunicationService:
    """CRUD for communications attached to networking contacts."""

    def __init__(self, conn: DBConnection) -> None:
        self._conn = conn

    def list_for_contact(
        self, contact_id: int, *, user_id: str
    ) -> list[dict[str, Any]]:
        load_contact(self._conn, contact_id, user_id=user_id)
        return load_contact_communications(self._conn, contact_id, user_id=user_id)

    def add_for_contact(
        self, contact_id: int, data: dict[str, Any], *, user_id: str
    ) -> dict[str, Any]:
        load_contact(self._conn, contact_id, user_id=user_id)
        _validate_comm_fields(data)
        cleaned = {
            "type": data["type"],
            "direction": data["direction"],
            "subject": data.get("subject", ""),
            "body": data["body"],
            "date": data["date"],
            "status": data.get("status", "sent"),
            "tags": normalize_tags(data.get("tags")),
        }
        return create_contact_communication(
            self._conn, contact_id, cleaned, user_id=user_id
        )

    def update(
        self,
        comm_id: int,
        data: dict[str, Any],
        *,
        user_id: str,
        contact_id: int | None = None,
    ) -> dict[str, Any]:
        """Patch a communication owned (via its contact) by ``user_id``.

        When ``contact_id`` is given (REST path) the communication must also
        belong to that contact; any mismatch is "not found".
        """
        data = _validate_patch(data)
        return update_communication(
            self._conn, comm_id, data, user_id=user_id, contact_id=contact_id
        )

    def remove(
        self, comm_id: int, *, user_id: str, contact_id: int | None = None
    ) -> str:
        return delete_communication_owned(
            self._conn, comm_id, user_id=user_id, contact_id=contact_id
        )

    def list_tags(self, user_id: str) -> list[str]:
        return load_communication_tags(self._conn, user_id=user_id)

    def search(
        self,
        q: str | None = None,
        tags: list[str] | None = None,
        *,
        user_id: str,
    ) -> list[dict[str, Any]]:
        normalized_tags = [t.strip().lower() for t in (tags or []) if t.strip()]
        return search_communications(
            self._conn, q=q, tags=normalized_tags, user_id=user_id
        )
