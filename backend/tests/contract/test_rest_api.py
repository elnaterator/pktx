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
def service_with_data(db_conn_with_data: Connection[Any]) -> ResumeService:
    """ResumeService backed by a pre-populated database."""
    return ResumeService(db_conn_with_data)  # type: ignore[arg-type]


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


def _default_url(client: TestClient) -> str:
    """URL prefix of the caller's default resume version."""
    rid = client.get("/api/resumes/default").json()["id"]
    return f"/api/resumes/{rid}"


# --- T012: GET /health, GET /api/resumes/default, GET .../{section} ---


class TestHealthEndpoint:
    def test_health_returns_ok(self, service: ResumeService) -> None:
        client = _make_client(service)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestGetResume:
    def test_get_empty_resume(self, service: ResumeService) -> None:
        client = _make_client(service)
        resp = client.get("/api/resumes/default")
        assert resp.status_code == 200
        data = resp.json()["resume_data"]
        assert "contact" in data
        assert "summary" in data
        assert "experience" in data
        assert "education" in data
        assert "skills" in data

    def test_get_populated_resume(self, service_with_data: ResumeService) -> None:
        client = _make_client(service_with_data)
        resp = client.get("/api/resumes/default")
        assert resp.status_code == 200
        data = resp.json()["resume_data"]
        assert data["contact"]["name"] == "Jane Doe"
        assert data["summary"] != ""
        assert len(data["experience"]) == 2
        assert len(data["education"]) == 2
        assert len(data["skills"]) == 8


class TestGetSection:
    def test_get_contact_section(self, service_with_data: ResumeService) -> None:
        client = _make_client(service_with_data)
        base = _default_url(client)
        resp = client.get(f"{base}/contact")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Jane Doe"

    def test_get_summary_section(self, service_with_data: ResumeService) -> None:
        client = _make_client(service_with_data)
        base = _default_url(client)
        resp = client.get(f"{base}/summary")
        assert resp.status_code == 200
        assert "software engineer" in resp.json().lower()

    def test_get_experience_section(self, service_with_data: ResumeService) -> None:
        client = _make_client(service_with_data)
        base = _default_url(client)
        resp = client.get(f"{base}/experience")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_education_section(self, service_with_data: ResumeService) -> None:
        client = _make_client(service_with_data)
        base = _default_url(client)
        resp = client.get(f"{base}/education")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_skills_section(self, service_with_data: ResumeService) -> None:
        client = _make_client(service_with_data)
        base = _default_url(client)
        resp = client.get(f"{base}/skills")
        assert resp.status_code == 200
        assert len(resp.json()) == 8


# --- T013: PUT .../contact, PUT .../summary ---


class TestUpdateContact:
    def test_update_contact_partial(self, service: ResumeService) -> None:
        client = _make_client(service)
        base = _default_url(client)
        resp = client.put(
            f"{base}/contact",
            json={"name": "John Doe", "email": "john@example.com"},
        )
        assert resp.status_code == 200
        assert "message" in resp.json()

        # Verify the data was saved
        get_resp = client.get(f"{base}/contact")
        assert get_resp.json()["name"] == "John Doe"
        assert get_resp.json()["email"] == "john@example.com"

    def test_update_contact_merge(self, service_with_data: ResumeService) -> None:
        client = _make_client(service_with_data)
        base = _default_url(client)
        # Update only email, other fields should be preserved
        resp = client.put(
            f"{base}/contact",
            json={"email": "newemail@example.com"},
        )
        assert resp.status_code == 200

        get_resp = client.get(f"{base}/contact")
        assert get_resp.json()["email"] == "newemail@example.com"
        assert get_resp.json()["name"] == "Jane Doe"  # preserved


class TestUpdateSummary:
    def test_update_summary(self, service: ResumeService) -> None:
        client = _make_client(service)
        base = _default_url(client)
        resp = client.put(
            f"{base}/summary",
            json={"text": "A new summary text."},
        )
        assert resp.status_code == 200
        assert "message" in resp.json()

        get_resp = client.get(f"{base}/summary")
        assert get_resp.json() == "A new summary text."

    def test_update_summary_empty_text_returns_422(
        self, service: ResumeService
    ) -> None:
        client = _make_client(service)
        base = _default_url(client)
        resp = client.put(f"{base}/summary", json={"text": ""})
        assert resp.status_code == 422
        assert "detail" in resp.json()


