"""PostgreSQL database operations for pktx resume data."""

import datetime
import json
import logging
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from pktx.db import DBConnection
from pktx.migrations import apply_migrations

logger = logging.getLogger("pktx")


def escape_like(value: str) -> str:
    """Escape LIKE/ILIKE wildcards so ``value`` matches literally.

    Pair with ``ESCAPE '\\'`` in the SQL.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def build_filters(
    user_id: str,
    tags: list[str] | None,
    q: str | None,
    q_columns: list[str],
    *,
    user_id_column: str = "user_id",
    tags_column: str = "tags",
) -> tuple[list[str], list[Any]]:
    """Build WHERE conditions + params for user_id, tag, and q filters.

    Returns (conditions, params). Caller appends any extra conditions then
    joins with " AND " and prepends " WHERE ". The user condition is always
    present — there is no unscoped query.

    q is split into words; each word must match at least one q_column (AND
    semantics across words, OR across columns). Tags use JSON-text matching:
    ``tags ILIKE '%"tag"%'``. ``%``, ``_`` and ``\\`` in q words and tags are
    escaped so they match literally.
    """
    conditions: list[str] = [f"{user_id_column} = %s"]
    params: list[Any] = [user_id]

    for tag in tags or []:
        conditions.append(f"{tags_column} ILIKE %s ESCAPE '\\'")
        params.append(f'%"{escape_like(tag)}"%')

    if q:
        for word in q.strip().split():
            pattern = f"%{escape_like(word)}%"
            col_expr = " OR ".join(f"{col} ILIKE %s ESCAPE '\\'" for col in q_columns)
            conditions.append(f"({col_expr})")
            params.extend([pattern] * len(q_columns))

    return conditions, params


def _load_tags(raw: str | None) -> list[str]:
    """Parse a stored tags JSON column; legacy ``'null'`` rows read as []."""
    return (json.loads(raw) if raw else None) or []


def init_pool(dsn: str, min_size: int = 1, max_size: int = 10) -> ConnectionPool[Any]:
    """Initialize a PostgreSQL connection pool and run pending migrations.

    Opens a pool configured with dict_row, applies any pending schema
    migrations using a single connection checkout, and returns the pool
    ready for use.
    """
    pool = ConnectionPool(
        dsn,
        min_size=min_size,
        max_size=max_size,
        open=True,
        kwargs={"row_factory": dict_row},
    )
    with pool.connection() as conn:
        apply_migrations(conn)
    logger.info("PostgreSQL pool initialized (min=%d, max=%d)", min_size, max_size)
    return pool


# --- User operations ---


def upsert_user(
    conn: DBConnection,
    user_id: str,
    email: str | None,
    display_name: str | None,
) -> None:
    """Insert or update a user row. Called on each successful sign-in."""
    conn.execute(
        """
        INSERT INTO users (id, email, display_name)
        VALUES (%s, %s, %s)
        ON CONFLICT(id) DO UPDATE SET
            email        = excluded.email,
            display_name = excluded.display_name
        """,
        (user_id, email, display_name),
    )


def delete_user(conn: DBConnection, user_id: str) -> None:
    """Hard-delete a user and all their owned data (cascade via FK)."""
    conn.execute("DELETE FROM users WHERE id = %s", (user_id,))


# --- Ownership helpers ---


def _load_owned(
    conn: DBConnection, table: str, row_id: int, user_id: str, label: str
) -> Any:
    """SELECT * for one row owned by ``user_id``; ValueError if absent.

    Ownership is part of the WHERE clause, so another user's row is
    indistinguishable from a missing one (no existence oracle).
    """
    row = conn.execute(
        f"SELECT * FROM {table} WHERE id = %s AND user_id = %s",
        (row_id, user_id),
    ).fetchone()
    if row is None:
        raise ValueError(f"{label} {row_id} not found")
    return row


def _user_tags(conn: DBConnection, sql: str, user_id: str) -> list[str]:
    """Run a ``SELECT tags ...`` query scoped by user and return sorted uniques."""
    rows = conn.execute(sql, (user_id,)).fetchall()
    all_tags: set[str] = set()
    for row in rows:
        all_tags.update(_load_tags(row["tags"]))
    return sorted(all_tags)


# --- Resume Version operations ---


def _row_to_resume_data(row: Any) -> dict[str, Any]:
    """Convert a resume_version row to a dict with parsed resume_data and tags."""
    return {
        "id": row["id"],
        "label": row["label"],
        "is_default": bool(row["is_default"]),
        "resume_data": json.loads(row["resume_data"]),
        "tags": _load_tags(row["tags"]) if "tags" in dict(row) else [],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_resume_version(
    conn: DBConnection,
    label: str,
    resume_data: dict[str, Any],
    user_id: str,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Create a new resume version. Returns the created version."""
    row = conn.execute(
        "INSERT INTO resume_version (user_id, label, is_default, resume_data, tags) "
        "VALUES (%s, %s, 0, %s, %s) RETURNING *",
        (user_id, label, json.dumps(resume_data), json.dumps(tags or [])),
    ).fetchone()
    return _row_to_resume_data(row)


