"""Unit tests for pktx.migrations module (PostgreSQL).

Uses a self-contained module-scoped testcontainers fixture — no conftest.py
dependency — so these tests can run before conftest.py is rewritten.

Isolation strategy: module-scoped container (starts once) + function-scoped
pg_conn that creates a fresh PostgreSQL schema per test and drops it on teardown.
This avoids DDL leakage between tests without restarting the container.
"""

import uuid
from typing import Any, cast

import psycopg
import pytest
from psycopg.rows import dict_row
from testcontainers.postgres import PostgresContainer

# ---------------------------------------------------------------------------
# Module-scoped inline fixture: starts one container for all migration tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pg_dsn():
    """Start a postgres:16-alpine container and yield the connection DSN."""
    with PostgresContainer("postgres:16-alpine", driver=None) as container:
        yield container.get_connection_url()


@pytest.fixture
def pg_conn(pg_dsn: str):
    """Per-test isolated connection using a fresh PostgreSQL schema.

    Creates a unique schema, sets search_path to it, yields the connection,
    then drops the schema (and all its objects) on teardown.
    """
    schema = f"t_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(pg_dsn, row_factory=dict_row) as _raw_conn:  # type: ignore[call-overload]
        conn = cast(psycopg.Connection[Any], _raw_conn)
        conn.execute(f'CREATE SCHEMA "{schema}"')  # type: ignore[arg-type]
        conn.execute(f'SET search_path = "{schema}"')  # type: ignore[arg-type]
        conn.commit()
        yield conn
        conn.execute("SET search_path = public")
        conn.execute(f'DROP SCHEMA "{schema}" CASCADE')  # type: ignore[arg-type]
        conn.commit()


# ---------------------------------------------------------------------------
# Helper: get current schema version
# ---------------------------------------------------------------------------


def _get_version(conn) -> int:
    row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    if row is None:
        return -1
    return row["version"] if isinstance(row, dict) else row[0]


# ---------------------------------------------------------------------------
# TestApplyMigrations
# ---------------------------------------------------------------------------


class TestApplyMigrations:
    """Tests for the migration framework."""

    def test_applies_all_migrations(self, pg_conn) -> None:
        from pktx.migrations import SCHEMA_VERSION, apply_migrations

        apply_migrations(pg_conn)
        version = _get_version(pg_conn)
        assert version == SCHEMA_VERSION

    def test_no_op_when_already_current(self, pg_conn) -> None:
        from pktx.migrations import apply_migrations

        apply_migrations(pg_conn)
        version_before = _get_version(pg_conn)

        # Apply again — should be a no-op
        apply_migrations(pg_conn)
        version_after = _get_version(pg_conn)

        assert version_before == version_after

    def test_raises_schema_version_error_when_db_ahead(self, pg_conn) -> None:
        from pktx.migrations import SchemaVersionError, apply_migrations

        # Bootstrap schema_version table manually with a future version
        pg_conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version "
            "(version INTEGER NOT NULL DEFAULT 0)"
        )
        pg_conn.execute("DELETE FROM schema_version")
        pg_conn.execute("INSERT INTO schema_version (version) VALUES (999)")
        pg_conn.commit()

        with pytest.raises(SchemaVersionError):
            apply_migrations(pg_conn)

    def test_schema_version_error_has_versions(self) -> None:
        from pktx.migrations import SchemaVersionError

        err = SchemaVersionError(db_version=5, code_version=1)
        assert err.db_version == 5
        assert err.code_version == 1
        assert "5" in str(err)
        assert "1" in str(err)

    def test_migration_error_has_context(self) -> None:
        from pktx.migrations import MigrationError

        cause = RuntimeError("bad sql")
        err = MigrationError(from_version=0, to_version=1, cause=cause)
        assert err.from_version == 0
        assert err.to_version == 1
        assert err.__cause__ is cause or "bad sql" in str(err)

    def test_rollback_on_migration_failure(self, pg_conn) -> None:
        """A failed migration should leave the DB at the pre-migration version."""
        from pktx.migrations import (
            MIGRATIONS,
            MigrationError,
            apply_migrations,
        )

        apply_migrations(pg_conn)
        version_before = _get_version(pg_conn)

        def broken_migration(c) -> None:
            raise RuntimeError("intentional failure")

        original_migrations = MIGRATIONS.copy()
        MIGRATIONS.append(broken_migration)

        try:
            with pytest.raises(MigrationError):
                apply_migrations(pg_conn)

            version_after = _get_version(pg_conn)
            assert version_after == version_before
        finally:
            MIGRATIONS.clear()
            MIGRATIONS.extend(original_migrations)

    def test_schema_version_bootstrapped_on_first_run(self, pg_conn) -> None:
        """schema_version must exist with exactly one row after apply_migrations."""
        from pktx.migrations import apply_migrations

        apply_migrations(pg_conn)
        rows = pg_conn.execute("SELECT version FROM schema_version").fetchall()
        assert len(rows) == 1
        assert rows[0]["version"] >= 0


