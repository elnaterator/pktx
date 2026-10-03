"""Unit tests for pktx.application_service module."""

from typing import Any

import pytest
from psycopg import Connection


@pytest.fixture
def app_service(db_conn: Connection[Any]):  # type: ignore[no-untyped-def]
    """ApplicationService backed by an empty PostgreSQL database."""
    from pktx.application_service import ApplicationService

    return ApplicationService(db_conn)  # type: ignore[arg-type]


class TestApplicationServiceCreate:
    """Tests for ApplicationService.create_application."""

    def test_requires_company(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="Company is required"):
            svc.create_application({"position": "Dev"}, user_id="legacy")

    def test_requires_position(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="Position is required"):
            svc.create_application({"company": "Corp"}, user_id="legacy")

    def test_rejects_invalid_status(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="Invalid status"):
            svc.create_application(
                {"company": "Corp", "position": "Dev", "status": "Bogus"},
                user_id="legacy",
            )

    def test_accepts_valid_statuses(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService
        from pktx.models import APPLICATION_STATUSES

        svc: ApplicationService = app_service  # type: ignore[assignment]
        for status in APPLICATION_STATUSES:
            result = svc.create_application(
                {"company": f"Corp_{status}", "position": "Dev", "status": status},
                user_id="legacy",
            )
            assert result["status"] == status

    def test_creates_with_defaults(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        result = svc.create_application(
            {"company": "Corp", "position": "Dev"}, user_id="legacy"
        )

        assert result["id"] is not None
        assert result["status"] == "Interested"
        assert result["company"] == "Corp"
        assert result["position"] == "Dev"


class TestApplicationServiceGet:
    """Tests for ApplicationService.get_application."""

    def test_gets_existing_application(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        created = svc.create_application(
            {"company": "Corp", "position": "Dev"}, user_id="legacy"
        )
        result = svc.get_application(created["id"], user_id="legacy")

        assert result["id"] == created["id"]
        assert result["company"] == "Corp"

    def test_raises_for_nonexistent(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="not found"):
            svc.get_application(9999, user_id="legacy")


class TestApplicationServiceList:
    """Tests for ApplicationService.list_applications."""

    def test_lists_all(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        svc.create_application({"company": "A", "position": "P1"}, user_id="legacy")
        svc.create_application({"company": "B", "position": "P2"}, user_id="legacy")
        results = svc.list_applications(user_id="legacy")

        assert len(results) == 2

    def test_filter_by_status(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        svc.create_application(
            {"company": "A", "position": "P1", "status": "Applied"}, user_id="legacy"
        )
        svc.create_application(
            {"company": "B", "position": "P2", "status": "Interested"}, user_id="legacy"
        )
        results = svc.list_applications(status="Applied", user_id="legacy")

        assert len(results) == 1
        assert results[0]["company"] == "A"

    def test_filter_by_multiple_statuses(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        svc.create_application(
            {"company": "A", "position": "P1", "status": "Applied"}, user_id="legacy"
        )
        svc.create_application(
            {"company": "B", "position": "P2", "status": "Interested"}, user_id="legacy"
        )
        svc.create_application(
            {"company": "C", "position": "P3", "status": "Rejected"}, user_id="legacy"
        )
        results = svc.list_applications(
            status=["Applied", "Interested"], user_id="legacy"
        )

        companies = {r["company"] for r in results}
        assert companies == {"A", "B"}

    def test_search_by_query(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        svc.create_application(
            {"company": "Acme Corp", "position": "Dev"}, user_id="legacy"
        )
        svc.create_application(
            {"company": "Other Inc", "position": "QA"}, user_id="legacy"
        )
        results = svc.list_applications(q="acme", user_id="legacy")

        assert len(results) == 1
        assert results[0]["company"] == "Acme Corp"

    def test_returns_empty_when_no_applications(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        results = svc.list_applications(user_id="legacy")

        assert results == []


class TestApplicationServiceUpdate:
    """Tests for ApplicationService.update_application."""

    def test_updates_fields(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        created = svc.create_application(
            {"company": "Corp", "position": "Dev"}, user_id="legacy"
        )
        updated = svc.update_application(
            created["id"], {"status": "Applied"}, user_id="legacy"
        )

        assert updated["status"] == "Applied"
        assert updated["company"] == "Corp"

    def test_rejects_invalid_status_on_update(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        created = svc.create_application(
            {"company": "Corp", "position": "Dev"}, user_id="legacy"
        )
        with pytest.raises(ValueError, match="Invalid status"):
            svc.update_application(created["id"], {"status": "Fake"}, user_id="legacy")

    def test_raises_for_nonexistent_app(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="not found"):
            svc.update_application(9999, {"status": "Applied"}, user_id="legacy")


class TestApplicationServiceDelete:
    """Tests for ApplicationService.delete_application."""

    def test_deletes_existing(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        created = svc.create_application(
            {"company": "Corp", "position": "Dev"}, user_id="legacy"
        )
        svc.delete_application(created["id"], user_id="legacy")

        with pytest.raises(ValueError, match="not found"):
            svc.get_application(created["id"], user_id="legacy")

    def test_returns_deleted_app_data(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        created = svc.create_application(
            {"company": "Corp", "position": "Dev"}, user_id="legacy"
        )
        result = svc.delete_application(created["id"], user_id="legacy")

        assert result["company"] == "Corp"
        assert result["position"] == "Dev"

    def test_raises_for_nonexistent(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="not found"):
            svc.delete_application(9999, user_id="legacy")


class TestApplicationServiceContext:
    """Tests for ApplicationService.get_application_context."""

    def test_returns_composite_data(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        created = svc.create_application(
            {"company": "Corp", "position": "Dev"}, user_id="legacy"
        )
        context = svc.get_application_context(created["id"], user_id="legacy")

        assert "application" in context
        assert "linked" in context

    def test_application_data_matches(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        created = svc.create_application(
            {"company": "Corp", "position": "Dev"}, user_id="legacy"
        )
        context = svc.get_application_context(created["id"], user_id="legacy")

        assert context["application"]["id"] == created["id"]
        assert context["application"]["company"] == "Corp"

    def test_raises_for_nonexistent_app(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="not found"):
            svc.get_application_context(9999, user_id="legacy")


class TestApplicationServiceTags:
    """Unit tests for tag normalization and filtering in ApplicationService."""

    def test_tags_normalized_on_create(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        result = svc.create_application(
            {"company": "A", "position": "P", "tags": ["  Python  ", "PYTHON", "go"]},
            user_id="legacy",
        )
        assert result["tags"] == ["python", "go"]

    def test_tags_50_char_limit_on_create(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        long_tag = "x" * 51
        with pytest.raises(ValueError, match="50 characters"):
            svc.create_application(
                {"company": "A", "position": "P", "tags": [long_tag]}, user_id="legacy"
            )

    def test_tags_normalized_on_update(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        created = svc.create_application(
            {"company": "A", "position": "P"}, user_id="legacy"
        )
        updated = svc.update_application(
            created["id"], {"tags": ["  Java  ", "JAVA", "rust"]}, user_id="legacy"
        )
        assert updated["tags"] == ["java", "rust"]

    def test_filter_by_tag(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        svc.create_application(
            {"company": "A", "position": "P1", "tags": ["python"]}, user_id="legacy"
        )
        svc.create_application(
            {"company": "B", "position": "P2", "tags": ["java"]}, user_id="legacy"
        )
        results = svc.list_applications(tags=["python"], user_id="legacy")
        assert len(results) == 1
        assert results[0]["company"] == "A"

    def test_list_tags(self, app_service: object) -> None:
        from pktx.application_service import ApplicationService

        svc: ApplicationService = app_service  # type: ignore[assignment]
        svc.create_application(
            {"company": "A", "position": "P1", "tags": ["python"]}, user_id="legacy"
        )
        svc.create_application(
            {"company": "B", "position": "P2", "tags": ["java"]}, user_id="legacy"
        )
        tags = svc.list_tags(user_id="legacy")
        assert sorted(tags) == ["java", "python"]
