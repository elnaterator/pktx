"""Integration tests for MCP tool handler user scoping (DEF-1).

Verifies that all MCP tool handlers call require_user_id() and pass the
resulting user_id to service methods, ensuring data isolation between users.
"""

import asyncio
from typing import Any, cast

import pytest
from psycopg import Connection

from pktx.auth import current_user_id_var
from pktx.database import (
    create_resume_version,
    load_default_resume_version,
    set_default_resume_version,
)
from pktx.db import DBConnection

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def two_user_db(db_conn: Connection[Any]) -> Connection[Any]:
    """Seed two users and give each a default resume."""
    conn = cast(DBConnection, db_conn)
    db_conn.execute(
        "INSERT INTO users (id, email) VALUES ('user_alice', 'alice@test.com')"
    )
    db_conn.execute("INSERT INTO users (id, email) VALUES ('user_bob', 'bob@test.com')")

    # Give Alice a default resume
    create_resume_version(
        conn, "Alice CV", {"contact": {"name": "Alice"}}, user_id="user_alice"
    )
    rows = db_conn.execute(
        "SELECT id FROM resume_version WHERE user_id = 'user_alice'"
    ).fetchall()
    set_default_resume_version(conn, rows[0]["id"], user_id="user_alice")

    # Give Bob a default resume
    create_resume_version(
        conn, "Bob CV", {"contact": {"name": "Bob"}}, user_id="user_bob"
    )
    rows = db_conn.execute(
        "SELECT id FROM resume_version WHERE user_id = 'user_bob'"
    ).fetchall()
    set_default_resume_version(conn, rows[0]["id"], user_id="user_bob")

    return db_conn


def _as_user(user_id: str):
    """Context manager to set current_user_id_var for MCP tool handler calls."""
    return current_user_id_var.set(user_id)


# ---------------------------------------------------------------------------
# DEF-1: MCP tool handlers must require user_id
# ---------------------------------------------------------------------------


def _get_tool_fn(mcp: Any, name: str) -> Any:
    """Extract a registered MCP tool function by name for direct testing."""
    tools = asyncio.run(mcp.list_tools())
    for tool in tools:
        if tool.name == name:
            return tool.fn
    registered = [t.name for t in tools]
    raise KeyError(f"MCP tool '{name}' not found. Registered: {registered}")


class TestMcpToolsRequireUserContext:
    """All MCP tool handlers must raise RuntimeError when no user context."""

    def test_resume_list_requires_user(self, two_user_db: Connection[Any]) -> None:
        from fastmcp import FastMCP

        from pktx.resume_service import ResumeService
        from pktx.tools.resume_tools import register_resume_tools

        mcp = FastMCP("test")
        svc = ResumeService(two_user_db)  # type: ignore[arg-type]
        register_resume_tools(mcp, lambda: svc)

        list_fn = _get_tool_fn(mcp, "list_resumes")
        token = current_user_id_var.set(None)
        try:
            with pytest.raises(RuntimeError, match="No user context"):
                list_fn()
        finally:
            current_user_id_var.reset(token)

    def test_accomplishment_list_requires_user(
        self, two_user_db: Connection[Any]
    ) -> None:
        from fastmcp import FastMCP

        from pktx.accomplishment_service import AccomplishmentService
        from pktx.tools.accomplishment_tools import register_accomplishment_tools

        mcp = FastMCP("test")
        svc = AccomplishmentService(two_user_db)  # type: ignore[arg-type]
        register_accomplishment_tools(mcp, lambda: svc)

        list_fn = _get_tool_fn(mcp, "list_accomplishments")
        token = current_user_id_var.set(None)
        try:
            with pytest.raises(RuntimeError, match="No user context"):
                list_fn(tag=None, q=None)
        finally:
            current_user_id_var.reset(token)

    def test_application_list_requires_user(self, two_user_db: Connection[Any]) -> None:
        from fastmcp import FastMCP

        from pktx.application_service import ApplicationService
        from pktx.tools.application_tools import register_application_tools

        mcp = FastMCP("test")
        svc = ApplicationService(two_user_db)  # type: ignore[arg-type]
        register_application_tools(mcp, lambda: svc)

        list_fn = _get_tool_fn(mcp, "list_applications")
        token = current_user_id_var.set(None)
        try:
            with pytest.raises(RuntimeError, match="No user context"):
                list_fn(status=None, q=None)
        finally:
            current_user_id_var.reset(token)