# ---------------------------------------------------------------------------
# Test individual migration final schema state
# ---------------------------------------------------------------------------


class TestMigrationV0ToV1:
    """Verify final schema state after v0→v1 migration."""

    def test_creates_all_v1_tables(self, pg_conn) -> None:
        from pktx.migrations import migrate_v0_to_v1

        # Bootstrap schema_version first
        pg_conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version "
            "(version INTEGER NOT NULL DEFAULT 0)"
        )
        pg_conn.execute(
            "INSERT INTO schema_version (version) VALUES (0) ON CONFLICT DO NOTHING"
        )
        pg_conn.commit()

        migrate_v0_to_v1(pg_conn)

        tables = {
            row["tablename"]
            for row in pg_conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = current_schema()"
            ).fetchall()
        }
        assert "contact" in tables
        assert "summary" in tables
        assert "experience" in tables
        assert "education" in tables
        assert "skill" in tables


class TestFullMigrationChain:
    """Tests for complete migration chain applied via apply_migrations."""

    def test_final_schema_has_users_table(self, pg_conn) -> None:
        from pktx.migrations import apply_migrations

        apply_migrations(pg_conn)

        tables = {
            row["tablename"]
            for row in pg_conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = current_schema()"
            ).fetchall()
        }
        assert "users" in tables
        assert "resume_version" in tables
        assert "application" in tables
        assert "accomplishment" in tables

    def test_resume_version_has_serial_pk(self, pg_conn) -> None:
        """After full migration, SERIAL PK on resume_version must be auto-assigned."""
        from pktx.migrations import apply_migrations

        apply_migrations(pg_conn)

        pg_conn.execute("INSERT INTO users (id) VALUES ('test-user-serial')")
        pg_conn.execute(
            "INSERT INTO resume_version (user_id, label, resume_data) "
            "VALUES ('test-user-serial', 'Test', '{}')"
        )
        pg_conn.commit()

        row = pg_conn.execute(
            "SELECT id FROM resume_version WHERE user_id = 'test-user-serial'"
        ).fetchone()
        assert row is not None
        assert isinstance(row["id"], int)
        assert row["id"] > 0

    def test_version_incremented_through_full_chain(self, pg_conn) -> None:
        from pktx.migrations import SCHEMA_VERSION, apply_migrations

        apply_migrations(pg_conn)
        version = _get_version(pg_conn)
        assert version == SCHEMA_VERSION

    def test_application_has_no_resume_version_id_column(self, pg_conn) -> None:
        """After v12, application table must not have resume_version_id column."""
        from pktx.migrations import _column_exists, apply_migrations

        apply_migrations(pg_conn)
        assert not _column_exists(pg_conn, "application", "resume_version_id")


