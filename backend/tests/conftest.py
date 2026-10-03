"""Shared test fixtures for pktx MCP server tests.

Three-layer fixture hierarchy
------------------------------
1. ``pg_container`` (session-scoped): starts one ``postgres:16-alpine``
   container for the entire test session.
2. ``_schema_applied`` (session-scoped): applies all migrations exactly once
   against a dedicated session-level schema so the DDL cost is paid once.
3. ``db_conn`` (function-scoped): opens a fresh psycopg connection, issues
   ``BEGIN``, yields, then ``ROLLBACK`` — every test sees a clean slate with
   no data leakage between tests.

Usage examples
--------------
Pure unit test (no DB needed)::

    def test_pure_logic() -> None:
        from unittest.mock import MagicMock
        conn = MagicMock()
        # test business logic in isolation

DB integration test::

    def test_foo(db_conn) -> None:
        from pktx.database import create_application
        app = create_application(db_conn, {"company": "Acme", "position": "Dev"})
        assert app["company"] == "Acme"
        # db_conn automatically rolls back after this test

API / contract test::

    def test_api(test_client, db_conn) -> None:
        response = test_client.post("/api/applications", json={...})
        assert response.status_code == 201
"""

import json
from collections.abc import Generator
from typing import Any

import psycopg
import pytest
from psycopg import Connection
from psycopg.rows import dict_row
from testcontainers.postgres import PostgresContainer

# ---------------------------------------------------------------------------
# Layer 1: session-scoped container (starts once per test session)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pg_container():
    """Start a postgres:16-alpine container once for the entire test session."""
    with PostgresContainer("postgres:16-alpine", driver=None) as container:
        yield container


# ---------------------------------------------------------------------------
# Layer 2: session-scoped DSN + migrations applied once
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pg_dsn(pg_container) -> str:
    """Extract the plain DSN from the running container."""
    return pg_container.get_connection_url()


@pytest.fixture(scope="session")
def _schema_applied(pg_dsn: str) -> None:
    """Apply all migrations exactly once per test session."""
    from pktx.migrations import apply_migrations

    with psycopg.connect(pg_dsn) as conn:
        apply_migrations(conn)


# ---------------------------------------------------------------------------
# Layer 3: function-scoped connection with BEGIN / ROLLBACK per test
# ---------------------------------------------------------------------------


@pytest.fixture
def db_conn(_schema_applied, pg_dsn: str) -> Generator[Connection[Any], None, None]:
    """Per-test PostgreSQL connection with automatic rollback.

    Each test runs inside a transaction that is rolled back on teardown,
    ensuring no data leaks between tests. Database functions must NOT call
    conn.commit() — transaction lifecycle is managed here and by the pool
    context manager in production.
    """
    with psycopg.connect(pg_dsn, row_factory=dict_row, autocommit=False) as conn:  # type: ignore[call-overload]
        yield conn
        conn.rollback()


# ---------------------------------------------------------------------------
# Sample resume data
# ---------------------------------------------------------------------------


SAMPLE_RESUME_DATA: dict[str, Any] = {
    "contact": {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+1-555-0100",
        "location": "San Francisco, CA",
        "linkedin": "https://linkedin.com/in/janedoe",
        "website": "https://janedoe.dev",
        "github": "https://github.com/janedoe",
    },
    "summary": "Experienced software engineer with 10 years of experience.",
    "experience": [
        {
            "title": "Senior Software Engineer",
            "company": "Acme Corp",
            "start_date": "2021-01",
            "end_date": "present",
            "location": "San Francisco, CA",
            "highlights": [
                "Led migration of monolithic application to microservices",
                "Reduced deployment time by 60%",
            ],
        },
        {
            "title": "Software Engineer",
            "company": "StartupCo",
            "start_date": "2018-06",
            "end_date": "2020-12",
            "location": "New York, NY",
            "highlights": [
                "Built real-time data pipeline processing 1M events/day",
                "Mentored 3 junior engineers",
            ],
        },
    ],
    "education": [
        {
            "institution": "Stanford University",
            "degree": "M.S. Computer Science",
            "field": None,
            "start_date": "2016-09",
            "end_date": "2018-05",
            "honors": "Dean's List",
        },
        {
            "institution": "UC Berkeley",
            "degree": "B.S. Computer Science",
            "field": None,
            "start_date": "2012-09",
            "end_date": "2016-05",
            "honors": None,
        },
    ],
    "skills": [
        {"name": "Python", "category": "Programming Languages"},
        {"name": "TypeScript", "category": "Programming Languages"},
        {"name": "Go", "category": "Programming Languages"},
        {"name": "FastAPI", "category": "Frameworks"},
        {"name": "React", "category": "Frameworks"},
        {"name": "Kubernetes", "category": "Frameworks"},
        {"name": "Technical Leadership", "category": "Soft Skills"},
        {"name": "Mentoring", "category": "Soft Skills"},
    ],
}


def populate_sample_data(conn: Connection[Any]) -> None:
    """Populate the default resume version with sample data.

    The migration creates an empty default version. This updates it
    with sample data for testing.
    """
    conn.execute(
        "UPDATE resume_version SET resume_data = %s WHERE is_default = 1",
        (json.dumps(SAMPLE_RESUME_DATA),),
    )


@pytest.fixture
def db_conn_with_data(db_conn: Connection[Any]) -> Connection[Any]:
    """Database connection pre-populated with sample resume data."""
    populate_sample_data(db_conn)
    return db_conn


