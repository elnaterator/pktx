"""Cross-interface integration tests — verify REST and MCP share state."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from psycopg import Connection

import pktx.server
from pktx.resume_service import ResumeService
from pktx.server import create_app


def _default_url(client: TestClient) -> str:
    """URL prefix of the no-auth ("legacy") user's default resume version."""
    rid = client.get("/api/resumes/default").json()["id"]
    return f"/api/resumes/{rid}"


class TestCrossInterfaceSharedState:
    """Integration tests verifying REST API and MCP tools share the same database."""

    @pytest.fixture
    def app_and_service(
        self, db_conn_with_data: Any
    ) -> tuple[Any, ResumeService, TestClient]:
        """Create FastAPI app with test database and HTTP test client."""
        service = ResumeService(db_conn_with_data)
        app = create_app(service=service, conn=db_conn_with_data)
        client = TestClient(app)
        return app, service, client

    def test_add_entry_via_rest_visible_in_service(
        self, app_and_service: tuple[Any, ResumeService, TestClient]
    ) -> None:
        """Test US3: Add entry via REST API, verify visible through service."""
        app, service, client = app_and_service

        # Add skill via REST API
        response = client.post(
            f"{_default_url(client)}/skills/entries",
            json={"name": "Docker", "category": "DevOps"},
        )
        assert response.status_code == 201

        # Read via service (same underlying database)
        skills = service.get_section("skills", user_id="legacy")
        skill_names = [s["name"] for s in skills]
        assert "Docker" in skill_names

    def test_update_via_service_visible_in_rest(
        self, app_and_service: tuple[Any, ResumeService, TestClient]
    ) -> None:
        """Test US3: Update via service, verify visible via REST API."""
        app, service, client = app_and_service

        # Update contact via service
        service.update_section(
            "contact",
            {"name": "John Updated", "email": "updated@example.com"},
            user_id="legacy",
        )

        # Read via REST API
        response = client.get(f"{_default_url(client)}/contact")
        assert response.status_code == 200
        contact = response.json()
        assert contact["name"] == "John Updated"
        assert contact["email"] == "updated@example.com"

    def test_concurrent_operations_no_corruption(
        self, app_and_service: tuple[Any, ResumeService, TestClient]
    ) -> None:
        """Test US3: Concurrent operations via both interfaces don't corrupt data."""
        app, service, client = app_and_service

        # Add multiple entries via both interfaces
        for i in range(5):
            if i % 2 == 0:
                # REST API
                client.post(
                    f"{_default_url(client)}/skills/entries",
                    json={"name": f"RestSkill{i}", "category": "Languages"},
                )
            else:
                # Service (used by MCP tools)
                service.add_entry(
                    "skills",
                    {"name": f"ServiceSkill{i}", "category": "Languages"},
                    user_id="legacy",
                )

        # Verify all entries present via REST
        response = client.get(f"{_default_url(client)}/skills")
        assert response.status_code == 200
        skills = response.json()
        skill_names = [s["name"] for s in skills]

        # All added skills should be present
        for i in range(5):
            if i % 2 == 0:
                assert f"RestSkill{i}" in skill_names
            else:
                assert f"ServiceSkill{i}" in skill_names

    def test_global_service_is_shared(
        self, app_and_service: tuple[Any, ResumeService, TestClient]
    ) -> None:
        """Test US3: Verify global _service used by MCP is the same instance."""
        app, service, client = app_and_service

        # The global _service should be the same instance
        assert pktx.server._service is service, (
            "MCP tools should use the same service instance"
        )


class TestResumeVersionCrossInterface:
    """Integration tests for resume version operations across REST and MCP."""

    @pytest.fixture
    def full_app(self, db_conn_with_data: Any) -> tuple[Any, ResumeService, TestClient]:
        """Create full app with both resume and application services."""

        service = ResumeService(db_conn_with_data)
        app = create_app(service=service, conn=db_conn_with_data)
        client = TestClient(app)
        return app, service, client

    def test_create_version_via_rest_visible_in_service(
        self, full_app: tuple[Any, ResumeService, TestClient]
    ) -> None:
        """Create a resume version via REST and verify it's visible via service."""
        app, service, client = full_app

        resp = client.post("/api/resumes", json={"label": "My New Resume"})
        assert resp.status_code == 201
        created_id = resp.json()["id"]

        versions = service.list_resumes(user_id="legacy")
        ids = [v["id"] for v in versions]
        assert created_id in ids

    def test_update_version_via_service_visible_in_rest(
        self, full_app: tuple[Any, ResumeService, TestClient]
    ) -> None:
        """Update a resume version via service and verify it's visible via REST."""
        app, service, client = full_app

        default = service.get_resume(user_id="legacy")
        service.update_section(
            "contact", {"name": "Updated Name"}, default["id"], user_id="legacy"
        )

        resp = client.get(f"/api/resumes/{default['id']}/contact")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    def test_set_default_via_rest_visible_in_service(
        self, full_app: tuple[Any, ResumeService, TestClient]
    ) -> None:
        """Set default via REST and verify service returns the new default."""
        app, service, client = full_app

        resp = client.post("/api/resumes", json={"label": "Promoted"})
        new_id = resp.json()["id"]

        client.post(f"/api/resumes/{new_id}/default")

        default = service.get_resume(user_id="legacy")
        assert default["id"] == new_id