def load_resume_version(
    conn: DBConnection,
    version_id: int,
    user_id: str,
) -> dict[str, Any]:
    """Load a user's resume version by ID. Raises ValueError if not found."""
    row = _load_owned(conn, "resume_version", version_id, user_id, "Resume version")
    return _row_to_resume_data(row)


def load_resume_versions(
    conn: DBConnection,
    user_id: str,
    tags: list[str] | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    """Load a user's resume versions (app_count set to 0; populated by caller)."""
    conditions, params = build_filters(user_id, tags, q, ["label"])
    query = (
        "SELECT id, label, is_default, tags, created_at, updated_at "
        "FROM resume_version WHERE " + " AND ".join(conditions) + " ORDER BY id"
    )
    rows = conn.execute(query, params).fetchall()
    return [
        {
            "id": row["id"],
            "label": row["label"],
            "is_default": bool(row["is_default"]),
            "app_count": 0,
            "tags": _load_tags(row["tags"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def load_default_resume_version(
    conn: DBConnection,
    user_id: str,
) -> dict[str, Any]:
    """Load the user's default resume version. Raises ValueError if none."""
    row = conn.execute(
        "SELECT * FROM resume_version WHERE user_id = %s AND is_default = 1",
        (user_id,),
    ).fetchone()
    if row is None:
        raise ValueError("No default resume version found")
    return _row_to_resume_data(row)


def update_resume_version_metadata(
    conn: DBConnection,
    version_id: int,
    label: str,
    user_id: str,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Update resume version label (and optionally tags). Returns updated version."""
    _load_owned(conn, "resume_version", version_id, user_id, "Resume version")
    if tags is not None:
        conn.execute(
            "UPDATE resume_version SET label = %s, tags = %s, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = %s AND user_id = %s",
            (label, json.dumps(tags), version_id, user_id),
        )
    else:
        conn.execute(
            "UPDATE resume_version SET label = %s, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = %s AND user_id = %s",
            (label, version_id, user_id),
        )
    return load_resume_version(conn, version_id, user_id)


def update_resume_version_data(
    conn: DBConnection,
    version_id: int,
    resume_data: dict[str, Any],
    user_id: str,
) -> None:
    """Update the resume_data JSON blob for a user's version."""
    _load_owned(conn, "resume_version", version_id, user_id, "Resume version")
    conn.execute(
        "UPDATE resume_version "
        "SET resume_data = %s, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = %s AND user_id = %s",
        (json.dumps(resume_data), version_id, user_id),
    )


def delete_resume_version(
    conn: DBConnection,
    version_id: int,
    user_id: str,
) -> str:
    """Delete a user's resume version. Returns label of deleted version.

    If deleting the default and other versions exist, auto-promotes
    the most recently updated version. Rejects deleting the last version.
    Delete + promote run in one ``conn.transaction()`` block, which is a real
    transaction on an autocommit connection and a savepoint inside an
    already-open one.
    """
    row = _load_owned(conn, "resume_version", version_id, user_id, "Resume version")
    label = row["label"]
    is_default = bool(row["is_default"])

    count = conn.execute(
        "SELECT COUNT(*) AS cnt FROM resume_version WHERE user_id = %s",
        (user_id,),
    ).fetchone()["cnt"]
    if count <= 1:
        raise ValueError("Cannot delete the last remaining resume version")

    with conn.transaction():
        conn.execute(
            "DELETE FROM resume_version WHERE id = %s AND user_id = %s",
            (version_id, user_id),
        )
        if is_default:
            conn.execute(
                "UPDATE resume_version SET is_default = 1 "
                "WHERE id = ("
                "  SELECT id FROM resume_version "
                "  WHERE user_id = %s ORDER BY updated_at DESC, id DESC LIMIT 1"
                ")",
                (user_id,),
            )
    return label


def set_default_resume_version(
    conn: DBConnection,
    version_id: int,
    user_id: str,
) -> str:
    """Set a user's resume version as their default. Returns its label."""
    row = _load_owned(conn, "resume_version", version_id, user_id, "Resume version")
    conn.execute(
        "UPDATE resume_version "
        "SET is_default = CASE WHEN id = %s THEN 1 ELSE 0 END "
        "WHERE user_id = %s",
        (version_id, user_id),
    )
    return row["label"]


def load_resume_version_tags(
    conn: DBConnection,
    user_id: str,
) -> list[str]:
    """Return a sorted unique list of the user's resume version tags."""
    return _user_tags(
        conn, "SELECT tags FROM resume_version WHERE user_id = %s", user_id
    )


# --- Application operations ---


def _row_to_application(row: Any) -> dict[str, Any]:
    """Convert an application row to a dict with parsed tags."""
    d = dict(row)
    d["tags"] = _load_tags(d.get("tags"))
    return d


def create_application(
    conn: DBConnection,
    data: dict[str, Any],
    user_id: str,
) -> dict[str, Any]:
    """Create a new application. Returns the created application."""
    row = conn.execute(
        "INSERT INTO application "
        "(user_id, company, position, description, status, url, notes, tags) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (
            user_id,
            data["company"],
            data["position"],
            data.get("description") or "",
            data.get("status", "Interested"),
            data.get("url"),
            data.get("notes") or "",
            json.dumps(data.get("tags") or []),
        ),
    ).fetchone()
    return load_application(conn, row["id"], user_id)


def load_application(
    conn: DBConnection,
    app_id: int,
    user_id: str,
) -> dict[str, Any]:
    """Load a user's application by ID. Raises ValueError if not found."""
    return _row_to_application(
        _load_owned(conn, "application", app_id, user_id, "Application")
    )


def load_applications(
    conn: DBConnection,
    user_id: str,
    status: str | list[str] | None = None,
    tags: list[str] | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    """Load a user's applications with optional status/tag filter and search.

    status accepts a single status or a list; a list matches ANY of the
    given statuses (OR semantics), unlike tags which require ALL (AND).
    """
    conditions, params = build_filters(user_id, tags, q, ["company", "position"])

    statuses = [status] if isinstance(status, str) else status
    if statuses:
        placeholders = ", ".join(["%s"] * len(statuses))
        conditions.append(f"status IN ({placeholders})")
        params.extend(statuses)

    query = (
        "SELECT id, company, position, status, url, tags, created_at, updated_at "
        "FROM application WHERE "
        + " AND ".join(conditions)
        + " ORDER BY updated_at DESC"
    )
    rows = conn.execute(query, params).fetchall()
    return [_row_to_application(row) for row in rows]


def update_application(
    conn: DBConnection,
    app_id: int,
    data: dict[str, Any],
    user_id: str,
) -> dict[str, Any]:
    """Update a user's application fields. Returns updated application."""
    existing = load_application(conn, app_id, user_id)

    updatable = (
        "company",
        "position",
        "description",
        "status",
        "url",
        "notes",
    )
    sets: list[str] = []
    params: list[Any] = []
    for field in updatable:
        if field in data:
            sets.append(f"{field} = %s")
            params.append(data[field])

    if "tags" in data:
        sets.append("tags = %s")
        params.append(json.dumps(data["tags"] or []))

    if not sets:
        return existing

    sets.append("updated_at = CURRENT_TIMESTAMP")
    params.extend([app_id, user_id])

    conn.execute(
        f"UPDATE application SET {', '.join(sets)} WHERE id = %s AND user_id = %s",
        params,
    )
    return load_application(conn, app_id, user_id)


def load_application_tags(
    conn: DBConnection,
    user_id: str,
) -> list[str]:
    """Return a sorted unique list of the user's application tags."""
    return _user_tags(conn, "SELECT tags FROM application WHERE user_id = %s", user_id)


def delete_application(
    conn: DBConnection,
    app_id: int,
    user_id: str,
) -> dict[str, Any]:
    """Delete a user's application and cascade. Returns deleted app data."""
    app = load_application(conn, app_id, user_id)
    conn.execute(
        "DELETE FROM application WHERE id = %s AND user_id = %s", (app_id, user_id)
    )
    return app


# --- Communication operations ---


def _row_to_communication(row: Any) -> dict[str, Any]:
    """Convert a communication row to dict with parsed tags."""
    d = dict(row)
    d["tags"] = _load_tags(d.get("tags"))
    return d


def load_communication(
    conn: DBConnection,
    comm_id: int,
    user_id: str,
    contact_id: int | None = None,
) -> dict[str, Any]:
    """Load a communication whose parent contact belongs to ``user_id``.

    When ``contact_id`` is given the communication must also belong to that
    contact. Any mismatch raises ValueError "not found".
    """
    query = (
        "SELECT c.* FROM communication c "
        "JOIN contact ct ON c.contact_ref_id = ct.id "
        "WHERE c.id = %s AND ct.user_id = %s"
    )
    params: list[Any] = [comm_id, user_id]
    if contact_id is not None:
        query += " AND c.contact_ref_id = %s"
        params.append(contact_id)
    row = conn.execute(query, params).fetchone()
    if row is None:
        raise ValueError(f"Communication {comm_id} not found")
    return _row_to_communication(row)


def create_contact_communication(
    conn: DBConnection,
    contact_id: int,
    data: dict[str, Any],
    user_id: str,
) -> dict[str, Any]:
    """Create a communication attached to one of the user's contacts."""
    _load_owned(conn, "contact", contact_id, user_id, "Contact")
    row = conn.execute(
        "INSERT INTO communication "
        "(contact_ref_id, type, direction, subject, body, date, status, tags) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
        (
            contact_id,
            data["type"],
            data["direction"],
            data.get("subject", ""),
            data["body"],
            data["date"],
            data.get("status", "sent"),
            json.dumps(data.get("tags") or []),
        ),
    ).fetchone()
    return _row_to_communication(row)


def load_contact_communications(
    conn: DBConnection, contact_id: int, user_id: str
) -> list[dict[str, Any]]:
    """Load communications for one of the user's contacts, sorted by date desc."""
    rows = conn.execute(
        "SELECT c.* FROM communication c "
        "JOIN contact ct ON c.contact_ref_id = ct.id "
        "WHERE c.contact_ref_id = %s AND ct.user_id = %s "
        "ORDER BY c.date DESC, c.id DESC",
        (contact_id, user_id),
    ).fetchall()
    return [_row_to_communication(row) for row in rows]


def update_communication(
    conn: DBConnection,
    comm_id: int,
    data: dict[str, Any],
    user_id: str,
    contact_id: int | None = None,
) -> dict[str, Any]:
    """Update a user's communication. Returns updated communication."""
    existing = load_communication(conn, comm_id, user_id, contact_id)

    updatable = ("type", "direction", "subject", "body", "date", "status")
    sets: list[str] = []
    params: list[Any] = []
    for field in updatable:
        if field in data:
            sets.append(f"{field} = %s")
            params.append(data[field])

    if "tags" in data:
        sets.append("tags = %s")
        params.append(json.dumps(data["tags"] or []))

    if not sets:
        return existing

    params.append(comm_id)
    conn.execute(
        f"UPDATE communication SET {', '.join(sets)} WHERE id = %s",
        params,
    )
    return load_communication(conn, comm_id, user_id)


def delete_communication_owned(
    conn: DBConnection,
    comm_id: int,
    user_id: str,
    contact_id: int | None = None,
) -> str:
    """Delete a user's communication. Returns its subject."""
    comm = load_communication(conn, comm_id, user_id, contact_id)
    conn.execute("DELETE FROM communication WHERE id = %s", (comm_id,))
    return comm["subject"] or "(no subject)"


def search_communications(
    conn: DBConnection,
    user_id: str,
    q: str | None = None,
    tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Search communications attached to the user's networking contacts."""
    conditions, params = build_filters(
        user_id,
        tags,
        q,
        ["c.subject", "c.body", "ct.name"],
        user_id_column="ct.user_id",
        tags_column="c.tags",
    )
    query = (
        "SELECT c.id, c.contact_ref_id, c.type, c.direction, c.subject, "
        "c.body, c.date, c.status, c.tags, c.created_at, "
        "'contact' AS parent_type, "
        "c.contact_ref_id AS parent_id, "
        "ct.name AS parent_name "
        "FROM communication c "
        "JOIN contact ct ON c.contact_ref_id = ct.id "
        "WHERE "
        + " AND ".join(conditions)
        + " ORDER BY c.date DESC, c.id DESC LIMIT 200"
    )
    rows = conn.execute(query, params).fetchall()
    return [_row_to_communication(row) for row in rows]


def load_communication_tags(
    conn: DBConnection,
    user_id: str,
) -> list[str]:
    """Return sorted unique tags across the user's communications."""
    return _user_tags(
        conn,
        "SELECT c.tags FROM communication c "
        "JOIN contact ct ON c.contact_ref_id = ct.id "
        "WHERE ct.user_id = %s",
        user_id,
    )


# --- Accomplishment operations ---


def _dt(value: Any) -> Any:
    """Return ISO string if value is a datetime/date, otherwise return as-is."""
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    return value


def _row_to_accomplishment(row: Any) -> dict[str, Any]:
    """Convert an accomplishment row to a dict with parsed tags."""
    return {
        "id": row["id"],
        "title": row["title"],
        "situation": row["situation"],
        "task": row["task"],
        "action": row["action"],
        "result": row["result"],
        "accomplishment_date": _dt(row["accomplishment_date"]),
        "tags": _load_tags(row["tags"]),
        "created_at": _dt(row["created_at"]),
        "updated_at": _dt(row["updated_at"]),
    }


def _row_to_accomplishment_summary(row: Any) -> dict[str, Any]:
    """Convert an accomplishment row to a summary dict (no STAR body)."""
    return {
        "id": row["id"],
        "title": row["title"],
        "accomplishment_date": _dt(row["accomplishment_date"]),
        "tags": _load_tags(row["tags"]),
        "created_at": _dt(row["created_at"]),
        "updated_at": _dt(row["updated_at"]),
    }


def create_accomplishment(
    conn: DBConnection,
    data: dict[str, Any],
    user_id: str,
) -> dict[str, Any]:
    """Insert a new accomplishment row and return it."""
    row = conn.execute(
        "INSERT INTO accomplishment "
        "(user_id, title, situation, task, action, result, accomplishment_date, tags) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
        (
            user_id,
            data["title"],
            data.get("situation", ""),
            data.get("task", ""),
            data.get("action", ""),
            data.get("result", ""),
            data.get("accomplishment_date"),
            json.dumps(data.get("tags") or []),
        ),
    ).fetchone()
    return _row_to_accomplishment(row)


def load_accomplishment(
    conn: DBConnection,
    acc_id: int,
    user_id: str,
) -> dict[str, Any]:
    """Load a user's accomplishment by ID. Raises ValueError if not found."""
    return _row_to_accomplishment(
        _load_owned(conn, "accomplishment", acc_id, user_id, "Accomplishment")
    )


def load_accomplishments(
    conn: DBConnection,
    user_id: str,
    tags: list[str] | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    """List a user's accomplishments reverse-chronologically with filters."""
    conditions, params = build_filters(
        user_id, tags, q, ["title", "situation", "task", "action", "result"]
    )
    query = (
        "SELECT id, title, accomplishment_date, tags, created_at, updated_at "
        "FROM accomplishment WHERE " + " AND ".join(conditions) + " ORDER BY "
        "CASE WHEN accomplishment_date IS NULL THEN 1 ELSE 0 END, "
        "accomplishment_date DESC, "
        "created_at DESC"
    )
    rows = conn.execute(query, params).fetchall()
    return [_row_to_accomplishment_summary(row) for row in rows]


def update_accomplishment(
    conn: DBConnection,
    acc_id: int,
    data: dict[str, Any],
    user_id: str,
) -> dict[str, Any]:
    """Patch a user's accomplishment. Raises ValueError if not found."""
    existing = load_accomplishment(conn, acc_id, user_id)

    updatable = (
        "title",
        "situation",
        "task",
        "action",
        "result",
        "accomplishment_date",
    )
    sets: list[str] = []
    params: list[Any] = []

    for field in updatable:
        if field in data:
            sets.append(f"{field} = %s")
            params.append(data[field])

    if "tags" in data:
        sets.append("tags = %s")
        params.append(json.dumps(data["tags"] or []))

    if not sets:
        return existing

    sets.append("updated_at = CURRENT_TIMESTAMP")
    params.extend([acc_id, user_id])

    conn.execute(
        f"UPDATE accomplishment SET {', '.join(sets)} WHERE id = %s AND user_id = %s",
        params,
    )
    return load_accomplishment(conn, acc_id, user_id)


def delete_accomplishment(
    conn: DBConnection,
    acc_id: int,
    user_id: str,
) -> dict[str, Any]:
    """Delete a user's accomplishment. Returns the deleted row."""
    acc = load_accomplishment(conn, acc_id, user_id)
    conn.execute(
        "DELETE FROM accomplishment WHERE id = %s AND user_id = %s", (acc_id, user_id)
    )
    return acc


def load_accomplishment_tags(
    conn: DBConnection,
    user_id: str,
) -> list[str]:
    """Return a sorted unique list of the user's accomplishment tags."""
    return _user_tags(
        conn, "SELECT tags FROM accomplishment WHERE user_id = %s", user_id
    )


# --- Note operations ---


def _row_to_note(row: Any) -> dict[str, Any]:
    """Full note with content."""
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "title": row["title"],
        "content": row["content"],
        "tags": _load_tags(row["tags"]),
        "created_at": _dt(row["created_at"]),
        "updated_at": _dt(row["updated_at"]),
    }


def _row_to_note_summary(row: Any) -> dict[str, Any]:
    """Summary for list view (content omitted)."""
    return {
        "id": row["id"],
        "title": row["title"],
        "tags": _load_tags(row["tags"]),
        "created_at": _dt(row["created_at"]),
        "updated_at": _dt(row["updated_at"]),
    }


def create_note(
    conn: DBConnection,
    data: dict[str, Any],
    user_id: str,
) -> dict[str, Any]:
    """Insert a new note row and return it."""
    row = conn.execute(
        "INSERT INTO note (user_id, title, content, tags) "
        "VALUES (%s, %s, %s, %s) RETURNING *",
        (
            user_id,
            data["title"],
            data.get("content", ""),
            json.dumps(data.get("tags") or []),
        ),
    ).fetchone()
    return _row_to_note(row)


def load_note(
    conn: DBConnection,
    note_id: int,
    user_id: str,
) -> dict[str, Any]:
    """Load a user's note by ID. Raises ValueError if not found."""
    return _row_to_note(_load_owned(conn, "note", note_id, user_id, "Note"))


def load_notes(
    conn: DBConnection,
    user_id: str,
    tags: list[str] | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    """List a user's notes as summaries ordered by updated_at DESC."""
    conditions, params = build_filters(user_id, tags, q, ["title", "content"])
    query = (
        "SELECT id, title, tags, created_at, updated_at FROM note WHERE "
        + " AND ".join(conditions)
        + " ORDER BY updated_at DESC"
    )
    rows = conn.execute(query, params).fetchall()
    return [_row_to_note_summary(row) for row in rows]


def update_note(
    conn: DBConnection,
    note_id: int,
    data: dict[str, Any],
    user_id: str,
) -> dict[str, Any]:
    """Patch a user's note. Raises ValueError if not found."""
    existing = load_note(conn, note_id, user_id)

    updatable = ("title", "content")
    sets: list[str] = []
    params: list[Any] = []

    for field in updatable:
        if field in data:
            sets.append(f"{field} = %s")
            params.append(data[field])

    if "tags" in data:
        sets.append("tags = %s")
        params.append(json.dumps(data["tags"] or []))

    if not sets:
        return existing

    sets.append("updated_at = CURRENT_TIMESTAMP")
    params.extend([note_id, user_id])

    conn.execute(
        f"UPDATE note SET {', '.join(sets)} WHERE id = %s AND user_id = %s",
        params,
    )
    return load_note(conn, note_id, user_id)


def delete_note(
    conn: DBConnection,
    note_id: int,
    user_id: str,
) -> dict[str, Any]:
    """Delete a user's note. Returns the deleted row."""
    note = load_note(conn, note_id, user_id)
    conn.execute("DELETE FROM note WHERE id = %s AND user_id = %s", (note_id, user_id))
    return note


def load_note_tags(
    conn: DBConnection,
    user_id: str,
) -> list[str]:
    """Return a sorted unique list of the user's note tags."""
    return _user_tags(conn, "SELECT tags FROM note WHERE user_id = %s", user_id)


# --- Contact operations ---

_CONTACT_FIELDS = (
    "email",
    "phone",
    "company",
    "title",
    "relationship",
    "linkedin_url",
    "location",
    "last_contacted_date",
    "followup_date",
    "notes",
)


def _row_to_contact(row: Any) -> dict[str, Any]:
    """Full contact with notes."""
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "name": row["name"],
        "email": row["email"],
        "phone": row["phone"],
        "company": row["company"],
        "title": row["title"],
        "relationship": row["relationship"],
        "linkedin_url": row["linkedin_url"],
        "location": row["location"],
        "last_contacted_date": row["last_contacted_date"],
        "followup_date": row["followup_date"],
        "notes": row["notes"],
        "tags": _load_tags(row["tags"]),
        "created_at": _dt(row["created_at"]),
        "updated_at": _dt(row["updated_at"]),
    }


def _row_to_contact_summary(row: Any) -> dict[str, Any]:
    """Summary for list view (notes omitted)."""
    return {
        "id": row["id"],
        "name": row["name"],
        "company": row["company"],
        "title": row["title"],
        "relationship": row["relationship"],
        "followup_date": row["followup_date"],
        "tags": _load_tags(row["tags"]),
        "updated_at": _dt(row["updated_at"]),
    }


def create_contact(
    conn: DBConnection,
    data: dict[str, Any],
    user_id: str,
) -> dict[str, Any]:
    """Insert a new contact row and return it."""
    row = conn.execute(
        "INSERT INTO contact "
        "(user_id, name, email, phone, company, title, relationship, "
        "linkedin_url, location, last_contacted_date, followup_date, notes, tags) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
        (
            user_id,
            data["name"],
            data.get("email"),
            data.get("phone"),
            data.get("company"),
            data.get("title"),
            data.get("relationship"),
            data.get("linkedin_url"),
            data.get("location"),
            data.get("last_contacted_date"),
            data.get("followup_date"),
            data.get("notes", ""),
            json.dumps(data.get("tags") or []),
        ),
    ).fetchone()
    return _row_to_contact(row)


def load_contact(
    conn: DBConnection,
    contact_id: int,
    user_id: str,
) -> dict[str, Any]:
    """Load a user's contact by ID. Raises ValueError if not found."""
    return _row_to_contact(_load_owned(conn, "contact", contact_id, user_id, "Contact"))


def load_contacts(
    conn: DBConnection,
    user_id: str,
    tags: list[str] | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    """List a user's contacts as summaries ordered by updated_at DESC."""
    conditions, params = build_filters(
        user_id, tags, q, ["name", "company", "title", "notes"]
    )
    query = (
        "SELECT id, name, company, title, relationship, "
        "followup_date, tags, updated_at FROM contact WHERE "
        + " AND ".join(conditions)
        + " ORDER BY updated_at DESC"
    )
    rows = conn.execute(query, params).fetchall()
    return [_row_to_contact_summary(row) for row in rows]


def update_contact(
    conn: DBConnection,
    contact_id: int,
    data: dict[str, Any],
    user_id: str,
) -> dict[str, Any]:
    """Patch a user's contact. Raises ValueError if not found."""
    existing = load_contact(conn, contact_id, user_id)

    updatable = ("name",) + _CONTACT_FIELDS
    sets: list[str] = []
    params: list[Any] = []

    for field in updatable:
        if field in data:
            sets.append(f"{field} = %s")
            params.append(data[field])

    if "tags" in data:
        sets.append("tags = %s")
        params.append(json.dumps(data["tags"] or []))

    if not sets:
        return existing

    sets.append("updated_at = CURRENT_TIMESTAMP")
    params.extend([contact_id, user_id])

    conn.execute(
        f"UPDATE contact SET {', '.join(sets)} WHERE id = %s AND user_id = %s",
        params,
    )
    return load_contact(conn, contact_id, user_id)


def delete_contact(
    conn: DBConnection,
    contact_id: int,
    user_id: str,
) -> dict[str, Any]:
    """Delete a user's contact. Returns the deleted row."""
    contact = load_contact(conn, contact_id, user_id)
    conn.execute(
        "DELETE FROM contact WHERE id = %s AND user_id = %s", (contact_id, user_id)
    )
    return contact


def load_contact_tags(
    conn: DBConnection,
    user_id: str,
) -> list[str]:
    """Return a sorted unique list of the user's contact tags."""
    return _user_tags(conn, "SELECT tags FROM contact WHERE user_id = %s", user_id)


# --- Resource Link operations ---


def link_insert(
    conn: DBConnection,
    left_type: str,
    left_id: int,
    right_type: str,
    right_id: int,
    user_id: str,
) -> None:
    """Insert a canonical resource_link row. No-op if already exists."""
    conn.execute(
        "INSERT INTO resource_link (left_type, left_id, right_type, right_id, user_id) "
        "VALUES (%s, %s, %s, %s, %s) "
        "ON CONFLICT (left_type, left_id, right_type, right_id) DO NOTHING",
        (left_type, left_id, right_type, right_id, user_id),
    )


def link_delete(
    conn: DBConnection,
    left_type: str,
    left_id: int,
    right_type: str,
    right_id: int,
    user_id: str,
) -> None:
    """Delete a canonical resource_link row."""
    conn.execute(
        "DELETE FROM resource_link "
        "WHERE left_type = %s AND left_id = %s "
        "AND right_type = %s AND right_id = %s AND user_id = %s",
        (left_type, left_id, right_type, right_id, user_id),
    )


def links_for_resource(
    conn: DBConnection,
    resource_type: str,
    resource_id: int,
    user_id: str,
) -> list[dict[str, Any]]:
    """Return all (other_type, other_id) linked to this resource for this user."""
    rows = conn.execute(
        "SELECT right_type AS other_type, right_id AS other_id "
        "FROM resource_link "
        "WHERE user_id = %s AND left_type = %s AND left_id = %s "
        "UNION ALL "
        "SELECT left_type AS other_type, left_id AS other_id "
        "FROM resource_link "
        "WHERE user_id = %s AND right_type = %s AND right_id = %s",
        (user_id, resource_type, resource_id, user_id, resource_type, resource_id),
    ).fetchall()
    return [{"other_type": r["other_type"], "other_id": r["other_id"]} for r in rows]


def load_all_links(conn: DBConnection, user_id: str) -> list[dict[str, Any]]:
    """Return every link owned by a user, in canonical (left, right) form."""
    rows = conn.execute(
        "SELECT left_type, left_id, right_type, right_id, created_at "
        "FROM resource_link WHERE user_id = %s "
        "ORDER BY left_type, left_id, right_type, right_id",
        (user_id,),
    ).fetchall()
    return [
        {
            "left_type": r["left_type"],
            "left_id": r["left_id"],
            "right_type": r["right_type"],
            "right_id": r["right_id"],
            "created_at": _dt(r["created_at"]),
        }
        for r in rows
    ]


def link_counts(
    conn: DBConnection,
    resource_type: str,
    resource_ids: list[int],
    user_id: str,
) -> dict[int, int]:
    """Return {resource_id: count} for all linked resources in bulk."""
    if not resource_ids:
        return {}
    rows = conn.execute(
        "SELECT resource_id, COUNT(*) AS cnt FROM ("
        "  SELECT left_id AS resource_id FROM resource_link "
        "  WHERE user_id = %s AND left_type = %s AND left_id = ANY(%s) "
        "  UNION ALL "
        "  SELECT right_id AS resource_id FROM resource_link "
        "  WHERE user_id = %s AND right_type = %s AND right_id = ANY(%s)"
        ") t GROUP BY resource_id",
        (user_id, resource_type, resource_ids, user_id, resource_type, resource_ids),
    ).fetchall()
    return {r["resource_id"]: r["cnt"] for r in rows}


def link_counts_by_type(
    conn: DBConnection,
    resource_type: str,
    resource_ids: list[int],
    other_type: str,
    user_id: str,
) -> dict[int, int]:
    """Return {resource_id: count} filtered to links with a specific other_type."""
    if not resource_ids:
        return {}
    rows = conn.execute(
        "SELECT resource_id, COUNT(*) AS cnt FROM ("
        "  SELECT left_id AS resource_id FROM resource_link "
        "  WHERE user_id = %s AND left_type = %s AND left_id = ANY(%s) "
        "  AND right_type = %s "
        "  UNION ALL "
        "  SELECT right_id AS resource_id FROM resource_link "
        "  WHERE user_id = %s AND right_type = %s AND right_id = ANY(%s) "
        "  AND left_type = %s"
        ") t GROUP BY resource_id",
        (
            user_id,
            resource_type,
            resource_ids,
            other_type,
            user_id,
            resource_type,
            resource_ids,
            other_type,
        ),
    ).fetchall()
    return {r["resource_id"]: r["cnt"] for r in rows}


def unlink_all_for(
    conn: DBConnection,
    resource_type: str,
    resource_id: int,
    user_id: str,
) -> None:
    """Delete all resource_link rows for this resource (both directions)."""
    conn.execute(
        "DELETE FROM resource_link "
        "WHERE user_id = %s "
        "AND ((left_type = %s AND left_id = %s) "
        "OR (right_type = %s AND right_id = %s))",
        (user_id, resource_type, resource_id, resource_type, resource_id),
    )
