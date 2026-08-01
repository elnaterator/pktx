"""Contract tests for GET /api/export — completeness and per-user isolation."""

from collections.abc import Generator
from typing import Any

import pytest
from psycopg import Connection
from starlette.testclient import TestClient

from pktx.auth import current_user_id_var

_USER = "export_user"
_OTHER = "export_other"


@pytest.fixture(autouse=True)
def _set_user_context() -> Generator[None, None, None]:
    token = current_user_id_var.set(_USER)
    try:
        yield
    finally:
        current_user_id_var.reset(token)


def _make_client(db_conn: Connection[Any], as_user: str) -> TestClient:
    """TestClient whose auth dependency always resolves to ``as_user``.

    Export is entirely about ownership, so these tests need a real user on the
    request — the no-auth path (``user_id=None``) means "no filter" and would
    make the isolation assertions meaningless.
    """
    from fastapi import FastAPI

    from pktx.accomplishment_service import AccomplishmentService
    from pktx.api.routes import create_router
    from pktx.application_service import ApplicationService
    from pktx.auth import UserContext
    from pktx.communication_service import ContactCommunicationService
    from pktx.contact_service import ContactService
    from pktx.link_service import LinkService
    from pktx.note_service import NoteService
    from pktx.resume_service import ResumeService

    def _fake_user() -> UserContext:
        return UserContext(id=as_user, email=f"{as_user}@test.com", display_name=None)

    conn: Any = db_conn
    app = FastAPI()
    app.include_router(
        create_router(
            ResumeService(conn),
            app_service=ApplicationService(conn),
            acc_service=AccomplishmentService(conn),
            note_service=NoteService(conn),
            contact_service=ContactService(conn),
            comm_service=ContactCommunicationService(conn),
            link_service=LinkService(conn),
            get_current_user=_fake_user,
        )
    )
    return TestClient(app)


@pytest.fixture
def seeded_users(db_conn: Connection[Any]) -> dict[str, Any]:
    """Give both users one of every resource type."""
    from pktx.accomplishment_service import AccomplishmentService
    from pktx.application_service import ApplicationService
    from pktx.communication_service import ContactCommunicationService
    from pktx.contact_service import ContactService
    from pktx.link_service import LinkService
    from pktx.note_service import NoteService
    from pktx.resume_service import ResumeService

    conn: Any = db_conn
    for uid in (_USER, _OTHER):
        conn.execute(
            "INSERT INTO users (id, email) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
            (uid, f"{uid}@test.com"),
        )

    created: dict[str, Any] = {}
    for uid, marker in ((_USER, "mine"), (_OTHER, "theirs")):
        resume = ResumeService(conn).create_resume(f"{marker} resume", user_id=uid)
        app_row = ApplicationService(conn).create_application(
            {"company": f"{marker} co", "position": "Engineer"}, user_id=uid
        )
        AccomplishmentService(conn).create_accomplishment(
            {"title": f"{marker} accomplishment"}, user_id=uid
        )
        NoteService(conn).create_note(
            {"title": f"{marker} note", "content": f"{marker} content"}, user_id=uid
        )
        contact = ContactService(conn).create_contact(
            {"name": f"{marker} contact"}, user_id=uid
        )
        ContactCommunicationService(conn).add_for_contact(
            contact["id"],
            {
                "type": "email",
                "direction": "sent",
                "subject": f"{marker} subject",
                "body": f"{marker} body",
                "date": "2026-07-30",
            },
            user_id=uid,
        )
        LinkService(conn).link(
            "application", app_row["id"], "resume", resume["id"], uid
        )
        created[uid] = {"resume": resume, "application": app_row, "contact": contact}
    return created


class TestExportContents:
    def test_export_includes_every_resource_type(
        self, db_conn: Connection[Any], seeded_users: dict[str, Any]
    ) -> None:
        client = _make_client(db_conn, _USER)

        data = client.get("/api/export").json()

        assert data["schema_version"] > 0
        assert data["exported_at"]
        for key in (
            "resumes",
            "applications",
            "accomplishments",
            "notes",
            "contacts",
            "communications",
            "links",
        ):
            assert data[key], f"{key} should not be empty"

    def test_export_carries_full_bodies_not_summaries(
        self, db_conn: Connection[Any], seeded_users: dict[str, Any]
    ) -> None:
        client = _make_client(db_conn, _USER)

        data = client.get("/api/export").json()

        assert "resume_data" in data["resumes"][0]
        assert data["notes"][0]["content"] == "mine content"
        assert data["communications"][0]["body"] == "mine body"
        assert (
            data["communications"][0]["contact_id"]
            == (seeded_users[_USER]["contact"]["id"])
        )

    def test_export_is_an_attachment_download(
        self, db_conn: Connection[Any], seeded_users: dict[str, Any]
    ) -> None:
        client = _make_client(db_conn, _USER)

        response = client.get("/api/export")

        disposition = response.headers["content-disposition"]
        assert disposition.startswith('attachment; filename="pktx-export-')
        assert disposition.endswith('.json"')


class TestExportIsolation:
    def test_export_never_contains_another_users_data(
        self, db_conn: Connection[Any], seeded_users: dict[str, Any]
    ) -> None:
        client = _make_client(db_conn, _USER)

        body = client.get("/api/export").text

        assert "mine" in body
        assert "theirs" not in body

    def test_other_user_export_contains_only_their_own(
        self, db_conn: Connection[Any], seeded_users: dict[str, Any]
    ) -> None:
        client = _make_client(db_conn, _OTHER)

        body = client.get("/api/export").text

        assert "theirs" in body
        assert "mine" not in body