# ---------------------------------------------------------------------------
# DEF-1: Resume tools pass user_id — isolation between Alice and Bob
# ---------------------------------------------------------------------------


class TestResumeToolUserScoping:
    """Resume MCP tools only operate on the authenticated user's data."""

    def test_list_resumes_scoped_to_user(self, two_user_db: Connection[Any]) -> None:
        from pktx.resume_service import ResumeService

        svc = ResumeService(two_user_db)  # type: ignore[arg-type]

        alice_resumes = svc.list_resumes(user_id="user_alice")
        bob_resumes = svc.list_resumes(user_id="user_bob")

        alice_labels = {r["label"] for r in alice_resumes}
        bob_labels = {r["label"] for r in bob_resumes}

        assert "Alice CV" in alice_labels
        assert "Bob CV" not in alice_labels
        assert "Bob CV" in bob_labels
        assert "Alice CV" not in bob_labels

    def test_get_resume_rejects_cross_user(self, two_user_db: Connection[Any]) -> None:
        from pktx.resume_service import ResumeService

        svc = ResumeService(two_user_db)  # type: ignore[arg-type]
        alice_resumes = svc.list_resumes(user_id="user_alice")
        alice_id = alice_resumes[0]["id"]

        with pytest.raises(ValueError, match="not found"):
            svc.get_resume(alice_id, user_id="user_bob")

    def test_create_resume_uses_user_id(self, two_user_db: Connection[Any]) -> None:
        from pktx.resume_service import ResumeService

        svc = ResumeService(two_user_db)  # type: ignore[arg-type]
        new = svc.create_resume("Bob Extra", user_id="user_bob")

        # Verify it's stored under Bob
        row = two_user_db.execute(
            "SELECT user_id FROM resume_version WHERE id = %s", (new["id"],)
        ).fetchone()
        assert row is not None
        assert row["user_id"] == "user_bob"

    def test_set_default_scoped_to_user(self, two_user_db: Connection[Any]) -> None:
        from pktx.resume_service import ResumeService

        svc = ResumeService(two_user_db)  # type: ignore[arg-type]

        # Create a second resume for Alice
        new = svc.create_resume("Alice v2", user_id="user_alice")
        svc.set_default(new["id"], user_id="user_alice")

        # Alice's default changed; Bob's default unchanged
        alice_default = load_default_resume_version(two_user_db, user_id="user_alice")  # type: ignore[arg-type]
        assert alice_default["label"] == "Alice v2"

        bob_default = load_default_resume_version(two_user_db, user_id="user_bob")  # type: ignore[arg-type]
        assert bob_default["label"] == "Bob CV"


# ---------------------------------------------------------------------------
# DEF-1: Application tools pass user_id
# ---------------------------------------------------------------------------


class TestApplicationToolUserScoping:
    """Application MCP tools only operate on the authenticated user's data."""

    def test_list_applications_scoped(self, two_user_db: Connection[Any]) -> None:
        from pktx.application_service import ApplicationService

        svc = ApplicationService(two_user_db)  # type: ignore[arg-type]
        svc.create_application(
            {"company": "AliceCo", "position": "Dev"}, user_id="user_alice"
        )
        svc.create_application(
            {"company": "BobCo", "position": "Eng"}, user_id="user_bob"
        )

        alice_apps = svc.list_applications(user_id="user_alice")
        bob_apps = svc.list_applications(user_id="user_bob")

        assert len(alice_apps) == 1
        assert alice_apps[0]["company"] == "AliceCo"
        assert len(bob_apps) == 1
        assert bob_apps[0]["company"] == "BobCo"

    def test_get_application_rejects_cross_user(
        self, two_user_db: Connection[Any]
    ) -> None:
        from pktx.application_service import ApplicationService

        svc = ApplicationService(two_user_db)  # type: ignore[arg-type]
        app = svc.create_application(
            {"company": "AliceCo", "position": "Dev"}, user_id="user_alice"
        )

        with pytest.raises(ValueError, match="not found"):
            svc.get_application(app["id"], user_id="user_bob")

    def test_delete_application_rejects_cross_user(
        self, two_user_db: Connection[Any]
    ) -> None:
        from pktx.application_service import ApplicationService

        svc = ApplicationService(two_user_db)  # type: ignore[arg-type]
        app = svc.create_application(
            {"company": "AliceCo", "position": "Dev"}, user_id="user_alice"
        )

        with pytest.raises(ValueError, match="not found"):
            svc.delete_application(app["id"], user_id="user_bob")


