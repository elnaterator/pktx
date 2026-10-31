"""MCP resume tools, driven through an in-memory FastMCP client."""

from typing import Any

import pytest
from fastmcp import FastMCP
from psycopg import Connection

from pktx.resume_service import ResumeService
from pktx.tools.resume_tools import register_resume_tools
from tests.mcp_client import Mcp

USER = "mcp_resume_user"

TOOLS = {
    "list_resumes",
    "get_resume",
    "create_resume",
    "update_resume",
    "delete_resume",
    "update_resume_basics",
    "add_resume_entry",
    "update_resume_entry",
    "remove_resume_entry",
    "reorder_resume_entries",
}


@pytest.fixture
def mcp(db_conn: Connection[Any]) -> Mcp:
    db_conn.execute("INSERT INTO users (id) VALUES (%s)", (USER,))
    svc = ResumeService(db_conn)  # type: ignore[arg-type]
    svc.create_resume("Main", user_id=USER)
    svc.update_resume(svc.list_resumes(USER)[0]["id"], user_id=USER, is_default=True)
    server = FastMCP("test")
    register_resume_tools(server, lambda: svc)
    return Mcp(server, USER)


def _ids(mcp: Mcp) -> list[str]:
    return [w["id"] for w in mcp.call("get_resume", section="work")["data"]]


def _vid(mcp: Mcp) -> int:
    return mcp.call("list_resumes")[0]["id"]


def test_exactly_the_documented_tools(mcp: Mcp) -> None:
    assert set(mcp.tools()) == TOOLS


def test_schemas_are_typed(mcp: Mcp) -> None:
    tools = mcp.tools()
    sections = tools["add_resume_entry"].inputSchema["properties"]["section"]["enum"]
    assert (
        sections[0] == "work" and "certificates" in sections and "interests" in sections
    )
    entry_help = tools["add_resume_entry"].inputSchema["properties"]["entry"][
        "description"
    ]
    assert "startDate" in entry_help and "studyType" in entry_help
    basics = tools["update_resume_basics"].inputSchema
    assert "postalCode" in str(basics) and "profiles" in str(basics)
    assert "work" in str(tools["create_resume"].inputSchema)


def test_get_resume_default_and_section(mcp: Mcp) -> None:
    r = mcp.call("get_resume")
    assert r["is_default"] is True and r["data"] == {}
    assert mcp.call("get_resume", section="work") == {
        "id": r["id"],
        "section": "work",
        "data": [],
    }
    assert mcp.call("get_resume", section="basics")["data"] == {}


def test_create_and_update_with_json_resume(mcp: Mcp) -> None:
    created = mcp.call(
        "create_resume",
        label="Imported",
        tags=["Backend"],
        data={"basics": {"name": "Ada"}, "work": [{"name": "X", "startDate": "2020"}]},
    )
    assert created["tags"] == ["backend"]
    assert created["data"]["work"][0]["id"]

    updated = mcp.call(
        "update_resume", id=created["id"], label="Renamed", is_default=True
    )
    assert updated["label"] == "Renamed" and updated["is_default"] is True
    assert mcp.call("get_resume")["id"] == created["id"]

    replaced = mcp.call(
        "update_resume", id=created["id"], data={"basics": {"name": "Bo"}}
    )
    assert replaced["data"] == {"basics": {"name": "Bo"}}


def test_entry_lifecycle_returns_objects(mcp: Mcp) -> None:
    vid = _vid(mcp)
    a = mcp.call("add_resume_entry", id=vid, section="work", entry={"name": "A"})
    b = mcp.call(
        "add_resume_entry", id=vid, section="work", entry={"name": "B"}, position=0
    )
    assert a["id"] and b["id"] != a["id"]
    assert _ids(mcp) == [b["id"], a["id"]]

    upd = mcp.call(
        "update_resume_entry",
        id=vid,
        section="work",
        entry_id=a["id"],
        entry={"position": "Dev", "start_date": "2024-02"},
    )
    assert upd == {
        "id": a["id"],
        "name": "A",
        "position": "Dev",
        "startDate": "2024-02",
    }

    order = mcp.call(
        "reorder_resume_entries",
        id=vid,
        section="work",
        entry_ids=[a["id"], b["id"]],
    )
    assert [w["id"] for w in order] == [a["id"], b["id"]]

    removed = mcp.call("remove_resume_entry", id=vid, section="work", entry_id=b["id"])
    assert removed["id"] == b["id"]
    assert _ids(mcp) == [a["id"]]


def test_update_basics_is_partial(mcp: Mcp) -> None:
    vid = _vid(mcp)
    mcp.call("update_resume_basics", id=vid, basics={"name": "Ada", "email": "a@b.co"})
    out = mcp.call(
        "update_resume_basics",
        id=vid,
        basics={"label": "Eng", "location": {"countryCode": "US"}},
    )
    assert out == {
        "name": "Ada",
        "email": "a@b.co",
        "label": "Eng",
        "location": {"countryCode": "US"},
    }
    cleared = mcp.call("update_resume_basics", id=vid, basics={"label": ""})
    assert "label" not in cleared


def test_delete_returns_deleted_summary(mcp: Mcp) -> None:
    other = mcp.call("create_resume", label="Temp")
    assert mcp.call("delete_resume", id=other["id"]) == {
        "id": other["id"],
        "label": "Temp",
    }


@pytest.mark.parametrize(
    "tool,args,match",
    [
        ("add_resume_entry", {"section": "hobbies", "entry": {"name": "x"}}, "section"),
        ("add_resume_entry", {"section": "work", "entry": {}}, "at least one field"),
        (
            "add_resume_entry",
            {"section": "work", "entry": {"startDate": "May 2020"}},
            "startDate",
        ),
        ("add_resume_entry", {"section": "work", "entry": {"zzz": 1}}, "Unknown field"),
        (
            "update_resume_entry",
            {"section": "work", "entry_id": "nope", "entry": {"name": "x"}},
            "not found",
        ),
        (
            "reorder_resume_entries",
            {"section": "work", "entry_ids": ["x"]},
            "exactly once",
        ),
        ("update_resume_basics", {"basics": {"email": "nope"}}, "email"),
        ("update_resume", {"is_default": False}, "Cannot unset"),
        ("update_resume", {}, "Nothing to update"),
        ("get_resume", {"section": "contact"}, "section"),
    ],
)
def test_errors_are_tool_errors_not_strings(
    mcp: Mcp, tool: str, args: dict[str, Any], match: str
) -> None:
    with pytest.raises(RuntimeError, match=match):
        mcp.call(tool, id=_vid(mcp), **args)


def test_invalid_import_changes_nothing(mcp: Mcp) -> None:
    vid = _vid(mcp)
    mcp.call("add_resume_entry", id=vid, section="work", entry={"name": "Keep"})
    with pytest.raises(RuntimeError):
        mcp.call(
            "update_resume",
            id=vid,
            label="Changed",
            data={"work": [{"endDate": "bad"}]},
        )
    r = mcp.call("get_resume", id=vid)
    assert r["label"] == "Main" and r["data"]["work"][0]["name"] == "Keep"
