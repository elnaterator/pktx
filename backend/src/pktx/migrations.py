"""Schema migration framework using schema_version table (PostgreSQL)."""

import json
import logging

from psycopg.rows import dict_row

logger = logging.getLogger("pktx")


class SchemaVersionError(Exception):
    """Database schema version is newer than code supports."""

    def __init__(self, db_version: int, code_version: int) -> None:
        self.db_version = db_version
        self.code_version = code_version
        super().__init__(
            f"Database schema version {db_version} is newer than "
            f"code version {code_version}. Please upgrade the application."
        )


class MigrationError(Exception):
    """A schema migration failed."""

    def __init__(self, from_version: int, to_version: int, cause: Exception) -> None:
        self.from_version = from_version
        self.to_version = to_version
        super().__init__(
            f"Migration from version {from_version} to {to_version} failed: {cause}"
        )
        self.__cause__ = cause


def _bootstrap_schema_version(conn) -> None:
    """Create schema_version table if it doesn't exist and seed with version 0."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    row = conn.execute("SELECT COUNT(*) AS cnt FROM schema_version").fetchone()
    count = row["cnt"] if isinstance(row, dict) else row[0]
    if count == 0:
        conn.execute("INSERT INTO schema_version (version) VALUES (0)")
    conn.commit()


def _get_version(conn) -> int:
    """Read current schema version."""
    row = conn.execute("SELECT MAX(version) AS version FROM schema_version").fetchone()
    if row is None:
        return 0
    version = row["version"] if isinstance(row, dict) else row[0]
    return version if version is not None else 0


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = %s",
        (name,),
    ).fetchone()
    return row is not None


def _column_exists(conn, table: str, column: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s AND column_name = %s",
        (table, column),
    ).fetchone()
    return row is not None


def _detect_actual_version(conn) -> int:
    """Infer the highest applied migration from the DB structure.

    Used to repair schema_version when it lags behind the actual DB state
    (e.g. after a partial migration failure with autocommit mode).
    Checked newest-to-oldest; returns the first version whose structural
    marker is present.
    """
    if _table_exists(conn, "oauth_kv"):
        return 13
    if (
        _table_exists(conn, "resource_link")
        and not _column_exists(conn, "communication", "app_id")
        and not _column_exists(conn, "application", "resume_version_id")
    ):
        return 12
    if _table_exists(conn, "resource_link") and not _column_exists(
        conn, "communication", "app_id"
    ):
        return 11
    if _table_exists(conn, "resource_link"):
        return 10
    if _column_exists(conn, "communication", "contact_ref_id"):
        return 9
    if _table_exists(conn, "contact") and _column_exists(conn, "contact", "user_id"):
        return 8
    if _column_exists(conn, "application", "tags"):
        return 7
    if _table_exists(conn, "note"):
        return 6
    if _table_exists(conn, "users") and _column_exists(
        conn, "resume_version", "user_id"
    ):
        return 4  # v5 is data-only; safe to re-run from v4
    if _table_exists(conn, "accomplishment"):
        return 3
    if _table_exists(conn, "resume_version"):
        return 2
    if _table_exists(conn, "experience"):
        return 1
    return 0


def migrate_v0_to_v1(conn) -> None:
    """Initial schema: create all tables."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS contact (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            name TEXT,
            email TEXT,
            phone TEXT,
            location TEXT,
            linkedin TEXT,
            website TEXT,
            github TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS summary (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            text TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS experience (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            start_date TEXT,
            end_date TEXT,
            location TEXT,
            highlights TEXT NOT NULL DEFAULT '[]',
            position INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS education (
            id SERIAL PRIMARY KEY,
            institution TEXT NOT NULL,
            degree TEXT NOT NULL,
            field TEXT,
            start_date TEXT,
            end_date TEXT,
            honors TEXT,
            position INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS skill (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL DEFAULT 'Other'
        )
        """
    )
    conn.execute(
        "UPDATE schema_version SET version = %s",
        (1,),
    )
    conn.commit()


def migrate_v1_to_v2(conn) -> None:
    """Replace singleton resume tables with resume_version + application tables."""
    conn.execute(
        """
        CREATE TABLE resume_version (
            id SERIAL PRIMARY KEY,
            label TEXT NOT NULL,
            is_default INTEGER NOT NULL DEFAULT 0,
            resume_data TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE application (
            id SERIAL PRIMARY KEY,
            company TEXT NOT NULL,
            position TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Interested',
            url TEXT,
            notes TEXT NOT NULL DEFAULT '',
            resume_version_id INTEGER REFERENCES resume_version(id)
                ON DELETE SET NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE application_contact (
            id SERIAL PRIMARY KEY,
            app_id INTEGER NOT NULL REFERENCES application(id)
                ON DELETE CASCADE,
            name TEXT NOT NULL,
            role TEXT,
            email TEXT,
            phone TEXT,
            notes TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE communication (
            id SERIAL PRIMARY KEY,
            app_id INTEGER NOT NULL REFERENCES application(id)
                ON DELETE CASCADE,
            contact_id INTEGER REFERENCES application_contact(id)
                ON DELETE SET NULL,
            contact_name TEXT,
            type TEXT NOT NULL,
            direction TEXT NOT NULL,
            subject TEXT NOT NULL DEFAULT '',
            body TEXT NOT NULL,
            date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'sent',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX idx_application_status ON application(status)")
    conn.execute("CREATE INDEX idx_application_updated ON application(updated_at DESC)")
    conn.execute(
        "CREATE INDEX idx_application_contact_app ON application_contact(app_id)"
    )
    conn.execute("CREATE INDEX idx_communication_app ON communication(app_id)")
    conn.execute("CREATE INDEX idx_communication_date ON communication(date DESC)")
    conn.execute(
        "CREATE INDEX idx_resume_version_default "
        "ON resume_version(is_default) WHERE is_default = 1"
    )

    # Migrate existing resume data into default version
    resume_data: dict = {
        "contact": {},
        "summary": "",
        "experience": [],
        "education": [],
        "skills": [],
    }

    row = conn.execute("SELECT * FROM contact WHERE id = 1").fetchone()
    if row:
        contact_keys = (
            "name",
            "email",
            "phone",
            "location",
            "linkedin",
            "website",
            "github",
        )
        for key in contact_keys:
            resume_data["contact"][key] = row[key]

    row = conn.execute("SELECT text FROM summary WHERE id = 1").fetchone()
    if row:
        resume_data["summary"] = row[0] or ""

    rows = conn.execute("SELECT * FROM experience ORDER BY position").fetchall()
    for row in rows:
        resume_data["experience"].append(
            {
                "title": row["title"],
                "company": row["company"],
                "start_date": row["start_date"],
                "end_date": row["end_date"],
                "location": row["location"],
                "highlights": json.loads(row["highlights"]),
            }
        )

    rows = conn.execute("SELECT * FROM education ORDER BY position").fetchall()
    for row in rows:
        resume_data["education"].append(
            {
                "institution": row["institution"],
                "degree": row["degree"],
                "field": row["field"],
                "start_date": row["start_date"],
                "end_date": row["end_date"],
                "honors": row["honors"],
            }
        )

    rows = conn.execute("SELECT * FROM skill ORDER BY id").fetchall()
    for row in rows:
        resume_data["skills"].append({"name": row["name"], "category": row["category"]})

    conn.execute(
        "INSERT INTO resume_version (label, is_default, resume_data) "
        "VALUES (%s, 1, %s)",
        ("Default Resume", json.dumps(resume_data)),
    )

    # Drop old tables
    conn.execute("DROP TABLE IF EXISTS skill CASCADE")
    conn.execute("DROP TABLE IF EXISTS education CASCADE")
    conn.execute("DROP TABLE IF EXISTS experience CASCADE")
    conn.execute("DROP TABLE IF EXISTS summary CASCADE")
    conn.execute("DROP TABLE IF EXISTS contact CASCADE")

    conn.execute("UPDATE schema_version SET version = %s", (2,))
    conn.commit()


def migrate_v2_to_v3(conn) -> None:
    """Add accomplishment table with STAR fields and tags."""
    conn.execute(
        """
        CREATE TABLE accomplishment (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            situation TEXT NOT NULL DEFAULT '',
            task TEXT NOT NULL DEFAULT '',
            action TEXT NOT NULL DEFAULT '',
            result TEXT NOT NULL DEFAULT '',
            accomplishment_date TEXT,
            tags TEXT NOT NULL DEFAULT '[]',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "CREATE INDEX idx_accomplishment_date "
        "ON accomplishment(accomplishment_date DESC)"
    )
    conn.execute(
        "CREATE INDEX idx_accomplishment_created ON accomplishment(created_at DESC)"
    )
    conn.execute("UPDATE schema_version SET version = %s", (3,))
    conn.commit()


def migrate_v3_to_v4(conn) -> None:
    """Add users table and thread user_id FK into owned tables."""
    conn.execute(
        """
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            email TEXT,
            display_name TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("INSERT INTO users (id) VALUES ('legacy')")

    # resume_version: add user_id column, backfill, add FK constraint
    conn.execute("ALTER TABLE resume_version ADD COLUMN user_id TEXT")
    conn.execute("UPDATE resume_version SET user_id = 'legacy'")
    conn.execute("ALTER TABLE resume_version ALTER COLUMN user_id SET NOT NULL")
    conn.execute(
        "ALTER TABLE resume_version ADD CONSTRAINT fk_rv_user "
        "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE"
    )

    # application: add user_id column, backfill, add FK constraint
    conn.execute("ALTER TABLE application ADD COLUMN user_id TEXT")
    conn.execute("UPDATE application SET user_id = 'legacy'")
    conn.execute("ALTER TABLE application ALTER COLUMN user_id SET NOT NULL")
    conn.execute(
        "ALTER TABLE application ADD CONSTRAINT fk_app_user "
        "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE"
    )

    # accomplishment: add user_id column, backfill, add FK constraint
    conn.execute("ALTER TABLE accomplishment ADD COLUMN user_id TEXT")
    conn.execute("UPDATE accomplishment SET user_id = 'legacy'")
    conn.execute("ALTER TABLE accomplishment ALTER COLUMN user_id SET NOT NULL")
    conn.execute(
        "ALTER TABLE accomplishment ADD CONSTRAINT fk_acc_user "
        "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE"
    )

    # Add new indexes
    conn.execute("CREATE INDEX idx_resume_version_user ON resume_version(user_id)")
    conn.execute(
        "CREATE INDEX idx_resume_version_user_default "
        "ON resume_version(user_id, is_default) WHERE is_default = 1"
    )
    conn.execute("CREATE INDEX idx_application_user ON application(user_id)")
    conn.execute("CREATE INDEX idx_accomplishment_user ON accomplishment(user_id)")

    conn.execute("UPDATE schema_version SET version = %s", (4,))
    conn.commit()


def migrate_v4_to_v5(conn) -> None:
    """Flatten items-based skills into individual flat skill entries.

    Prior to this migration, skills could be stored as:
      {"name": "Languages", "category": "Other", "items": ["Python", "TypeScript"]}

    After this migration, each skill has exactly one name and one category:
      {"name": "Python", "category": "Languages"}
      {"name": "TypeScript", "category": "Languages"}

    Skills with no items (or empty items) are preserved with the items field stripped.
    """
    rows = conn.execute("SELECT id, resume_data FROM resume_version").fetchall()
    for row in rows:
        version_id = row["id"] if isinstance(row, dict) else row[0]
        resume_data_str = row["resume_data"] if isinstance(row, dict) else row[1]
        resume_data = json.loads(resume_data_str)

        old_skills = resume_data.get("skills", [])
        new_skills: list[dict] = []
        for skill in old_skills:
            items = skill.get("items", [])
            if items:
                # Each item becomes a flat skill; the old name becomes the category
                category = skill.get("name", "Other")
                for item in items:
                    new_skills.append({"name": item, "category": category})
            else:
                # Keep as-is, strip the items field
                new_skills.append(
                    {"name": skill["name"], "category": skill.get("category", "Other")}
                )

        resume_data["skills"] = new_skills
        conn.execute(
            "UPDATE resume_version SET resume_data = %s WHERE id = %s",
            (json.dumps(resume_data), version_id),
        )

    conn.execute("UPDATE schema_version SET version = %s", (5,))
    conn.commit()


def migrate_v5_to_v6(conn) -> None:
    """Add note table for personal context notes."""
    conn.execute(
        """
        CREATE TABLE note (
            id          SERIAL PRIMARY KEY,
            user_id     TEXT NOT NULL,
            title       TEXT NOT NULL,
            content     TEXT NOT NULL DEFAULT '',
            tags        TEXT NOT NULL DEFAULT '[]',
            created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_note_user FOREIGN KEY (user_id)
                REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute("CREATE INDEX idx_note_user ON note(user_id)")
    conn.execute("CREATE INDEX idx_note_updated ON note(updated_at DESC)")
    conn.execute("UPDATE schema_version SET version = %s", (6,))
    conn.commit()


def migrate_v6_to_v7(conn) -> None:
    """Add tags column to application and resume_version tables."""
    conn.execute("ALTER TABLE application ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'")
    conn.execute(
        "ALTER TABLE resume_version ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'"
    )
    conn.execute("UPDATE schema_version SET version = %s", (7,))
    conn.commit()


def migrate_v7_to_v8(conn) -> None:
    """Add contact table for networking/relationship contacts."""
    # The v0→v1 migration creates a singleton 'contact' table with the old
    # resume-contact schema. If v0→v1 was accidentally re-run (bootstrap bug),
    # that old table may still exist here. Drop it before creating the new one.
    conn.execute("DROP TABLE IF EXISTS contact CASCADE")
    conn.execute(
        """
        CREATE TABLE contact (
            id                    SERIAL PRIMARY KEY,
            user_id               TEXT NOT NULL,
            name                  TEXT NOT NULL,
            email                 TEXT,
            phone                 TEXT,
            company               TEXT,
            title                 TEXT,
            relationship          TEXT,
            linkedin_url          TEXT,
            location              TEXT,
            last_contacted_date   TEXT,
            followup_date         TEXT,
            notes                 TEXT NOT NULL DEFAULT '',
            tags                  TEXT NOT NULL DEFAULT '[]',
            created_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_contact_user FOREIGN KEY (user_id)
                REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute("CREATE INDEX idx_contact_user ON contact(user_id)")
    conn.execute("CREATE INDEX idx_contact_updated ON contact(updated_at DESC)")
    conn.execute(
        "CREATE INDEX idx_contact_followup ON contact(followup_date) "
        "WHERE followup_date IS NOT NULL"
    )
    conn.execute("UPDATE schema_version SET version = %s", (8,))
    conn.commit()


def migrate_v8_to_v9(conn) -> None:
    """Generalize communication table: nullable app_id, add contact_ref_id + tags."""
    conn.execute("ALTER TABLE communication ALTER COLUMN app_id DROP NOT NULL")
    conn.execute(
        "ALTER TABLE communication ADD COLUMN contact_ref_id INTEGER "
        "REFERENCES contact(id) ON DELETE CASCADE"
    )
    conn.execute("ALTER TABLE communication ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'")
    conn.execute(
        "ALTER TABLE communication ADD CONSTRAINT communication_parent_xor CHECK ("
        "(app_id IS NOT NULL AND contact_ref_id IS NULL) OR "
        "(app_id IS NULL AND contact_ref_id IS NOT NULL)"
        ")"
    )
    conn.execute(
        "CREATE INDEX idx_communication_contact_ref ON communication(contact_ref_id)"
    )
    conn.execute("UPDATE schema_version SET version = %s", (9,))
    conn.commit()


def migrate_v9_to_v10(conn) -> None:
    """Add resource_link table for polymorphic cross-resource linking."""
    conn.execute(
        """
        CREATE TABLE resource_link (
            left_type   TEXT NOT NULL,
            left_id     INTEGER NOT NULL,
            right_type  TEXT NOT NULL,
            right_id    INTEGER NOT NULL,
            user_id     TEXT NOT NULL,
            created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (left_type, left_id, right_type, right_id),
            CONSTRAINT resource_link_no_self CHECK (
                (left_type, left_id) <> (right_type, right_id)
            ),
            CONSTRAINT resource_link_left_type_valid CHECK (
                left_type IN ('application','accomplishment','resume','note','contact')
            ),
            CONSTRAINT resource_link_right_type_valid CHECK (
                right_type IN ('application','accomplishment','resume','note','contact')
            ),
            CONSTRAINT resource_link_canonical CHECK (
                left_type < right_type
                OR (left_type = right_type AND left_id < right_id)
            ),
            CONSTRAINT fk_resource_link_user FOREIGN KEY (user_id)
                REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX idx_link_user_left ON resource_link(user_id, left_type, left_id)"
    )
    conn.execute(
        "CREATE INDEX idx_link_user_right "
        "ON resource_link(user_id, right_type, right_id)"
    )
    conn.execute("UPDATE schema_version SET version = %s", (10,))
    conn.commit()


def migrate_v10_to_v11(conn) -> None:
    """Drop application-scoped contacts and communications.

    Removes the application_contact table and the app-related columns on
    communication (app_id, contact_id, contact_name). Communications now
    only attach to networking contacts; cross-resource relations to
    applications are expressed via resource_link.
    """
    # Drop the parent-XOR check constraint before columns it references.
    conn.execute(
        "ALTER TABLE communication DROP CONSTRAINT IF EXISTS communication_parent_xor"
    )
    # Purge app-only communications (they have no contact_ref_id).
    conn.execute("DELETE FROM communication WHERE contact_ref_id IS NULL")
    # Drop indexes on dropped columns / table.
    conn.execute("DROP INDEX IF EXISTS idx_application_contact_app")
    conn.execute("DROP INDEX IF EXISTS idx_communication_app")
    conn.execute("DROP INDEX IF EXISTS idx_communication_date")
    # Drop application-scoped columns.
    conn.execute("ALTER TABLE communication DROP COLUMN IF EXISTS app_id")
    conn.execute("ALTER TABLE communication DROP COLUMN IF EXISTS contact_id")
    conn.execute("ALTER TABLE communication DROP COLUMN IF EXISTS contact_name")
    # Tighten contact_ref_id now that it's the only parent.
    conn.execute("ALTER TABLE communication ALTER COLUMN contact_ref_id SET NOT NULL")
    # Drop the application_contact table itself.
    conn.execute("DROP TABLE IF EXISTS application_contact CASCADE")
    conn.execute("UPDATE schema_version SET version = %s", (11,))
    conn.commit()


def migrate_v11_to_v12(conn) -> None:
    """Backfill application.resume_version_id into resource_link, then drop it."""
    conn.execute(
        "INSERT INTO resource_link "
        "(left_type, left_id, right_type, right_id, user_id) "
        "SELECT 'application', id, 'resume', resume_version_id, user_id "
        "FROM application WHERE resume_version_id IS NOT NULL "
        "ON CONFLICT (left_type, left_id, right_type, right_id) DO NOTHING"
    )
    conn.execute("ALTER TABLE application DROP COLUMN resume_version_id")
    conn.execute("UPDATE schema_version SET version = %s", (12,))
    conn.commit()


def migrate_v12_to_v13(conn) -> None:
    """Add oauth_kv table for FastMCP OAuth-proxy shared state (plan 017).

    Backs the DCR proxy's key-value storage (client registrations, encrypted
    upstream tokens, JTI mappings, transient authorize state) so it is shared
    across serverless instances instead of a per-instance local DiskStore.
    """
    conn.execute(
        """
        CREATE TABLE oauth_kv (
            collection  TEXT NOT NULL,
            key         TEXT NOT NULL,
            value       TEXT NOT NULL,
            expires_at  TIMESTAMPTZ,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (collection, key)
        )
        """
    )
    conn.execute(
        "CREATE INDEX idx_oauth_kv_expires ON oauth_kv(expires_at) "
        "WHERE expires_at IS NOT NULL"
    )
    conn.execute("UPDATE schema_version SET version = %s", (13,))
    conn.commit()


_TAGGED_TABLES = (
    "resume_version",
    "application",
    "accomplishment",
    "note",
    "contact",
    "communication",
)


def _normalize_http_url(value: object) -> str | None:
    """Frozen copy of 027's URL rule: absolute http(s) URL, or ``None``.

    Bare hosts (``linkedin.com/in/jane``) get ``https://`` prepended so v14
    keeps them; only values that are still not a web URL (``javascript:``,
    ``data:``, ``mailto:``…) are dropped. Kept local so later changes to
    ``pktx.validation`` cannot alter what this migration did.
    """
    from urllib.parse import urlparse

    if not isinstance(value, str) or not value.strip():
        return None
    url = value.strip()
    if "://" not in url and not url.startswith("//"):
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    try:
        parsed.port  # noqa: B018 — raises ValueError on a malformed port
    except ValueError:
        return None
    if "." not in parsed.hostname and parsed.hostname != "localhost":
        return None
    return url


def migrate_v13_to_v14(conn) -> None:
    """Repair data the 027 input validation now rejects (data-only).

    - ``tags = 'null'`` (stored by ``PATCH {"tags": null}``) → ``'[]'``; the
      'null' rows broke every later tag listing for that user.
    - Non-http(s) URLs (``javascript:`` etc.) in ``application.url``,
      ``contact.linkedin_url`` and resume ``contact.linkedin|website|github``
      → bare hosts get ``https://`` prepended; anything still not a web URL
      → NULL, so the new model validators can still read every stored row.
    """
    for table in _TAGGED_TABLES:
        conn.execute(
            f"UPDATE {table} SET tags = '[]' WHERE tags IS NULL OR tags = 'null'"  # noqa: S608 — table from fixed _TAGGED_TABLES
        )

    # Explicit dict rows: the migration connection may use the default factory.
    cur = conn.cursor(row_factory=dict_row)
    for table, column in (("application", "url"), ("contact", "linkedin_url")):
        rows = cur.execute(
            f"SELECT id, {column} AS url FROM {table} "  # noqa: S608 — table/column from literal tuple
            f"WHERE {column} IS NOT NULL AND {column} <> ''"
        ).fetchall()
        for row in rows:
            fixed = _normalize_http_url(row["url"])
            if fixed != row["url"]:
                conn.execute(
                    f"UPDATE {table} SET {column} = %s WHERE id = %s",  # noqa: S608 — table/column from literal tuple
                    (fixed, row["id"]),
                )

    rows = cur.execute("SELECT id, resume_data FROM resume_version").fetchall()
    for row in rows:
        data = json.loads(row["resume_data"] or "{}")
        contact = data.get("contact") if isinstance(data, dict) else None
        if not isinstance(contact, dict):
            continue
        changed = False
        for key in ("linkedin", "website", "github"):
            value = contact.get(key)
            if value:
                fixed = _normalize_http_url(value)
                if fixed != value:
                    contact[key] = fixed
                    changed = True
        if changed:
            conn.execute(
                "UPDATE resume_version SET resume_data = %s WHERE id = %s",
                (json.dumps(data), row["id"]),
            )

    conn.execute("UPDATE schema_version SET version = %s", (14,))
    conn.commit()


def migrate_v14_to_v15(conn) -> None:
    """Give every resume list entry a stable id and seed the section layout.

    Data-only and idempotent: entries that already have an id are untouched and
    an existing layout is kept. Sections that predate the layout stay visible;
    the new ones start hidden until they have content. Values are hardcoded so
    later registry changes cannot alter what this migration did.
    """
    import uuid

    legacy = ("experience", "education", "skills")
    later = (
        "projects",
        "certifications",
        "awards",
        "publications",
        "volunteer",
        "languages",
    )
    # Explicit dict rows: the migration connection may use the default factory.
    cur = conn.cursor(row_factory=dict_row)
    rows = cur.execute("SELECT id, resume_data FROM resume_version").fetchall()
    for row in rows:
        data = json.loads(row["resume_data"] or "{}")
        if not isinstance(data, dict):
            continue
        for key in (*legacy, *later):
            for entry in data.get(key) or []:
                if isinstance(entry, dict) and not entry.get("id"):
                    entry["id"] = uuid.uuid4().hex
        if not data.get("layout"):
            data["layout"] = [
                {"section": k, "visible": True, "title": None}
                for k in ("summary", *legacy)
            ] + [{"section": k, "visible": False, "title": None} for k in later]
        conn.execute(
            "UPDATE resume_version SET resume_data = %s WHERE id = %s",
            (json.dumps(data), row["id"]),
        )

    conn.execute("UPDATE schema_version SET version = %s", (15,))
    conn.commit()


MIGRATIONS: list = [
    migrate_v0_to_v1,
    migrate_v1_to_v2,
    migrate_v2_to_v3,
    migrate_v3_to_v4,
    migrate_v4_to_v5,
    migrate_v5_to_v6,
    migrate_v6_to_v7,
    migrate_v7_to_v8,
    migrate_v8_to_v9,
    migrate_v9_to_v10,
    migrate_v10_to_v11,
    migrate_v11_to_v12,
    migrate_v12_to_v13,
    migrate_v13_to_v14,
    migrate_v14_to_v15,
]

SCHEMA_VERSION: int = len(MIGRATIONS)


def apply_migrations(conn) -> None:
    """Apply pending migrations to bring the database to the current schema version."""
    _bootstrap_schema_version(conn)
    current = _get_version(conn)

    # Repair schema_version if it lags behind the actual DB structure.
    # This handles the case where autocommit mode caused table DDL to persist
    # but the schema_version UPDATE at the end of a migration never ran.
    actual = _detect_actual_version(conn)
    if actual > current:
        logger.warning(
            "schema_version (%d) lags actual DB state (%d) — repairing",
            current,
            actual,
        )
        conn.execute("UPDATE schema_version SET version = %s", (actual,))
        conn.commit()
        current = actual

    if current > len(MIGRATIONS):
        raise SchemaVersionError(db_version=current, code_version=len(MIGRATIONS))

    if current == len(MIGRATIONS):
        logger.info("Database schema is current (version %d)", current)
        return

    for i in range(current, len(MIGRATIONS)):
        target = i + 1
        logger.info("Applying migration v%d → v%d", i, target)
        try:
            MIGRATIONS[i](conn)
        except Exception as e:
            conn.rollback()
            raise MigrationError(from_version=i, to_version=target, cause=e) from e

    logger.info("Database migrated to version %d", len(MIGRATIONS))