class TestMigrateV11ToV12:
    """Verify v11→v12 migration backfills FK into resource_link then drops column."""

    def test_backfills_fk_into_resource_link(self, pg_conn) -> None:
        from pktx.migrations import (
            MIGRATIONS,
            apply_migrations,
            migrate_v11_to_v12,
        )

        # Apply all migrations up to v11.
        original = MIGRATIONS.copy()
        MIGRATIONS_UP_TO_V11 = original[:11]
        MIGRATIONS.clear()
        MIGRATIONS.extend(MIGRATIONS_UP_TO_V11)
        try:
            apply_migrations(pg_conn)
        finally:
            MIGRATIONS.clear()
            MIGRATIONS.extend(original)

        # Seed a user, resume, and application with resume_version_id set.
        pg_conn.execute("INSERT INTO users (id) VALUES ('u1')")
        pg_conn.execute(
            "INSERT INTO resume_version (user_id, label, is_default, resume_data) "
            "VALUES ('u1', 'R1', 1, '{}')"
        )
        rv_id = pg_conn.execute(
            "SELECT id FROM resume_version WHERE user_id = 'u1'"
        ).fetchone()["id"]
        pg_conn.execute(
            "INSERT INTO application (user_id, company, position, resume_version_id) "
            "VALUES ('u1', 'Co', 'Dev', %s)",
            (rv_id,),
        )
        app_id = pg_conn.execute(
            "SELECT id FROM application WHERE user_id = 'u1'"
        ).fetchone()["id"]
        pg_conn.commit()

        # Run the migration.
        migrate_v11_to_v12(pg_conn)

        # Canonical link must exist (application < resume lexicographically).
        row = pg_conn.execute(
            "SELECT * FROM resource_link "
            "WHERE left_type = 'application' AND left_id = %s "
            "AND right_type = 'resume' AND right_id = %s",
            (app_id, rv_id),
        ).fetchone()
        assert row is not None

    def test_drops_resume_version_id_column(self, pg_conn) -> None:
        from pktx.migrations import (
            MIGRATIONS,
            _column_exists,
            apply_migrations,
            migrate_v11_to_v12,
        )

        original = MIGRATIONS.copy()
        MIGRATIONS_UP_TO_V11 = original[:11]
        MIGRATIONS.clear()
        MIGRATIONS.extend(MIGRATIONS_UP_TO_V11)
        try:
            apply_migrations(pg_conn)
        finally:
            MIGRATIONS.clear()
            MIGRATIONS.extend(original)

        pg_conn.commit()
        migrate_v11_to_v12(pg_conn)
        assert not _column_exists(pg_conn, "application", "resume_version_id")


class TestMigrateV13ToV14:
    """v13→v14 repairs data the 027 validation now rejects."""

    def test_repairs_null_tags_and_unsafe_urls(self, pg_conn) -> None:
        import json

        from pktx.migrations import MIGRATIONS, apply_migrations, migrate_v13_to_v14

        original = MIGRATIONS.copy()
        MIGRATIONS[:] = original[:13]
        try:
            apply_migrations(pg_conn)
        finally:
            MIGRATIONS[:] = original

        resume = {
            "contact": {
                "name": "Jo",
                "website": "javascript:alert(1)",
                "github": "https://github.com/jo",
                "linkedin": "linkedin.com/in/jo",
            }
        }
        pg_conn.execute("INSERT INTO users (id) VALUES ('u1')")
        pg_conn.execute(
            "INSERT INTO resume_version (user_id, label, resume_data, tags) "
            "VALUES ('u1', 'R', %s, 'null')",
            (json.dumps(resume),),
        )
        pg_conn.execute(
            "INSERT INTO application (user_id, company, position, url, tags) "
            "VALUES ('u1', 'Co', 'Dev', 'javascript:alert(1)', 'null')"
        )
        pg_conn.execute(
            "INSERT INTO note (user_id, title, tags) VALUES ('u1', 'N', '[\"ok\"]')"
        )
        contact_id = pg_conn.execute(
            "INSERT INTO contact (user_id, name, linkedin_url, tags) "
            "VALUES ('u1', 'C', 'linkedin.com/in/c', 'null') RETURNING id"
        ).fetchone()["id"]
        pg_conn.execute(
            "INSERT INTO communication "
            "(contact_ref_id, type, direction, body, date, tags) "
            "VALUES (%s, 'email', 'sent', 'b', '2024-01-01', 'null')",
            (contact_id,),
        )
        pg_conn.commit()

        migrate_v13_to_v14(pg_conn)

        def one(sql: str) -> Any:
            return next(iter(pg_conn.execute(sql).fetchone().values()))

        for table in ("resume_version", "application", "contact", "communication"):
            assert one(f"SELECT tags FROM {table} ORDER BY id DESC") == "[]", table
        assert one("SELECT tags FROM note") == '["ok"]'
        assert one("SELECT url FROM application") is None
        assert one("SELECT linkedin_url FROM contact") == "https://linkedin.com/in/c"
        stored = json.loads(
            one("SELECT resume_data FROM resume_version WHERE user_id = 'u1'")
        )
        assert stored["contact"]["website"] is None
        assert stored["contact"]["github"] == "https://github.com/jo"
        # Bare hosts are kept, not dropped: https:// is prepended.
        assert stored["contact"]["linkedin"] == "https://linkedin.com/in/jo"
        assert _get_version(pg_conn) == 14


