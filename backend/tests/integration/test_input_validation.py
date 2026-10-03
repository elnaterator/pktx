"""Bad-input and data-integrity tests for the 027 fixes (H7–H9, C4, M14, H5).

Every case goes through the real REST router (or MCP tool / service where
that is the interface under test) against Postgres.
"""

import asyncio
from typing import Any

import pytest
from fastmcp import FastMCP
from psycopg import Connection
from starlette.testclient import TestClient

from pktx.application_service import ApplicationService
from pktx.auth import current_user_id_var
from pktx.communication_service import ContactCommunicationService
from pktx.contact_service import ContactService
from pktx.link_service import LinkService
from pktx.note_service import NoteService
from pktx.resume_service import ResumeService
from tests.helpers import build_full_app, user_client

CAROL = "user_carol"
BAD_URLS = ["javascript:alert(1)", "data:text/html,<b>x</b>", "ftp://example.com"]
BAD_TAGS = ["backend", [1], [f"t{i}" for i in range(51)], ["x" * 51]]


@pytest.fixture
def carol(db_conn: Connection[Any]) -> TestClient:
    db_conn.execute("INSERT INTO users (id) VALUES (%s)", (CAROL,))
    return user_client(build_full_app(db_conn), CAROL)


def _resume_url(client: TestClient) -> str:
    rid = client.post("/api/resumes", json={"label": "Main"}).json()["id"]
    client.post(f"/api/resumes/{rid}/default")
    return f"/api/resumes/{rid}"


def _get_tool_fn(mcp: FastMCP, name: str) -> Any:
    return next(t.fn for t in asyncio.run(mcp.list_tools()) if t.name == name)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# H7/H8 — tags
# ---------------------------------------------------------------------------


def test_null_tags_store_empty_list_and_tag_listing_still_works(
    carol: TestClient,
) -> None:
    note = carol.post("/api/notes", json={"title": "n", "tags": ["a"]}).json()

    resp = carol.patch(f"/api/notes/{note['id']}", json={"tags": None})

    assert resp.status_code == 200
    assert resp.json()["tags"] == []
    assert carol.get("/api/tags").status_code == 200


@pytest.mark.parametrize("tags", BAD_TAGS)
def test_bad_tags_rejected_with_422(carol: TestClient, tags: Any) -> None:
    assert (
        carol.post("/api/notes", json={"title": "n", "tags": tags}).status_code == 422
    )
    app = carol.post("/api/applications", json={"company": "c", "position": "p"})
    patch = carol.patch(f"/api/applications/{app.json()['id']}", json={"tags": tags})
    assert patch.status_code == 422


# ---------------------------------------------------------------------------
# C4 — http(s)-only URLs (REST 422, MCP tool error)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url", BAD_URLS)
def test_non_http_urls_rejected_everywhere(carol: TestClient, url: str) -> None:
    app_body = {"company": "c", "position": "p", "url": url}
    assert carol.post("/api/applications", json=app_body).status_code == 422

    app_id = carol.post("/api/applications", json={"company": "c", "position": "p"})
    patch = carol.patch(f"/api/applications/{app_id.json()['id']}", json={"url": url})
    assert patch.status_code == 422

    contact = {"name": "x", "linkedin_url": url}
    assert carol.post("/api/contacts", json=contact).status_code == 422

    resume = _resume_url(carol)
    for field in ("linkedin", "website", "github"):
        resp = carol.put(f"{resume}/contact", json={field: url})
        assert resp.status_code == 422, field


def test_http_urls_accepted(carol: TestClient) -> None:
    body = {"company": "c", "position": "p", "url": "https://jobs.example.com/1"}
    assert carol.post("/api/applications", json=body).status_code == 201
    resume = _resume_url(carol)
    resp = carol.put(f"{resume}/contact", json={"website": "https://me.dev"})
    assert resp.status_code == 200
    assert carol.get(f"{resume}/contact").json()["website"] == "https://me.dev"


def test_mcp_create_application_rejects_javascript_url(
    db_conn: Connection[Any],
) -> None:
    from pktx.tools.application_tools import register_application_tools

    db_conn.execute("INSERT INTO users (id) VALUES (%s)", (CAROL,))
    mcp = FastMCP("test")
    svc = ApplicationService(db_conn)  # type: ignore[arg-type]
    register_application_tools(mcp, lambda: svc)
    token = current_user_id_var.set(CAROL)
    try:
        with pytest.raises(ValueError, match="http"):
            _get_tool_fn(mcp, "create_application")(
                company="c", position="p", url="javascript:alert(1)"
            )
    finally:
        current_user_id_var.reset(token)


