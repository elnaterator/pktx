"""Integration tests: contact comm MCP tools roundtrip + cross-parent search."""

import asyncio
from typing import Any, cast

import pytest
from psycopg import Connection

from pktx.auth import current_user_id_var
from pktx.db import DBConnection

_TEST_USER = "contact_comm_mcp_user"


@pytest.fixture
def seeded_db(db_conn: Connection[Any]) -> Connection[Any]:
    db_conn.execute(
        "INSERT INTO users (id, email) VALUES (%s, 'comm@test.com') "
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


class TestContactCommMcpRoundtrip:
    def test_add_list_update_delete(self, seeded_db: Connection[Any]) -> None:
        from fastmcp import FastMCP

        from pktx.communication_service import ContactCommunicationService
        from pktx.contact_service import ContactService
        from pktx.tools.contact_tools import register_contact_tools

        conn = cast(DBConnection, seeded_db)
        contact_svc = ContactService(conn)
        comm_svc = ContactCommunicationService(conn)
        mcp = FastMCP("test")
        register_contact_tools(mcp, lambda: contact_svc, lambda: comm_svc)

        token = current_user_id_var.set(_TEST_USER)
        try:
            create_contact_fn = _get_tool_fn(mcp, "create_contact")
            add_comm_fn = _get_tool_fn(mcp, "add_contact_communication")
            list_comm_fn = _get_tool_fn(mcp, "list_contact_communications")
            update_comm_fn = _get_tool_fn(mcp, "update_contact_communication")
            remove_comm_fn = _get_tool_fn(mcp, "remove_contact_communication")

            # Create contact
            cid = create_contact_fn(name="Jane Recruiter")["id"]

            # Add communication
            add_result = add_comm_fn(
                contact_id=cid,
                type="email",
                direction="sent",
                body="Intro email",
                date="2025-04-01",
                subject="Intro",
                tags=["outreach"],
            )
            assert add_result["subject"] == "Intro"
            comm_id = add_result["id"]

            # List
            comms = list_comm_fn(contact_id=cid)
            assert isinstance(comms, list)
            assert len(comms) == 1
            assert comms[0]["body"] == "Intro email"
            assert comms[0]["tags"] == ["outreach"]

            # Update
            update_result = update_comm_fn(comm_id=comm_id, subject="Updated Subject")
            assert update_result["id"] == comm_id
            assert update_result["subject"] == "Updated Subject"

            # Verify update
            comms2 = list_comm_fn(contact_id=cid)
            assert comms2[0]["subject"] == "Updated Subject"

            # Delete
            del_result = remove_comm_fn(comm_id=comm_id)
            assert del_result == {"id": comm_id, "subject": "Updated Subject"}

            # Verify deleted
            comms3 = list_comm_fn(contact_id=cid)
            assert comms3 == []

        finally:
            current_user_id_var.reset(token)


class TestSearchCrossParents:
    def test_search_finds_contact_comm(self, seeded_db: Connection[Any]) -> None:
        from fastmcp import FastMCP

        from pktx.communication_service import ContactCommunicationService
        from pktx.contact_service import ContactService
        from pktx.tools.contact_tools import register_contact_tools

        conn = cast(DBConnection, seeded_db)
        contact_svc = ContactService(conn)
        comm_svc = ContactCommunicationService(conn)
        mcp = FastMCP("test")
        register_contact_tools(mcp, lambda: contact_svc, lambda: comm_svc)

        token = current_user_id_var.set(_TEST_USER)
        try:
            create_fn = _get_tool_fn(mcp, "create_contact")
            add_fn = _get_tool_fn(mcp, "add_contact_communication")
            search_fn = _get_tool_fn(mcp, "search_communications")

            cid = create_fn(name="Search Test Contact")["id"]

            add_fn(
                contact_id=cid,
                type="email",
                direction="received",
                body="Unique search term zxqw",
                date="2025-05-01",
                tags=["search-tag"],
            )

            results = search_fn(q="zxqw")
            assert isinstance(results, list)
            assert len(results) >= 1
            assert any("zxqw" in r["body"] for r in results)

            results_by_tag = search_fn(tag="search-tag")
            assert any("search-tag" in r["tags"] for r in results_by_tag)

            results_all = search_fn()
            assert all(r["parent_type"] == "contact" for r in results_all)

        finally:
            current_user_id_var.reset(token)