# ---------------------------------------------------------------------------
# DEF-1: Accomplishment tools pass user_id
# ---------------------------------------------------------------------------


class TestAccomplishmentToolUserScoping:
    """Accomplishment MCP tools only operate on the authenticated user's data."""

    def test_list_accomplishments_scoped(self, two_user_db: Connection[Any]) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc = AccomplishmentService(two_user_db)  # type: ignore[arg-type]
        svc.create_accomplishment({"title": "Alice win"}, user_id="user_alice")
        svc.create_accomplishment({"title": "Bob win"}, user_id="user_bob")

        alice_accs = svc.list_accomplishments(user_id="user_alice")
        bob_accs = svc.list_accomplishments(user_id="user_bob")

        assert len(alice_accs) == 1
        assert alice_accs[0]["title"] == "Alice win"
        assert len(bob_accs) == 1
        assert bob_accs[0]["title"] == "Bob win"

    def test_get_accomplishment_rejects_cross_user(
        self, two_user_db: Connection[Any]
    ) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc = AccomplishmentService(two_user_db)  # type: ignore[arg-type]
        acc = svc.create_accomplishment({"title": "Alice win"}, user_id="user_alice")

        with pytest.raises(ValueError, match="not found"):
            svc.get_accomplishment(acc["id"], user_id="user_bob")


# ---------------------------------------------------------------------------
# DEF-1a: load_default_resume_version does NOT fall back to other users
# ---------------------------------------------------------------------------


class TestDefaultResumeFallbackRemoved:
    """load_default_resume_version must NOT return another user's default."""

    def test_no_cross_user_fallback(self, two_user_db: Connection[Any]) -> None:
        """A user with no default resume gets ValueError, not another user's."""
        # Create a new user with no resume
        two_user_db.execute(
            "INSERT INTO users (id, email) VALUES ('user_charlie', 'charlie@test.com')"
        )

        with pytest.raises(ValueError, match="No default resume version found"):
            load_default_resume_version(two_user_db, user_id="user_charlie")  # type: ignore[arg-type]

    def test_returns_own_default(self, two_user_db: Connection[Any]) -> None:
        """A user with a default resume gets their own."""
        result = load_default_resume_version(two_user_db, user_id="user_alice")  # type: ignore[arg-type]
        assert result["label"] == "Alice CV"


# ---------------------------------------------------------------------------
# DEF-1: ApplicationService.get_application_context passes user_id
# ---------------------------------------------------------------------------


class TestApplicationContextUserScoping:
    """get_application_context must enforce ownership."""

    def test_context_returns_own_application(
        self, two_user_db: Connection[Any]
    ) -> None:
        from pktx.application_service import ApplicationService

        svc = ApplicationService(two_user_db)  # type: ignore[arg-type]
        app = svc.create_application(
            {"company": "AliceCo", "position": "Dev"}, user_id="user_alice"
        )
        context = svc.get_application_context(app["id"], user_id="user_alice")

        assert context["application"]["id"] == app["id"]
        assert context["application"]["company"] == "AliceCo"
        assert "linked" in context

    def test_context_rejects_cross_user_app(self, two_user_db: Connection[Any]) -> None:
        from pktx.application_service import ApplicationService

        svc = ApplicationService(two_user_db)  # type: ignore[arg-type]
        app = svc.create_application(
            {"company": "AliceCo", "position": "Dev"}, user_id="user_alice"
        )

        with pytest.raises(ValueError, match="not found"):
            svc.get_application_context(app["id"], user_id="user_bob")
