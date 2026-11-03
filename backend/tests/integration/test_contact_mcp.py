"""Integration tests for contact MCP tools — create→list→get→update→delete roundtrip."""

import asyncio
from typing import Any, cast

import pytest
from fastmcp.exceptions import ToolError
from psycopg import Connection

from pktx.auth import current_user_id_var
from pktx.db import DBConnection

_TEST_USER = "contact_mcp_test_user"


@pytest.fixture
def seeded_db(db_conn: Connection[Any]) -> Connection[Any]:
    db_conn.execute(
        "INSERT INTO users (id, email) VALUES (%s, 'mcp@test.com') "
        "ON CONFLICT (id) DO NOTHING",
        (_TEST_USER,),
    )
    return db_conn


def _get_tool_fn(mcp: Any, name: str) -> Any:
    tools = asyncio.run(mcp.list_tools())
    for tool in tools:
        if tool.name == name:
            return tool.fn
    registered = [t.name for t in tools]
    raise KeyError(f"MCP tool '{name}' not found. Registered: {registered}")


class TestContactMcpRoundtrip:
    def test_full_roundtrip(self, seeded_db: Connection[Any]) -> None:
        from fastmcp import FastMCP

        from pktx.contact_service import ContactService
        from pktx.tools.contact_tools import register_contact_tools

        conn = cast(DBConnection, seeded_db)
        svc = ContactService(conn)
        mcp = FastMCP("test")
        register_contact_tools(mcp, lambda: svc)

        token = current_user_id_var.set(_TEST_USER)
        try:
            create_fn = _get_tool_fn(mcp, "create_contact")
            list_fn = _get_tool_fn(mcp, "list_contacts")
            get_fn = _get_tool_fn(mcp, "get_contact")
            update_fn = _get_tool_fn(mcp, "update_contact")
            delete_fn = _get_tool_fn(mcp, "delete_contact")

            # Create
            created = create_fn(
                name="Test Person", company="TestCorp", tags=["mcp-test"]
            )
            assert created["name"] == "Test Person"
            assert created["tags"] == ["mcp-test"]

            # List — verify it appears
            contacts = list_fn()
            assert any(c["name"] == "Test Person" for c in contacts)
            contact_id = created["id"]

            # Get full record
            contact = get_fn(id=contact_id)
            assert isinstance(contact, dict)
            assert contact["name"] == "Test Person"
            assert contact["company"] == "TestCorp"

            # Update
            update_result = update_fn(
                id=contact_id, company="UpdatedCorp", notes="Updated notes"
            )
            assert update_result["company"] == "UpdatedCorp"
            assert update_result["name"] == "Test Person"

            updated = get_fn(id=contact_id)
            assert updated["company"] == "UpdatedCorp"
            assert updated["notes"] == "Updated notes"

            # Delete
            del_result = delete_fn(id=contact_id)
            assert del_result == {"id": contact_id, "name": "Test Person"}

            # Verify gone
            with pytest.raises(ToolError, match="not found"):
                get_fn(id=contact_id)

        finally:
            current_user_id_var.reset(token)

    def test_list_filter_by_tag(self, seeded_db: Connection[Any]) -> None:
        from fastmcp import FastMCP

        from pktx.contact_service import ContactService
        from pktx.tools.contact_tools import register_contact_tools

        conn = cast(DBConnection, seeded_db)
        svc = ContactService(conn)
        mcp = FastMCP("test2")
        register_contact_tools(mcp, lambda: svc)

        token = current_user_id_var.set(_TEST_USER)
        try:
            create_fn = _get_tool_fn(mcp, "create_contact")
            list_fn = _get_tool_fn(mcp, "list_contacts")

            create_fn(name="Alice", tags=["alpha", "beta"])
            create_fn(name="Bob", tags=["alpha"])

            alpha_beta = list_fn(tag="beta")
            names = [c["name"] for c in alpha_beta]
            assert "Alice" in names
            assert "Bob" not in names
        finally:
            current_user_id_var.reset(token)

    def test_require_user_id_without_context(self, seeded_db: Connection[Any]) -> None:
        from fastmcp import FastMCP

        from pktx.contact_service import ContactService
        from pktx.tools.contact_tools import register_contact_tools

        conn = cast(DBConnection, seeded_db)
        svc = ContactService(conn)
        mcp = FastMCP("test3")
        register_contact_tools(mcp, lambda: svc)

        list_fn = _get_tool_fn(mcp, "list_contacts")
        with pytest.raises(RuntimeError):
            list_fn()