class TestMigrateV14ToV15:
    """v14→v15 backfills stable entry ids."""

    def test_backfills_ids_idempotently(self, pg_conn) -> None:
        import json

        from pktx.migrations import MIGRATIONS, apply_migrations, migrate_v14_to_v15

        original = MIGRATIONS.copy()
        MIGRATIONS[:] = original[:14]
        try:
            apply_migrations(pg_conn)
        finally:
            MIGRATIONS[:] = original

        resume = {
            "summary": "s",
            "experience": [{"title": "Dev", "company": "Co"}],
            "skills": [{"name": "Go", "id": "keepme"}, {"name": "Rust"}],
        }
        pg_conn.execute("INSERT INTO users (id) VALUES ('u1')")
        pg_conn.execute(
            "INSERT INTO resume_version (user_id, label, resume_data, tags) "
            "VALUES ('u1', 'R', %s, '[]')",
            (json.dumps(resume),),
        )
        pg_conn.execute(
            "INSERT INTO resume_version (user_id, label, resume_data, tags) "
            "VALUES ('u1', 'Empty', '{}', '[]')"
        )
        pg_conn.commit()

        def stored() -> dict:
            row = pg_conn.execute(
                "SELECT resume_data FROM resume_version WHERE label = 'R'"
            ).fetchone()
            return json.loads(row["resume_data"])

        migrate_v14_to_v15(pg_conn)
        first = stored()
        ids = [e["id"] for e in first["experience"] + first["skills"]]
        assert all(ids) and len(set(ids)) == 3
        assert first["skills"][0]["id"] == "keepme"
        assert first["experience"][0]["title"] == "Dev" and first["summary"] == "s"
        assert _get_version(pg_conn) == 15

        migrate_v14_to_v15(pg_conn)
        assert stored() == first


class TestMigrateV15ToV16:
    """v15→v16 turns fixed contact links into key/value fields."""

    def test_converts_legacy_contact_idempotently(self, pg_conn) -> None:
        import json

        from pktx.migrations import MIGRATIONS, apply_migrations, migrate_v15_to_v16

        original = MIGRATIONS.copy()
        MIGRATIONS[:] = original[:15]
        try:
            apply_migrations(pg_conn)
        finally:
            MIGRATIONS[:] = original

        contact = {
            "name": "Jo",
            "phone": "555",
            "email": "jo@x.io",
            "website": None,
            "linkedin": "https://linkedin.com/in/jo",
            "github": "https://github.com/jo",
            "profiles": [
                {"label": "GitLab", "url": "https://gitlab.com/jo"},
                {"label": "github", "url": "https://github.com/dupe"},
            ],
        }
        pg_conn.execute("INSERT INTO users (id) VALUES ('u1')")
        for label, data in (
            ("R", {"contact": contact}),
            ("E", {}),
            ("N", {"contact": {"name": "x"}}),
        ):
            pg_conn.execute(
                "INSERT INTO resume_version (user_id, label, resume_data, tags) "
                "VALUES ('u1', %s, %s, '[]')",
                (label, json.dumps(data)),
            )
        pg_conn.commit()

        def stored(label: str) -> dict:
            row = pg_conn.execute(
                "SELECT resume_data FROM resume_version WHERE label = %s", (label,)
            ).fetchone()
            return json.loads(row["resume_data"])

        migrate_v15_to_v16(pg_conn)
        c = stored("R")["contact"]
        assert c["name"] == "Jo" and c["phone"] == "555"
        assert c["fields"] == [
            {"key": "Email", "value": "jo@x.io"},
            {"key": "LinkedIn", "value": "https://linkedin.com/in/jo"},
            {"key": "GitHub", "value": "https://github.com/jo"},
            {"key": "GitLab", "value": "https://gitlab.com/jo"},
        ]
        assert not {"email", "website", "linkedin", "github", "profiles"} & set(c)
        assert stored("E") == {} and "fields" not in stored("N")["contact"]
        assert _get_version(pg_conn) == 16

        first = stored("R")
        migrate_v15_to_v16(pg_conn)
        assert stored("R") == first


