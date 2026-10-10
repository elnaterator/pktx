"""MCP tools for registry-driven resume sections, entry ids and layout."""

import asyncio
from typing import Any

import pytest
from fastmcp import FastMCP
from psycopg import Connection

from pktx.auth import current_user_id_var
from pktx.resume_service import ResumeService
from pktx.tools.resume_tools import register_resume_tools

USER = "mcp_sections_user"


@pytest.fixture
def tools(db_conn: Connection[Any]):
    db_conn.execute("INSERT INTO users (id) VALUES (%s)", (USER,))
    svc = ResumeService(db_conn)  # type: ignore[arg-type]
    vid = svc.create_resume("Main", user_id=USER)["id"]
    mcp = FastMCP("test")
    register_resume_tools(mcp, lambda: svc)
    fns = {t.name: t.fn for t in asyncio.run(mcp.list_tools())}  # type: ignore[attr-defined]
    token = current_user_id_var.set(USER)
    try:
        yield vid, fns
    finally:
        current_user_id_var.reset(token)


def test_entry_roundtrip_by_id(tools) -> None:
    vid, fns = tools
    msg = fns["add_resume_entry"](vid, "projects", {"name": "pktx"})
    assert "id=" in msg
    entries = fns["get_resume_section"]("projects", vid)
    eid = entries[0]["id"]
    fns["update_resume_entry"](vid, "projects", eid, {"name": "pktx2"})
    assert fns["get_resume_section"]("projects", vid)[0]["name"] == "pktx2"
    fns["remove_resume_entry"](vid, "projects", eid)
    assert fns["get_resume_section"]("projects", vid) == []


def test_layout_and_custom_section(tools) -> None:
    vid, fns = tools
    out = fns["update_resume_layout"](vid, [{"section": "skills", "visible": False}])
    assert out.startswith("Updated layout: skills (hidden)")

    msg = fns["add_resume_custom_section"](vid, "Talks")
    key = msg[msg.index("(") + 1 : -1]
    assert key.startswith("custom:")
    fns["add_resume_entry"](vid, key, {"heading": "KubeCon"})
    assert fns["get_resume_section"](key, vid)[0]["heading"] == "KubeCon"
    data = fns["get_resume"](vid)["resume_data"]
    assert data["custom_sections"][key.split(":")[1]]["title"] == "Talks"
    assert data["layout"][0]["section"] == "skills"

    fns["remove_resume_custom_section"](vid, key)
    with pytest.raises(ValueError, match="Unknown custom section"):
        fns["get_resume_section"](key, vid)


def test_invalid_section_rejected(tools) -> None:
    vid, fns = tools
    with pytest.raises(ValueError, match="Invalid section"):
        fns["get_resume_section"]("hobbies", vid)
    with pytest.raises(ValueError, match="Invalid section"):
        fns["add_resume_entry"](vid, "hobbies", {})