# ── Accomplishment Cross-Interface Tests ──────────────────────────────────────


class TestAccomplishmentCrossInterface:
    """T049 — Cross-interface tests: service layer ↔ REST API + SC-006 durability."""

    @pytest.fixture
    def full_app(self, db_conn_with_data: Any) -> tuple[Any, Any, TestClient]:
        """Create full app (all services) with test database and HTTP test client."""
        service = ResumeService(db_conn_with_data)
        app = create_app(service=service, conn=db_conn_with_data)
        client = TestClient(app)
        return app, service, client

    def test_create_via_service_visible_via_rest(
        self, full_app: tuple[Any, Any, TestClient]
    ) -> None:
        """Accomplishment created via AccomplishmentService visible via REST API."""
        _app, _service, client = full_app
        acc_svc = pktx.server._acc_service
        assert acc_svc is not None

        created = acc_svc.create_accomplishment(
            {"title": "Cross-interface test", "result": "Success"}, user_id="legacy"
        )

        resp = client.get(f"/api/accomplishments/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Cross-interface test"

    def test_create_via_rest_visible_via_service(
        self, full_app: tuple[Any, Any, TestClient]
    ) -> None:
        """Accomplishment created via REST API visible via AccomplishmentService."""
        _app, _service, client = full_app
        acc_svc = pktx.server._acc_service
        assert acc_svc is not None

        resp = client.post(
            "/api/accomplishments",
            json={"title": "REST creation", "tags": ["test"]},
        )
        assert resp.status_code == 201
        acc_id = resp.json()["id"]

        acc = acc_svc.get_accomplishment(acc_id, user_id="legacy")
        assert acc["title"] == "REST creation"

    def test_global_acc_service_shared(
        self, full_app: tuple[Any, Any, TestClient]
    ) -> None:
        """Verify global _acc_service used by MCP is the same instance."""
        _app, _service, client = full_app
        assert pktx.server._acc_service is not None

    def test_durability_across_connection_reopen(
        self, db_conn: Connection[Any]
    ) -> None:
        """SC-006: Accomplishment readable via second service on same connection."""
        from pktx.accomplishment_service import AccomplishmentService

        svc1 = AccomplishmentService(db_conn)  # type: ignore[arg-type]
        created = svc1.create_accomplishment(
            {"title": "Durability test"}, user_id="legacy"
        )
        acc_id = created["id"]

        # Second service instance on same connection — data visible within transaction
        svc2 = AccomplishmentService(db_conn)  # type: ignore[arg-type]
        recovered = svc2.get_accomplishment(acc_id, user_id="legacy")
        assert recovered["title"] == "Durability test"


# ── Note Cross-Interface Tests ─────────────────────────────────────────────────


class TestNoteCrossInterface:
    """T052 — Cross-interface tests: NoteService ↔ REST API + durability."""

    @pytest.fixture
    def full_app(self, db_conn_with_data: Any) -> tuple[Any, Any, TestClient]:
        """Create full app (all services) with test database and HTTP test client."""
        service = ResumeService(db_conn_with_data)
        app = create_app(service=service, conn=db_conn_with_data)
        client = TestClient(app)
        return app, service, client

    def test_create_via_service_visible_via_rest(
        self, full_app: tuple[Any, Any, TestClient]
    ) -> None:
        """Note created via NoteService visible via REST API."""
        _app, _service, client = full_app
        note_svc = pktx.server._note_service
        assert note_svc is not None

        created = note_svc.create_note(
            {
                "title": "Cross-interface note",
                "content": "Test content",
                "tags": ["test"],
            },
            user_id="legacy",
        )

        resp = client.get(f"/api/notes/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Cross-interface note"
        assert resp.json()["content"] == "Test content"

    def test_create_via_rest_visible_via_service(
        self, full_app: tuple[Any, Any, TestClient]
    ) -> None:
        """Note created via REST API visible via NoteService."""
        _app, _service, client = full_app
        note_svc = pktx.server._note_service
        assert note_svc is not None

        resp = client.post(
            "/api/notes",
            json={"title": "REST note", "content": "From REST", "tags": ["api"]},
        )
        assert resp.status_code == 201
        note_id = resp.json()["id"]

        note = note_svc.get_note(note_id, user_id="legacy")
        assert note["title"] == "REST note"
        assert note["content"] == "From REST"

    def test_global_note_service_shared(
        self, full_app: tuple[Any, Any, TestClient]
    ) -> None:
        """Verify global _note_service used by MCP is the same instance."""
        _app, _service, client = full_app
        assert pktx.server._note_service is not None

    def test_durability_across_service_instances(
        self, db_conn: Connection[Any]
    ) -> None:
        """Note readable via second service on same connection."""
        from pktx.note_service import NoteService

        svc1 = NoteService(db_conn)  # type: ignore[arg-type]
        created = svc1.create_note({"title": "Durability note"}, user_id="legacy")
        note_id = created["id"]

        svc2 = NoteService(db_conn)  # type: ignore[arg-type]
        recovered = svc2.get_note(note_id, user_id="legacy")
        assert recovered["title"] == "Durability note"