# --- T014: POST entries, PUT entries/{index}, DELETE entries/{index} ---


class TestAddEntry:
    def test_add_experience_entry(self, service: ResumeService) -> None:
        client = _make_client(service)
        base = _default_url(client)
        resp = client.post(
            f"{base}/experience/entries",
            json={"title": "Engineer", "company": "TestCo"},
        )
        assert resp.status_code == 201
        assert "message" in resp.json()

        # Verify it was added
        get_resp = client.get(f"{base}/experience")
        assert len(get_resp.json()) == 1
        assert get_resp.json()[0]["title"] == "Engineer"

    def test_add_education_entry(self, service: ResumeService) -> None:
        client = _make_client(service)
        base = _default_url(client)
        resp = client.post(
            f"{base}/education/entries",
            json={"institution": "MIT", "degree": "B.S."},
        )
        assert resp.status_code == 201
        assert "message" in resp.json()

    def test_add_skill_entry(self, service: ResumeService) -> None:
        client = _make_client(service)
        base = _default_url(client)
        resp = client.post(
            f"{base}/skills/entries",
            json={"name": "Python", "category": "Languages"},
        )
        assert resp.status_code == 201
        assert "message" in resp.json()


class TestUpdateEntry:
    def test_update_experience_entry(self, service_with_data: ResumeService) -> None:
        client = _make_client(service_with_data)
        base = _default_url(client)
        resp = client.put(
            f"{base}/experience/entries/0",
            json={"title": "Staff Engineer"},
        )
        assert resp.status_code == 200
        assert "message" in resp.json()

        get_resp = client.get(f"{base}/experience")
        assert get_resp.json()[0]["title"] == "Staff Engineer"

    def test_update_skill_entry(self, service_with_data: ResumeService) -> None:
        client = _make_client(service_with_data)
        base = _default_url(client)
        resp = client.put(
            f"{base}/skills/entries/0",
            json={"category": "Core Languages"},
        )
        assert resp.status_code == 200


class TestDeleteEntry:
    def test_delete_experience_entry(self, service_with_data: ResumeService) -> None:
        client = _make_client(service_with_data)
        base = _default_url(client)
        resp = client.delete(f"{base}/experience/entries/0")
        assert resp.status_code == 200
        assert "message" in resp.json()

        get_resp = client.get(f"{base}/experience")
        assert len(get_resp.json()) == 1

    def test_delete_skill_entry(self, service_with_data: ResumeService) -> None:
        client = _make_client(service_with_data)
        base = _default_url(client)
        resp = client.delete(f"{base}/skills/entries/0")
        assert resp.status_code == 200

        get_resp = client.get(f"{base}/skills")
        assert len(get_resp.json()) == 7


# --- T015: Error cases ---