V16_RESUME: dict[str, Any] = {
    "contact": {
        "name": "Nathan",
        "phone": "555",
        "location": "Bellingham, WA",
        "fields": [
            {"key": "Email", "value": "n@x.io"},
            {"key": "Website", "value": "https://n.dev"},
            {"key": "LinkedIn", "value": "https://linkedin.com/in/n"},
            {"key": "Pronouns", "value": "he/him"},
            {"key": "Backup email", "value": "n2@x.io"},
        ],
    },
    "summary": "Staff engineer.",
    "experience": [
        {
            "id": "e1",
            "title": "Staff Engineer",
            "company": "Experian",
            "start_date": "11/2019",
            "end_date": "Present",
            "location": "WA - Remote",
            "highlights": ["Migrated batch apps"],
        },
        {"id": "e2", "title": "QA", "company": "Experian", "start_date": "soon"},
    ],
    "education": [
        {
            "id": "d1",
            "institution": "WWU",
            "degree": "BS",
            "field": "Physics",
            "start_date": "01/2005",
            "end_date": "2008",
            "honors": "cum laude",
            "highlights": ["x"],
        }
    ],
    "skills": [
        {"id": "s1", "name": "Java", "category": "Languages"},
        {"id": "s2", "name": "Go", "category": "Languages"},
        {"id": "s3", "name": "EC2", "category": "AWS"},
        {"id": "s4", "name": "Other thing", "category": None},
    ],
    "projects": [{"id": "p1", "name": "pktx", "tech": ["py"], "start_date": "2026"}],
    "certifications": [
        {
            "id": "c1",
            "name": "CKA",
            "issuer": "CNCF",
            "issued": "Mar 2024",
            "expires": "2027",
            "credential_id": "42",
        }
    ],
    "awards": [{"id": "a1", "title": "Best", "issuer": "Acme", "description": "d"}],
    "publications": [{"id": "u1", "title": "T", "venue": "V", "date": "2020-05-01"}],
    "volunteer": [
        {"id": "v1", "role": "Mentor", "organization": "Club", "location": "x"}
    ],
    "languages": [{"id": "l1", "language": "Spanish", "proficiency": "Fluent"}],
    "enabled_sections": ["projects"],
}


class TestV16ToV17Converter:
    """Pure reshape: v16 blob -> JSON Resume document."""

    def test_full_resume(self) -> None:
        from pktx.migrations import _v16_to_v17

        warnings: list[str] = []
        out = _v16_to_v17(V16_RESUME, warnings.append)

        basics = out["basics"]
        profile_id = basics["profiles"][0].pop("id")
        assert profile_id
        assert basics == {
            "name": "Nathan",
            "phone": "555",
            "summary": "Staff engineer.",
            "location": {"city": "Bellingham", "region": "WA"},
            "email": "n@x.io",
            "url": "https://n.dev",
            "profiles": [{"network": "LinkedIn", "url": "https://linkedin.com/in/n"}],
        }
        assert out["work"] == [
            {
                "id": "e1",
                "name": "Experian",
                "position": "Staff Engineer",
                "location": "WA - Remote",
                "startDate": "2019-11",
                "highlights": ["Migrated batch apps"],
            },
            {"id": "e2", "name": "Experian", "position": "QA"},
        ]
        assert out["education"] == [
            {
                "id": "d1",
                "institution": "WWU",
                "studyType": "BS",
                "area": "Physics",
                "startDate": "2005-01",
                "endDate": "2008",
            }
        ]
        groups = [(g["name"], g["keywords"]) for g in out["skills"]]
        assert groups == [
            ("Languages", ["Java", "Go"]),
            ("AWS", ["EC2"]),
            ("Other", ["Other thing"]),
        ]
        assert all(g["id"] for g in out["skills"])
        assert out["projects"] == [
            {"id": "p1", "name": "pktx", "keywords": ["py"], "startDate": "2026"}
        ]
        assert out["certificates"] == [
            {"id": "c1", "name": "CKA", "issuer": "CNCF", "date": "2024-03"}
        ]
        assert out["awards"] == [
            {"id": "a1", "title": "Best", "awarder": "Acme", "summary": "d"}
        ]
        assert out["publications"] == [
            {"id": "u1", "name": "T", "publisher": "V", "releaseDate": "2020-05-01"}
        ]
        assert out["volunteer"] == [
            {"id": "v1", "organization": "Club", "position": "Mentor"}
        ]
        assert out["languages"] == [
            {"id": "l1", "language": "Spanish", "fluency": "Fluent"}
        ]
        for old in (
            "contact",
            "summary",
            "experience",
            "certifications",
            "enabled_sections",
        ):
            assert old not in out
        assert warnings == ["dropped unparseable date 'soon' in experience"]

    def test_period_sections_keep_the_newest_first_order_the_old_ui_showed(
        self,
    ) -> None:
        from pktx.migrations import _v16_to_v17

        out = _v16_to_v17(
            {
                "experience": [
                    {"id": "a", "title": "t", "company": "c", "start_date": "03/2011",
                     "end_date": "02/2013"},
                    {"id": "b", "title": "t", "company": "c", "start_date": "03/2013",
                     "end_date": "11/2019"},
                    {"id": "c", "title": "t", "company": "c", "start_date": "11/2019",
                     "end_date": "Present"},
                    {"id": "d", "title": "t", "company": "c", "start_date": "2012",
                     "end_date": "2013"},
                ],
                "awards": [{"id": "x", "title": "old"}, {"id": "y", "title": "new"}],
                "skills": [{"id": "s1", "name": "Go", "category": "B"},
                           {"id": "s2", "name": "C", "category": "A"}],
            }
        )  # fmt: skip
        assert [w["id"] for w in out["work"]] == ["c", "b", "a", "d"]
        # Sections without a period keep their stored order.
        assert [a["id"] for a in out["awards"]] == ["x", "y"]
        assert [g["name"] for g in out["skills"]] == ["B", "A"]

    def test_idempotent(self) -> None:
        from pktx.migrations import _v16_to_v17

        once = _v16_to_v17(V16_RESUME)
        assert _v16_to_v17(once) == once

    def test_empty_stays_empty(self) -> None:
        from pktx.migrations import _v16_to_v17

        assert _v16_to_v17({}) == {}
        assert (
            _v16_to_v17({"contact": {"fields": []}, "summary": "", "skills": []}) == {}
        )

    def test_location_without_comma_is_city(self) -> None:
        from pktx.migrations import _v16_to_v17

        out = _v16_to_v17({"contact": {"location": "Remote"}})
        assert out["basics"]["location"] == {"city": "Remote"}
        out = _v16_to_v17({"contact": {"location": "A, B, C"}})
        assert out["basics"]["location"] == {"city": "A, B", "region": "C"}

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("2020", "2020"),
            ("2020-05", "2020-05"),
            ("2020-05-17", "2020-05-17"),
            ("2020-5", "2020-05"),
            ("03/2011", "2011-03"),
            ("3/2011", "2011-03"),
            ("2011/03", "2011-03"),
            ("Mar 2020", "2020-03"),
            ("sept 2020", "2020-09"),
            ("December, 2019", "2019-12"),
            ("Present", None),
            ("current", None),
            ("", None),
            (None, None),
            ("13/2020", None),
            ("2020-02-30", None),
            ("someday", None),
        ],
    )
    def test_normalize_date(self, raw: Any, expected: str | None) -> None:
        from pktx.migrations import _normalize_date

        assert _normalize_date(raw) == expected