# ---------------------------------------------------------------------------
# ResumeService fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def resume_service(db_conn: Connection[Any]):  # type: ignore[no-untyped-def]
    """ResumeService backed by a PostgreSQL database."""
    from pktx.resume_service import ResumeService

    return ResumeService(db_conn)  # type: ignore[arg-type]


@pytest.fixture
def resume_service_with_data(db_conn_with_data: Connection[Any]):  # type: ignore[no-untyped-def]
    """ResumeService backed by a database pre-populated with sample data."""
    from pktx.resume_service import ResumeService

    return ResumeService(db_conn_with_data)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Production-parity connection (autocommit) — 027
# ---------------------------------------------------------------------------


@pytest.fixture
def autocommit_conn(
    _schema_applied, pg_dsn: str
) -> Generator[Connection[Any], None, None]:
    """Autocommit connection matching the production connection mode.

    Writes are real (no wrapping transaction), so tests MUST create data only
    under users whose ids start with ``ac_``; every such user is deleted on
    teardown and ``ON DELETE CASCADE`` removes everything they own.
    """
    with psycopg.connect(pg_dsn, row_factory=dict_row, autocommit=True) as conn:  # type: ignore[call-overload]
        try:
            yield conn
        finally:
            conn.execute("DELETE FROM users WHERE id LIKE 'ac\\_%%'")


# ---------------------------------------------------------------------------
# Two-user fixture — alice owns one of everything, bob owns nothing — 027
# ---------------------------------------------------------------------------

ALICE = "user_alice"
BOB = "user_bob"
# Marker planted in every alice-owned text field / tag; must never reach bob.
ALICE_MARKER = "alicesecret"


@pytest.fixture
def two_users(db_conn: Connection[Any]) -> dict[str, Any]:
    """Seed alice with one of every resource type (plus links + a comm).

    Returns a dict of alice's resource ids plus ``conn``. Bob exists with no data.
    """
    from pktx.accomplishment_service import AccomplishmentService
    from pktx.application_service import ApplicationService
    from pktx.communication_service import ContactCommunicationService
    from pktx.contact_service import ContactService
    from pktx.link_service import LinkService
    from pktx.note_service import NoteService
    from pktx.resume_service import ResumeService

    for uid in (ALICE, BOB):
        db_conn.execute(
            "INSERT INTO users (id) VALUES (%s) ON CONFLICT DO NOTHING", (uid,)
        )

    m = ALICE_MARKER
    tags = [m]
    resumes = ResumeService(db_conn)  # type: ignore[arg-type]
    r1 = resumes.create_resume(f"{m} resume", user_id=ALICE, tags=tags)
    r2 = resumes.create_resume(f"{m} resume two", user_id=ALICE, tags=tags)
    resumes.set_default(r1["id"], user_id=ALICE)
    resumes.update_section("summary", {"text": f"{m} summary"}, r1["id"], user_id=ALICE)
    resumes.add_entry(
        "experience",
        {"title": f"{m} title", "company": f"{m} co"},
        r1["id"],
        user_id=ALICE,
    )

    app = ApplicationService(db_conn).create_application(  # type: ignore[arg-type]
        {"company": f"{m} corp", "position": f"{m} eng", "tags": tags}, user_id=ALICE
    )
    acc = AccomplishmentService(db_conn).create_accomplishment(  # type: ignore[arg-type]
        {"title": f"{m} win", "tags": tags}, user_id=ALICE
    )
    note = NoteService(db_conn).create_note(  # type: ignore[arg-type]
        {"title": f"{m} note", "content": f"{m} body", "tags": tags}, user_id=ALICE
    )
    contact = ContactService(db_conn).create_contact(  # type: ignore[arg-type]
        {"name": f"{m} person", "tags": tags}, user_id=ALICE
    )
    comm = ContactCommunicationService(db_conn).add_for_contact(  # type: ignore[arg-type]
        contact["id"],
        {
            "type": "email",
            "direction": "sent",
            "subject": f"{m} subj",
            "body": f"{m} body",
            "date": "2024-01-01",
            "tags": tags,
        },
        user_id=ALICE,
    )
    links = LinkService(db_conn)  # type: ignore[arg-type]
    links.link("note", note["id"], "contact", contact["id"], ALICE)
    links.link("application", app["id"], "resume", r1["id"], ALICE)

    return {
        "conn": db_conn,
        "resume_id": r1["id"],
        "resume2_id": r2["id"],
        "app_id": app["id"],
        "acc_id": acc["id"],
        "note_id": note["id"],
        "contact_id": contact["id"],
        "comm_id": comm["id"],
    }


def snapshot_user_rows(conn: Connection[Any], user_id: str) -> dict[str, Any]:
    """Every row a user owns, per table — compare before/after to detect writes."""
    out: dict[str, Any] = {}
    for table in ("resume_version", "application", "accomplishment", "note", "contact"):
        out[table] = conn.execute(
            f"SELECT * FROM {table} WHERE user_id = %s ORDER BY id", (user_id,)
        ).fetchall()
    out["communication"] = conn.execute(
        "SELECT c.* FROM communication c JOIN contact ct ON c.contact_ref_id = ct.id "
        "WHERE ct.user_id = %s ORDER BY c.id",
        (user_id,),
    ).fetchall()
    out["resource_link"] = conn.execute(
        "SELECT * FROM resource_link WHERE user_id = %s "
        "ORDER BY left_type, left_id, right_type, right_id",
        (user_id,),
    ).fetchall()
    return out