# ---------------------------------------------------------------------------
# H9 — update_entry validates through the model
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "patch", [{"title": 123}, {"highlights": "not a list"}, {"company": None}]
)
def test_update_entry_wrong_types_422_and_resume_stays_readable(
    carol: TestClient, patch: dict[str, Any]
) -> None:
    resume = _resume_url(carol)
    carol.post(f"{resume}/experience/entries", json={"title": "t", "company": "c"})

    resp = carol.put(f"{resume}/experience/entries/0", json=patch)

    assert resp.status_code == 422
    after = carol.get(resume)
    assert after.status_code == 200
    assert after.json()["resume_data"]["experience"][0]["title"] == "t"


def test_update_entry_drops_unknown_fields(carol: TestClient) -> None:
    resume = _resume_url(carol)
    carol.post(f"{resume}/experience/entries", json={"title": "t", "company": "c"})

    resp = carol.put(f"{resume}/experience/entries/0", json={"bogus": {"x": 1}})

    assert resp.status_code == 200
    assert "bogus" not in carol.get(f"{resume}/experience").json()[0]


# ---------------------------------------------------------------------------
# M14 — length limits
# ---------------------------------------------------------------------------


def test_oversized_fields_rejected_with_422(carol: TestClient) -> None:
    long = "x" * 100_001
    resume = _resume_url(carol)
    contact = carol.post("/api/contacts", json={"name": "c"}).json()
    comm = {"type": "email", "direction": "sent", "body": "b", "date": "2024-01-01"}

    cases = [
        ("POST", "/api/notes", {"title": "n", "content": long}),
        ("POST", "/api/notes", {"title": "x" * 201}),
        ("POST", "/api/applications", {"company": "x" * 201, "position": "p"}),
        ("POST", "/api/accomplishments", {"title": "t", "result": long}),
        ("POST", "/api/contacts", {"name": "c", "email": "x" * 501}),
        ("PATCH", f"/api/contacts/{contact['id']}", {"notes": long}),
        (
            "POST",
            f"/api/contacts/{contact['id']}/communications",
            {**comm, "subject": "x" * 501},
        ),
        ("POST", "/api/resumes", {"label": "x" * 201}),
        ("PUT", f"{resume}/summary", {"text": long}),
        ("POST", f"{resume}/experience/entries", {"title": "x" * 201, "company": "c"}),
    ]
    for method, url, body in cases:
        resp = carol.request(method, url, json=body)
        assert resp.status_code == 422, f"{method} {url}: {resp.status_code}"


# ---------------------------------------------------------------------------
# M14 — ILIKE wildcards match literally
# ---------------------------------------------------------------------------


def test_percent_and_underscore_in_q_and_tags_match_literally(
    db_conn: Connection[Any],
) -> None:
    db_conn.execute("INSERT INTO users (id) VALUES (%s)", (CAROL,))
    notes = NoteService(db_conn)  # type: ignore[arg-type]
    notes.create_note({"title": "1000 widgets", "tags": ["axb"]}, user_id=CAROL)
    notes.create_note({"title": "100% done", "tags": ["a_b"]}, user_id=CAROL)
    notes.create_note({"title": "abc"}, user_id=CAROL)

    def titles(**kw: Any) -> list[str]:
        return sorted(n["title"] for n in notes.list_notes(user_id=CAROL, **kw))

    assert titles(q="100%") == ["100% done"]
    assert titles(q="a_c") == []
    assert titles(tags=["a_b"]) == ["100% done"]


# ---------------------------------------------------------------------------
# M14 — communication PATCH/DELETE require the cmid to live under cid
# ---------------------------------------------------------------------------


def test_communication_under_wrong_contact_is_404(
    carol: TestClient, db_conn: Connection[Any]
) -> None:
    c1 = carol.post("/api/contacts", json={"name": "one"}).json()["id"]
    c2 = carol.post("/api/contacts", json={"name": "two"}).json()["id"]
    body = {"type": "email", "direction": "sent", "body": "b", "date": "2024-01-01"}
    cm = carol.post(f"/api/contacts/{c1}/communications", json=body).json()["id"]

    wrong = f"/api/contacts/{c2}/communications/{cm}"
    assert carol.patch(wrong, json={"subject": "x"}).status_code == 404
    assert carol.delete(wrong).status_code == 404
    row = db_conn.execute(
        "SELECT subject FROM communication WHERE id = %s", (cm,)
    ).fetchone()
    assert row is not None and row["subject"] == ""

    right = f"/api/contacts/{c1}/communications/{cm}"
    assert carol.patch(right, json={"subject": "ok"}).status_code == 200
    assert carol.delete(right).status_code == 200


