"""LinkService — polymorphic resource linking across all resource types."""

from typing import Any

from pktx.database import (
    link_counts,
    link_delete,
    link_insert,
    links_for_resource,
    load_all_links,
    unlink_all_for,
)
from pktx.db import DBConnection
from pktx.models import ResourceRef

RESOURCE_TYPES = ("application", "accomplishment", "resume", "note", "contact")

# (db_table, name_expr) — name_expr is interpolated as SQL so may be a column
# name or a compound expression.
_NAME_QUERIES: dict[str, tuple[str, str]] = {
    "application": ("application", "company || ' – ' || position"),
    "accomplishment": ("accomplishment", "title"),
    "resume": ("resume_version", "label"),
    "note": ("note", "title"),
    "contact": ("contact", "name"),
}

# ownership check queries — SELECT 1 FROM <table> WHERE id = %s AND user_id = %s
_OWNERSHIP_SQL: dict[str, str] = {
    t: f"SELECT 1 FROM {tbl} WHERE id = %s AND user_id = %s"
    for t, (tbl, _) in _NAME_QUERIES.items()
}


def canonicalize(
    a_type: str, a_id: int, b_type: str, b_id: int
) -> tuple[str, int, str, int]:
    """Return (left_type, left_id, right_type, right_id) in canonical order.

    Canonical = left_type < right_type lexicographically; tie broken by id.
    """
    if a_type < b_type or (a_type == b_type and a_id < b_id):
        return a_type, a_id, b_type, b_id
    return b_type, b_id, a_type, a_id


class LinkService:
    """Service for creating/removing/querying resource links."""

    def __init__(self, conn: DBConnection) -> None:
        self._conn = conn

    def _validate_type(self, resource_type: str) -> None:
        if resource_type not in RESOURCE_TYPES:
            raise ValueError(
                f"Invalid resource type: '{resource_type}'. "
                f"Must be one of: {', '.join(RESOURCE_TYPES)}"
            )

    def _check_ownership(self, resource_type: str, resource_id: int, uid: str) -> None:
        """Raise ValueError if the resource doesn't exist or belong to uid."""
        row = self._conn.execute(
            _OWNERSHIP_SQL[resource_type], (resource_id, uid)
        ).fetchone()
        if row is None:
            raise ValueError(
                f"{resource_type.capitalize()} {resource_id} not found "
                f"or not owned by user"
            )

    def link(self, a_type: str, a_id: int, b_type: str, b_id: int, uid: str) -> None:
        """Create a link between two resources. Idempotent."""
        self._validate_type(a_type)
        self._validate_type(b_type)
        if a_type == b_type and a_id == b_id:
            raise ValueError("Cannot link a resource to itself")
        self._check_ownership(a_type, a_id, uid)
        self._check_ownership(b_type, b_id, uid)
        lt, lid, rt, rid = canonicalize(a_type, a_id, b_type, b_id)
        link_insert(self._conn, lt, lid, rt, rid, uid)

    def unlink(self, a_type: str, a_id: int, b_type: str, b_id: int, uid: str) -> None:
        """Remove a link between two resources."""
        self._validate_type(a_type)
        self._validate_type(b_type)
        lt, lid, rt, rid = canonicalize(a_type, a_id, b_type, b_id)
        link_delete(self._conn, lt, lid, rt, rid, uid)

    def list_links(
        self, resource_type: str, resource_id: int, uid: str
    ) -> dict[str, list[ResourceRef]]:
        """Return grouped links for a resource, fetching display names."""
        raw = links_for_resource(self._conn, resource_type, resource_id, uid)
        if not raw:
            return {}

        # Group by other_type
        by_type: dict[str, list[int]] = {}
        for item in raw:
            by_type.setdefault(item["other_type"], []).append(item["other_id"])

        result: dict[str, list[ResourceRef]] = {}
        for rtype, ids in by_type.items():
            tbl, name_col = _NAME_QUERIES[rtype]
            rows = self._conn.execute(
                f"SELECT id, {name_col} AS name, updated_at FROM {tbl} "
                f"WHERE id = ANY(%s)",
                (ids,),
            ).fetchall()
            name_map: dict[int, dict[str, Any]] = {
                r["id"]: {"name": r["name"], "updated_at": r.get("updated_at")}
                for r in rows
            }
            refs: list[ResourceRef] = []
            for rid in ids:
                if rid in name_map:
                    info = name_map[rid]
                    name = info["name"] or ""
                    updated_at = info["updated_at"]
                    refs.append(
                        ResourceRef(
                            type=rtype,  # type: ignore[arg-type]
                            id=rid,
                            name=str(name),
                            updated_at=str(updated_at) if updated_at else None,
                        )
                    )
            if refs:
                result[rtype] = refs

        return result

    def list_all(self, uid: str) -> list[dict[str, Any]]:
        """Return every link owned by a user as flat canonical pairs."""
        return load_all_links(self._conn, uid)

    def count_links(
        self, resource_type: str, resource_ids: list[int], uid: str
    ) -> dict[int, int]:
        """Return {resource_id: link_count} for a set of resource IDs."""
        return link_counts(self._conn, resource_type, resource_ids, uid)

    def unlink_all(self, resource_type: str, resource_id: int, uid: str) -> None:
        """Delete all links for a resource (cascade helper for deletes)."""
        unlink_all_for(self._conn, resource_type, resource_id, uid)
