"""Contract tests for REST API endpoints per openapi.yaml."""

from typing import Any

import pytest
from psycopg import Connection
from starlette.testclient import TestClient

from pktx.api.routes import create_router
from pktx.application_service import ApplicationService
from pktx.resume_service import ResumeService


@pytest.fixture
def service(db_conn: Connection[Any]) -> ResumeService:
    """ResumeService backed by an empty PostgreSQL database."""
    return ResumeService(db_conn)  # type: ignore[arg-type]


@pytest.fixture
def app_service(db_conn: Connection[Any]) -> ApplicationService:
    """ApplicationService backed by an empty PostgreSQL database."""
    return ApplicationService(db_conn)  # type: ignore[arg-type]


def _make_client(svc: ResumeService) -> TestClient:
    """Create a TestClient from a ResumeService using the API router."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(create_router(svc))
    return TestClient(app)


def _make_full_client(svc: ResumeService, app_svc: ApplicationService) -> TestClient:
    """Create a TestClient with both ResumeService and ApplicationService."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(create_router(svc, app_service=app_svc))
    return TestClient(app)


# --- Health ---


class TestHealthEndpoint:
    def test_health_returns_ok(self, service: ResumeService) -> None:
        client = _make_client(service)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestApplicationEndpoints:
    def test_list_applications_empty(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        resp = client.get("/api/applications")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_application(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        resp = client.post(
            "/api/applications",
            json={"company": "Acme", "position": "Engineer"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["company"] == "Acme"
        assert data["position"] == "Engineer"
        assert data["id"] is not None

    def test_create_application_missing_company_returns_422(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        resp = client.post("/api/applications", json={"position": "Dev"})
        assert resp.status_code == 422

    def test_create_application_invalid_status_returns_422(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        resp = client.post(
            "/api/applications",
            json={"company": "Corp", "position": "Dev", "status": "Bogus"},
        )
        assert resp.status_code == 422

    def test_get_application(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        created = client.post(
            "/api/applications",
            json={"company": "Acme", "position": "Dev"},
        ).json()
        resp = client.get(f"/api/applications/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_get_application_not_found(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        resp = client.get("/api/applications/9999")
        assert resp.status_code == 404

    def test_update_application(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        created = client.post(
            "/api/applications",
            json={"company": "Acme", "position": "Dev"},
        ).json()
        resp = client.patch(
            f"/api/applications/{created['id']}",
            json={"status": "Applied"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "Applied"

    def test_update_application_invalid_status_returns_422(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        created = client.post(
            "/api/applications",
            json={"company": "Acme", "position": "Dev"},
        ).json()
        resp = client.patch(
            f"/api/applications/{created['id']}",
            json={"status": "Nope"},
        )
        assert resp.status_code == 422

    def test_delete_application(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        created = client.post(
            "/api/applications",
            json={"company": "Acme", "position": "Dev"},
        ).json()
        resp = client.delete(f"/api/applications/{created['id']}")
        assert resp.status_code == 200
        assert "message" in resp.json()

        get_resp = client.get(f"/api/applications/{created['id']}")
        assert get_resp.status_code == 404

    def test_delete_application_not_found(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        resp = client.delete("/api/applications/9999")
        assert resp.status_code == 404

    def test_list_applications_filter_by_status(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        client.post(
            "/api/applications",
            json={"company": "A", "position": "P1", "status": "Applied"},
        )
        client.post(
            "/api/applications",
            json={"company": "B", "position": "P2", "status": "Interested"},
        )
        resp = client.get("/api/applications?status=Applied")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["company"] == "A"

    def test_list_applications_filter_by_multiple_statuses(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        client.post(
            "/api/applications",
            json={"company": "A", "position": "P1", "status": "Applied"},
        )
        client.post(
            "/api/applications",
            json={"company": "B", "position": "P2", "status": "Interested"},
        )
        client.post(
            "/api/applications",
            json={"company": "C", "position": "P3", "status": "Rejected"},
        )
        resp = client.get("/api/applications?status=Applied&status=Interested")
        assert resp.status_code == 200
        companies = {a["company"] for a in resp.json()}
        assert companies == {"A", "B"}


# --- Application Context Endpoint ---


class TestApplicationContextEndpoint:
    def test_get_context_returns_composite(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        app = client.post(
            "/api/applications",
            json={"company": "Acme", "position": "Dev"},
        ).json()
        resp = client.get(f"/api/applications/{app['id']}/context")
        assert resp.status_code == 200
        data = resp.json()
        assert "application" in data
        assert "linked" in data

    def test_context_application_data_matches(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        app = client.post(
            "/api/applications",
            json={"company": "Acme", "position": "Engineer"},
        ).json()
        resp = client.get(f"/api/applications/{app['id']}/context")
        assert resp.status_code == 200
        data = resp.json()
        assert data["application"]["company"] == "Acme"
        assert data["application"]["position"] == "Engineer"

    def test_context_not_found_returns_404(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        resp = client.get("/api/applications/9999/context")
        assert resp.status_code == 404


# ── Tag Contract Tests ────────────────────────────────────────────────────────


def _make_all_services_client(db_conn: Any) -> TestClient:
    """TestClient with all services enabled."""
    from fastapi import FastAPI

    from pktx.accomplishment_service import AccomplishmentService
    from pktx.note_service import NoteService

    svc = ResumeService(db_conn)  # type: ignore[arg-type]
    app_svc = ApplicationService(db_conn)  # type: ignore[arg-type]
    acc_svc = AccomplishmentService(db_conn)  # type: ignore[arg-type]
    note_svc = NoteService(db_conn)  # type: ignore[arg-type]
    app = FastAPI()
    app.include_router(
        create_router(
            svc,
            app_service=app_svc,
            acc_service=acc_svc,
            note_service=note_svc,
        )
    )
    return TestClient(app)


class TestApplicationTagFilter:
    """Contract tests for application tag endpoints."""

    def test_list_applications_tag_filter(self, db_conn: Any) -> None:
        client = _make_full_client(
            ResumeService(db_conn),  # type: ignore[arg-type]
            ApplicationService(db_conn),  # type: ignore[arg-type]
        )
        client.post(
            "/api/applications",
            json={"company": "A", "position": "P1", "tags": ["python"]},
        )
        client.post(
            "/api/applications",
            json={"company": "B", "position": "P2", "tags": ["java"]},
        )
        resp = client.get("/api/applications?tag=python")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["company"] == "A"

    def test_list_application_tags(self, db_conn: Any) -> None:
        client = _make_full_client(
            ResumeService(db_conn),  # type: ignore[arg-type]
            ApplicationService(db_conn),  # type: ignore[arg-type]
        )
        client.post(
            "/api/applications",
            json={"company": "A", "position": "P1", "tags": ["python"]},
        )
        client.post(
            "/api/applications",
            json={"company": "B", "position": "P2", "tags": ["java"]},
        )
        resp = client.get("/api/applications/tags")
        assert resp.status_code == 200
        assert sorted(resp.json()) == ["java", "python"]


class TestUnifiedTagsEndpoint:
    """Contract tests for GET /api/tags aggregated endpoint."""

    def test_aggregates_all_resource_tags(self, db_conn: Any) -> None:
        client = _make_all_services_client(db_conn)
        client.post(
            "/api/applications",
            json={"company": "A", "position": "P", "tags": ["app-tag"]},
        )
        client.post("/api/accomplishments", json={"title": "Acc", "tags": ["acc-tag"]})
        client.post("/api/notes", json={"title": "Note", "tags": ["note-tag"]})
        resp = client.get("/api/tags")
        assert resp.status_code == 200
        tags = resp.json()
        assert "app-tag" in tags
        assert "acc-tag" in tags
        assert "note-tag" in tags

    def test_deduplicates_tags(self, db_conn: Any) -> None:
        client = _make_all_services_client(db_conn)
        client.post(
            "/api/applications",
            json={"company": "A", "position": "P", "tags": ["shared"]},
        )
        client.post("/api/notes", json={"title": "N", "tags": ["shared"]})
        resp = client.get("/api/tags")
        assert resp.status_code == 200
        assert resp.json().count("shared") == 1

    def test_returns_sorted(self, db_conn: Any) -> None:
        client = _make_all_services_client(db_conn)
        client.post(
            "/api/applications",
            json={"company": "A", "position": "P", "tags": ["zebra", "apple"]},
        )
        resp = client.get("/api/tags")
        assert resp.status_code == 200
        tags = resp.json()
        assert tags == sorted(tags)