def test_mcp_comm_tools_still_work_without_contact_id(
    db_conn: Connection[Any],
) -> None:
    db_conn.execute("INSERT INTO users (id) VALUES (%s)", (CAROL,))
    contact = ContactService(db_conn).create_contact({"name": "x"}, user_id=CAROL)  # type: ignore[arg-type]
    svc = ContactCommunicationService(db_conn)  # type: ignore[arg-type]
    body = {"type": "email", "direction": "sent", "body": "b", "date": "2024-01-01"}
    cm = svc.add_for_contact(contact["id"], body, user_id=CAROL)

    assert svc.update(cm["id"], {"subject": "s"}, user_id=CAROL)["subject"] == "s"
    with pytest.raises(ValueError, match="not found"):
        svc.update(cm["id"], {"subject": "s"}, user_id="user_mallory")


# ---------------------------------------------------------------------------
# H5 — deletes: ownership first, unlink + delete atomic, autocommit-safe
# ---------------------------------------------------------------------------


def test_failed_resume_delete_keeps_its_links(db_conn: Connection[Any]) -> None:
    db_conn.execute("INSERT INTO users (id) VALUES (%s)", (CAROL,))
    resumes = ResumeService(db_conn)  # type: ignore[arg-type]
    only = resumes.create_resume("only", user_id=CAROL)
    note = NoteService(db_conn).create_note({"title": "n"}, user_id=CAROL)  # type: ignore[arg-type]
    links = LinkService(db_conn)  # type: ignore[arg-type]
    links.link("resume", only["id"], "note", note["id"], CAROL)

    with pytest.raises(ValueError, match="last remaining"):
        resumes.delete_resume(only["id"], user_id=CAROL)

    assert links.list_links("resume", only["id"], CAROL) != {}


def test_delete_application_with_links_autocommit(autocommit_conn: Any) -> None:
    uid = "ac_app_del"
    autocommit_conn.execute("INSERT INTO users (id) VALUES (%s)", (uid,))
    apps = ApplicationService(autocommit_conn)
    app = apps.create_application({"company": "c", "position": "p"}, user_id=uid)
    note = NoteService(autocommit_conn).create_note({"title": "n"}, user_id=uid)
    LinkService(autocommit_conn).link("application", app["id"], "note", note["id"], uid)

    apps.delete_application(app["id"], user_id=uid)

    left = autocommit_conn.execute(
        "SELECT COUNT(*) AS n FROM resource_link WHERE user_id = %s", (uid,)
    ).fetchone()
    assert left["n"] == 0


def test_delete_of_foreign_id_touches_nothing(db_conn: Connection[Any]) -> None:
    for uid in (CAROL, "user_mallory"):
        db_conn.execute("INSERT INTO users (id) VALUES (%s)", (uid,))
    app = ApplicationService(db_conn).create_application(  # type: ignore[arg-type]
        {"company": "c", "position": "p"}, user_id=CAROL
    )
    note = NoteService(db_conn).create_note({"title": "n"}, user_id=CAROL)  # type: ignore[arg-type]
    LinkService(db_conn).link("application", app["id"], "note", note["id"], CAROL)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="not found"):
        ApplicationService(db_conn).delete_application(  # type: ignore[arg-type]
            app["id"], user_id="user_mallory"
        )

    assert ApplicationService(db_conn).get_application(  # type: ignore[arg-type]
        app["id"], user_id=CAROL
    )["links"]["note"]


# ---------------------------------------------------------------------------
# M14 — link tools require an authenticated user
# ---------------------------------------------------------------------------


def test_link_tools_require_user_context(db_conn: Connection[Any]) -> None:
    from pktx.tools.link_tools import register_link_tools

    mcp = FastMCP("test")
    svc = LinkService(db_conn)  # type: ignore[arg-type]
    register_link_tools(mcp, lambda: svc)
    token = current_user_id_var.set(None)
    try:
        for name in ("link_resources", "unlink_resources"):
            with pytest.raises(RuntimeError, match="No user context"):
                _get_tool_fn(mcp, name)(a_type="note", a_id=1, b_type="contact", b_id=2)
    finally:
        current_user_id_var.reset(token)
