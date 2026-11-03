"""Integration tests for resource linking — MCP tools + service + cascade delete."""

import asyncio
from typing import Any, cast

import pytest
from psycopg import Connection

from pktx.auth import current_user_id_var
from pktx.db import DBConnection

_TEST_USER = "link_int_user"


def _ref_id(ref: Any) -> int:
    """Return the ID from a ResourceRef (Pydantic model) or dict."""
    return ref.id if hasattr(ref, "id") else ref["id"]


def _get_tool_fn(mcp: Any, name: str) -> Any:
    tools = asyncio.run(mcp.list_tools())
    for tool in tools:
        if tool.name == name:
            return tool.fn
    registered = [t.name for t in tools]
    raise KeyError(f"MCP tool '{name}' not found. Registered: {registered}")


@pytest.fixture
def seeded_db(db_conn: Connection[Any]) -> Connection[Any]:
    db_conn.execute(
        "INSERT INTO users (id, email) VALUES (%s, 'int@test.com') "
        "ON CONFLICT (id) DO NOTHING",
        (_TEST_USER,),
    )
    return db_conn


class TestLinkMcpRoundtrip:
    def test_link_unlink_roundtrip(self, seeded_db: Connection[Any]) -> None:
        from fastmcp import FastMCP

        from pktx.application_service import ApplicationService
        from pktx.link_service import LinkService
        from pktx.note_service import NoteService
        from pktx.tools.application_tools import register_application_tools
        from pktx.tools.link_tools import register_link_tools
        from pktx.tools.note_tools import register_note_tools

        conn = cast(DBConnection, seeded_db)
        note_svc = NoteService(conn)
        app_svc = ApplicationService(conn)
        link_svc = LinkService(conn)

        mcp = FastMCP("test")
        register_note_tools(mcp, lambda: note_svc)
        register_application_tools(mcp, lambda: app_svc)
        register_link_tools(mcp, lambda: link_svc)

        token = current_user_id_var.set(_TEST_USER)
        try:
            create_note_fn = _get_tool_fn(mcp, "create_note")
            create_app_fn = _get_tool_fn(mcp, "create_application")
            link_fn = _get_tool_fn(mcp, "link_resources")
            unlink_fn = _get_tool_fn(mcp, "unlink_resources")

            # Create resources
            note_id = create_note_fn(title="Integration Note")["id"]
            app_id = create_app_fn(company="Acme", position="Dev", status="Interested")[
                "id"
            ]

            # Link
            link_msg = link_fn(
                a_type="note", a_id=note_id, b_type="application", b_id=app_id
            )
            assert link_msg == {
                "a_type": "note",
                "a_id": note_id,
                "b_type": "application",
                "b_id": app_id,
            }

            # Verify note → app
            note_data = note_svc.get_note(note_id, user_id=_TEST_USER)
            app_links = note_data.get("links", {}).get("application", [])
            assert any(_ref_id(r) == app_id for r in app_links)

            # Verify app → note
            app_data = app_svc.get_application(app_id, user_id=_TEST_USER)
            note_links = app_data.get("links", {}).get("note", [])
            assert any(_ref_id(r) == note_id for r in note_links)

            # Unlink
            unlink_msg = unlink_fn(
                a_type="note", a_id=note_id, b_type="application", b_id=app_id
            )
            assert unlink_msg == link_msg

            # Verify cleared
            note_data2 = note_svc.get_note(note_id, user_id=_TEST_USER)
            assert note_data2.get("links", {}).get("application", []) == []

        finally:
            current_user_id_var.reset(token)


class TestLinkCascadeDelete:
    def test_delete_note_removes_links(self, seeded_db: Connection[Any]) -> None:
        from pktx.application_service import ApplicationService
        from pktx.link_service import LinkService
        from pktx.note_service import NoteService

        conn = cast(DBConnection, seeded_db)
        note_svc = NoteService(conn)
        app_svc = ApplicationService(conn)
        link_svc = LinkService(conn)

        token = current_user_id_var.set(_TEST_USER)
        try:
            note = note_svc.create_note({"title": "Cascade Note"}, user_id=_TEST_USER)
            app = app_svc.create_application(
                {"company": "Co", "position": "Eng", "status": "Interested"},
                user_id=_TEST_USER,
            )
            note_id = note["id"]
            app_id = app["id"]

            link_svc.link("note", note_id, "application", app_id, _TEST_USER)

            # Verify link exists in app
            app_data = app_svc.get_application(app_id, user_id=_TEST_USER)
            assert any(
                _ref_id(r) == note_id for r in app_data.get("links", {}).get("note", [])
            )

            # Delete note — should cascade-remove the link
            note_svc.delete_note(note_id, user_id=_TEST_USER)

            # App should no longer have the note link
            app_data2 = app_svc.get_application(app_id, user_id=_TEST_USER)
            assert app_data2.get("links", {}).get("note", []) == []

            # raw table check
            row = seeded_db.execute(
                "SELECT COUNT(*) AS c FROM resource_link "
                "WHERE (left_type = 'note' AND left_id = %s) "
                "OR (right_type = 'note' AND right_id = %s)",
                (note_id, note_id),
            ).fetchone()
            assert row is not None
            assert row["c"] == 0

        finally:
            current_user_id_var.reset(token)
