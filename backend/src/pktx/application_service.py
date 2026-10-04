"""ApplicationService — business logic for job application CRUD operations."""

from typing import Any

from pktx.database import (
    create_application,
    delete_application,
    load_application,
    load_application_tags,
    load_applications,
    unlink_all_for,
    update_application,
)
from pktx.db import DBConnection
from pktx.link_service import LinkService
from pktx.models import APPLICATION_STATUSES
from pktx.validation import (
    MAX_LONG,
    MAX_NAME,
    check_lengths,
    normalize_tags,
    validate_http_url,
)

_LIMITS = {
    "company": MAX_NAME,
    "position": MAX_NAME,
    "description": MAX_LONG,
    "notes": MAX_LONG,
}


def _clean(data: dict[str, Any]) -> dict[str, Any]:
    """Validate the fields present in ``data`` and return a normalized copy."""
    check_lengths(data, _LIMITS)
    if "status" in data and data["status"] not in APPLICATION_STATUSES:
        valid = ", ".join(APPLICATION_STATUSES)
        raise ValueError(f"Invalid status: '{data['status']}'. Must be one of: {valid}")
    cleaned = dict(data)
    if "url" in data:
        cleaned["url"] = validate_http_url(data["url"], "url")
    if "tags" in data:
        cleaned["tags"] = normalize_tags(data["tags"])
    return cleaned


class ApplicationService:
    """Application CRUD operations with constructor-injected DB connection."""

    def __init__(self, conn: DBConnection) -> None:
        self._conn = conn
        self._links = LinkService(conn)

    # --- Application CRUD ---

    def create_application(
        self, data: dict[str, Any], *, user_id: str
    ) -> dict[str, Any]:
        """Create a new application."""
        if not data.get("company"):
            raise ValueError("Company is required")
        if not data.get("position"):
            raise ValueError("Position is required")
        data = _clean({"status": "Interested", **data})
        return create_application(self._conn, data, user_id=user_id)

    def get_application(self, app_id: int, *, user_id: str) -> dict[str, Any]:
        """Get a single application by ID."""
        app = load_application(self._conn, app_id, user_id=user_id)
        app["links"] = self._links.list_links("application", app_id, user_id)
        return app

    def list_applications(
        self,
        status: str | list[str] | None = None,
        tags: list[str] | None = None,
        q: str | None = None,
        *,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """List applications with optional filter/search."""
        apps = load_applications(
            self._conn, status=status, tags=tags, q=q, user_id=user_id
        )
        if apps:
            ids = [a["id"] for a in apps]
            counts = self._links.count_links("application", ids, user_id)
            for a in apps:
                a["link_count"] = counts.get(a["id"], 0)
        return apps

    def list_tags(self, user_id: str) -> list[str]:
        """Return sorted unique tag list for autocomplete."""
        return load_application_tags(self._conn, user_id=user_id)

    def update_application(
        self, app_id: int, data: dict[str, Any], *, user_id: str
    ) -> dict[str, Any]:
        """Update application fields."""
        return update_application(self._conn, app_id, _clean(data), user_id=user_id)

    def delete_application(self, app_id: int, *, user_id: str) -> dict[str, Any]:
        """Delete an application and its links atomically (ownership first)."""
        load_application(self._conn, app_id, user_id=user_id)
        with self._conn.transaction():
            unlink_all_for(self._conn, "application", app_id, user_id)
            return delete_application(self._conn, app_id, user_id=user_id)

    # --- Context (AI composite) ---

    def get_application_context(self, app_id: int, *, user_id: str) -> dict[str, Any]:
        """Get full context for AI-assisted operations.

        Returns the application plus everything linked to it via the
        cross-resource links registry, grouped by type.
        """
        app = self.get_application(app_id, user_id=user_id)
        return {"application": app, "linked": app["links"]}
