"""MCP contract for non-resume tools, driven through an in-memory client.

A failed write must come back as ``isError`` (so ``DBSessionToolMiddleware``
rolls back) and leave data unchanged; a successful write returns the object.
"""

from typing import Any

import pytest
from fastmcp import FastMCP
from psycopg import Connection

from pktx.accomplishment_service import AccomplishmentService
from pktx.application_service import ApplicationService
from pktx.communication_service import ContactCommunicationService
from pktx.contact_service import ContactService
from pktx.link_service import LinkService
from pktx.note_service import NoteService
from pktx.tools.accomplishment_tools import register_accomplishment_tools
from pktx.tools.application_tools import register_application_tools
from pktx.tools.contact_tools import register_contact_tools
from pktx.tools.link_tools import register_link_tools
from pktx.tools.note_tools import register_note_tools
from tests.mcp_client import Mcp

USER = "mcp_tools_user"


@pytest.fixture
def mcp(db_conn: Connection[Any]) -> Mcp:
    db_conn.execute("INSERT INTO users (id) VALUES (%s)", (USER,))
    conn: Any = db_conn
    notes, accs, apps = (
        NoteService(conn),
        AccomplishmentService(conn),
        ApplicationService(conn),
    )
    contacts, comms, links = (
        ContactService(conn),
        ContactCommunicationService(conn),
        LinkService(conn),
    )
    server = FastMCP("test")
    register_note_tools(server, lambda: notes)
    register_accomplishment_tools(server, lambda: accs)
    register_application_tools(server, lambda: apps)
    register_contact_tools(server, lambda: contacts, lambda: comms)
    register_link_tools(server, lambda: links)
    return Mcp(server, USER)


def test_every_tool_returns_structured_output(mcp: Mcp) -> None:
    for name, tool in mcp.tools().items():
        assert tool.outputSchema is not None, name
        assert "string" not in str(tool.outputSchema.get("type")), name


def test_note_tools(mcp: Mcp) -> None:
    note = mcp.call("create_note", title="T", tags=["A"])
    assert note["title"] == "T" and note["tags"] == ["a"]
    assert mcp.call("update_note", id=note["id"], content="c")["content"] == "c"

    with pytest.raises(RuntimeError, match="(?i)title"):
        mcp.call("update_note", id=note["id"], title=" ")
    with pytest.raises(RuntimeError, match="not found"):
        mcp.call("update_note", id=999999, content="x")
    with pytest.raises(RuntimeError, match="(?i)title"):
        mcp.call("create_note", title="")
    assert mcp.call("get_note", id=note["id"])["title"] == "T"
    assert len(mcp.call("list_notes")) == 1

    assert mcp.call("delete_note", id=note["id"]) == {"id": note["id"], "title": "T"}
    with pytest.raises(RuntimeError, match="not found"):
        mcp.call("get_note", id=note["id"])


def test_accomplishment_tools(mcp: Mcp) -> None:
    acc = mcp.call("create_accomplishment", title="Shipped", result="r")
    assert acc["result"] == "r"
    updated = mcp.call("update_accomplishment", id=acc["id"], task="t")
    assert updated["task"] == "t" and updated["result"] == "r"

    with pytest.raises(RuntimeError):
        mcp.call("update_accomplishment", id=acc["id"], accomplishment_date="nope")
    with pytest.raises(RuntimeError, match="not found"):
        mcp.call("delete_accomplishment", id=999999)
    assert mcp.call("get_accomplishment", id=acc["id"])["task"] == "t"

    assert mcp.call("delete_accomplishment", id=acc["id"]) == {
        "id": acc["id"],
        "title": "Shipped",
    }


def test_application_tools(mcp: Mcp) -> None:
    app = mcp.call("create_application", company="Acme", position="Dev")
    assert app["company"] == "Acme" and app["status"] == "Interested"
    assert mcp.call("update_application", id=app["id"], notes="n")["notes"] == "n"

    with pytest.raises(RuntimeError, match="http"):
        mcp.call("update_application", id=app["id"], url="javascript:alert(1)")
    with pytest.raises(RuntimeError, match="http"):
        mcp.call("create_application", company="X", position="Y", url="ftp://x")
    with pytest.raises(RuntimeError, match="not found"):
        mcp.call("get_application", id=999999)
    assert mcp.call("get_application", id=app["id"])["url"] is None
    assert len(mcp.call("list_applications")) == 1

    assert mcp.call("delete_application", id=app["id"]) == {
        "id": app["id"],
        "company": "Acme",
        "position": "Dev",
    }


def test_contact_and_communication_tools(mcp: Mcp) -> None:
    contact = mcp.call("create_contact", name="Ann", company="Co")
    assert mcp.call("update_contact", id=contact["id"], title="CTO")["title"] == "CTO"

    with pytest.raises(RuntimeError):
        mcp.call("update_contact", id=contact["id"], linkedin_url="javascript:x")
    with pytest.raises(RuntimeError):
        mcp.call("create_contact", name=" ")
    assert mcp.call("get_contact", id=contact["id"])["linkedin_url"] is None

    comm = mcp.call(
        "add_contact_communication",
        contact_id=contact["id"],
        type="email",
        direction="sent",
        body="hi",
        date="2026-01-02",
        subject="Hello",
    )
    assert comm["subject"] == "Hello" and comm["body"] == "hi"
    assert (
        mcp.call("update_contact_communication", comm_id=comm["id"], body="yo")["body"]
        == "yo"
    )

    with pytest.raises(RuntimeError):
        mcp.call("update_contact_communication", comm_id=comm["id"], type="fax")
    with pytest.raises(RuntimeError, match="not found"):
        mcp.call("list_contact_communications", contact_id=999999)
    with pytest.raises(RuntimeError):
        mcp.call(
            "add_contact_communication",
            contact_id=contact["id"],
            type="email",
            direction="sideways",
            body="b",
            date="2026-01-02",
        )
    assert [c["id"] for c in mcp.call("search_communications", q="yo")] == [comm["id"]]
    [only] = mcp.call("list_contact_communications", contact_id=contact["id"])
    assert only["type"] == "email" and only["body"] == "yo"

    assert mcp.call("remove_contact_communication", comm_id=comm["id"]) == {
        "id": comm["id"],
        "subject": "Hello",
    }
    assert mcp.call("delete_contact", id=contact["id"]) == {
        "id": contact["id"],
        "name": "Ann",
    }


def test_link_tools(mcp: Mcp) -> None:
    note = mcp.call("create_note", title="N")
    app = mcp.call("create_application", company="Acme", position="Dev")
    link = {"a_type": "note", "a_id": note["id"], "b_type": "application"}
    link["b_id"] = app["id"]
    assert mcp.call("link_resources", **link) == link
    assert mcp.call("get_note", id=note["id"])["links"]["application"]

    with pytest.raises(RuntimeError):
        mcp.call("link_resources", **{**link, "b_type": "widget"})
    with pytest.raises(RuntimeError, match="not found"):
        mcp.call("link_resources", **{**link, "b_id": 999999})
    with pytest.raises(RuntimeError, match="itself"):
        mcp.call("link_resources", **{**link, "b_type": "note", "b_id": note["id"]})
    assert len(mcp.call("get_note", id=note["id"])["links"]["application"]) == 1

    assert mcp.call("unlink_resources", **link) == link
    assert not mcp.call("get_note", id=note["id"])["links"].get("application")


def test_link_types_advertised_in_schema(mcp: Mcp) -> None:
    schema = mcp.tools()["link_resources"].inputSchema
    assert "contact" in str(schema["properties"]["a_type"])