class TestErrorCases:
    def test_invalid_section_returns_404(self, service: ResumeService) -> None:
        client = _make_client(service)
        base = _default_url(client)
        resp = client.get(f"{base}/invalid_section")
        assert resp.status_code == 404
        assert "detail" in resp.json()

    def test_add_entry_invalid_section_returns_400(
        self, service: ResumeService
    ) -> None:
        client = _make_client(service)
        base = _default_url(client)
        resp = client.post(
            f"{base}/contact/entries",
            json={"name": "test"},
        )
        assert resp.status_code == 400
        assert "detail" in resp.json()

    def test_update_entry_out_of_range_returns_404(
        self, service: ResumeService
    ) -> None:
        client = _make_client(service)
        base = _default_url(client)
        resp = client.put(
            f"{base}/experience/entries/99",
            json={"title": "Ghost"},
        )
        assert resp.status_code == 404
        assert "detail" in resp.json()

    def test_delete_entry_out_of_range_returns_404(
        self, service: ResumeService
    ) -> None:
        client = _make_client(service)
        base = _default_url(client)
        resp = client.delete(f"{base}/experience/entries/99")
        assert resp.status_code == 404
        assert "detail" in resp.json()

    def test_add_experience_missing_required_fields_returns_422(
        self, service: ResumeService
    ) -> None:
        client = _make_client(service)
        base = _default_url(client)
        resp = client.post(
            f"{base}/experience/entries",
            json={"title": "Engineer"},  # missing 'company'
        )
        assert resp.status_code == 422
        assert "detail" in resp.json()

    def test_malformed_json_returns_422(self, service: ResumeService) -> None:
        client = _make_client(service)
        base = _default_url(client)
        resp = client.put(
            f"{base}/contact",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422


# --- Resume Version Endpoints ---


class TestResumeVersionEndpoints:
    def test_list_resumes(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        resp = client.get("/api/resumes")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1

    def test_create_resume(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        resp = client.post("/api/resumes", json={"label": "My Custom Resume"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["label"] == "My Custom Resume"
        assert data["is_default"] is False

    def test_create_resume_missing_label_returns_422(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        resp = client.post("/api/resumes", json={"label": ""})
        assert resp.status_code == 422

    def test_get_default_resume(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        resp = client.get("/api/resumes/default")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_default"] is True
        assert "resume_data" in data

    def test_get_resume_by_id(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        versions = client.get("/api/resumes").json()
        version_id = versions[0]["id"]
        resp = client.get(f"/api/resumes/{version_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == version_id

    def test_get_resume_by_id_not_found(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        resp = client.get("/api/resumes/9999")
        assert resp.status_code == 404

    def test_update_resume_metadata(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        versions = client.get("/api/resumes").json()
        version_id = versions[0]["id"]
        resp = client.patch(f"/api/resumes/{version_id}", json={"label": "Renamed"})
        assert resp.status_code == 200
        assert resp.json()["label"] == "Renamed"

    def test_delete_resume_version(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        created = client.post("/api/resumes", json={"label": "Temp"}).json()
        resp = client.delete(f"/api/resumes/{created['id']}")
        assert resp.status_code == 200
        assert "message" in resp.json()

    def test_delete_last_version_returns_409(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        versions = client.get("/api/resumes").json()
        assert len(versions) == 1
        resp = client.delete(f"/api/resumes/{versions[0]['id']}")
        assert resp.status_code == 409

    def test_set_resume_default(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        created = client.post("/api/resumes", json={"label": "New Default"}).json()
        resp = client.post(f"/api/resumes/{created['id']}/default")
        assert resp.status_code == 200
        assert "message" in resp.json()

        default = client.get("/api/resumes/default").json()
        assert default["id"] == created["id"]

    def test_get_resume_section(
        self,
        service_with_data: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service_with_data, app_service)
        versions = client.get("/api/resumes").json()
        version_id = versions[0]["id"]
        resp = client.get(f"/api/resumes/{version_id}/contact")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Jane Doe"

    def test_get_resume_invalid_section_returns_404(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        versions = client.get("/api/resumes").json()
        version_id = versions[0]["id"]
        resp = client.get(f"/api/resumes/{version_id}/invalid_section")
        assert resp.status_code == 404

    def test_update_resume_contact(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        versions = client.get("/api/resumes").json()
        version_id = versions[0]["id"]
        resp = client.put(
            f"/api/resumes/{version_id}/contact",
            json={"name": "Alice"},
        )
        assert resp.status_code == 200
        assert "message" in resp.json()

    def test_update_resume_summary(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        versions = client.get("/api/resumes").json()
        version_id = versions[0]["id"]
        resp = client.put(
            f"/api/resumes/{version_id}/summary",
            json={"text": "New summary"},
        )
        assert resp.status_code == 200

    def test_add_resume_entry(
        self,
        service: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service, app_service)
        versions = client.get("/api/resumes").json()
        version_id = versions[0]["id"]
        resp = client.post(
            f"/api/resumes/{version_id}/experience/entries",
            json={"title": "Dev", "company": "Corp"},
        )
        assert resp.status_code == 201
        assert "message" in resp.json()

    def test_update_resume_entry(
        self,
        service_with_data: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service_with_data, app_service)
        versions = client.get("/api/resumes").json()
        version_id = versions[0]["id"]
        resp = client.put(
            f"/api/resumes/{version_id}/experience/entries/0",
            json={"title": "Staff Engineer"},
        )
        assert resp.status_code == 200

    def test_delete_resume_entry(
        self,
        service_with_data: ResumeService,
        app_service: ApplicationService,
    ) -> None:
        client = _make_full_client(service_with_data, app_service)
        versions = client.get("/api/resumes").json()
        version_id = versions[0]["id"]
        resp = client.delete(f"/api/resumes/{version_id}/experience/entries/0")
        assert resp.status_code == 200


# --- Application Endpoints ---


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