class TestMigrateV16ToV17:
    """v16->v17 stores resumes as JSON Resume in a JSONB column."""

    def test_converts_rows_and_column_type(self, pg_conn) -> None:
        import json

        from pktx.migrations import MIGRATIONS, apply_migrations, migrate_v16_to_v17

        original = MIGRATIONS.copy()
        MIGRATIONS[:] = original[:16]
        try:
            apply_migrations(pg_conn)
        finally:
            MIGRATIONS[:] = original

        pg_conn.execute("INSERT INTO users (id) VALUES ('u1')")
        for label, data in (("R", V16_RESUME), ("E", {})):
            pg_conn.execute(
                "INSERT INTO resume_version (user_id, label, resume_data, tags) "
                "VALUES ('u1', %s, %s, '[]')",
                (label, json.dumps(data)),
            )
        pg_conn.commit()

        migrate_v16_to_v17(pg_conn)

        col = pg_conn.execute(
            "SELECT data_type, column_default FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND table_name = 'resume_version' AND column_name = 'resume_data'"
        ).fetchone()
        assert col["data_type"] == "jsonb"
        assert "{}" in col["column_default"]

        rows = {
            r["label"]: r["resume_data"]
            for r in pg_conn.execute(
                "SELECT label, resume_data FROM resume_version WHERE user_id = 'u1'"
            ).fetchall()
        }
        assert isinstance(rows["R"], dict)
        assert rows["R"]["basics"]["name"] == "Nathan"
        assert rows["R"]["work"][0]["position"] == "Staff Engineer"
        assert rows["E"] == {}
        assert _get_version(pg_conn) == 17

    def test_full_chain_ends_at_17_with_empty_default(self, pg_conn) -> None:
        from pktx.migrations import apply_migrations

        apply_migrations(pg_conn)
        assert _get_version(pg_conn) == 17
        row = pg_conn.execute(
            "SELECT resume_data FROM resume_version WHERE is_default = 1"
        ).fetchone()
        assert row["resume_data"] == {}
