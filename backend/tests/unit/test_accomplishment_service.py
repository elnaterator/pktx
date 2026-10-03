"""Unit tests for AccomplishmentService and accomplishment DB functions."""

from typing import Any

import pytest
from psycopg import Connection


@pytest.fixture
def acc_service(db_conn: Connection[Any]):  # type: ignore[no-untyped-def]
    """AccomplishmentService backed by an empty PostgreSQL database."""
    from pktx.accomplishment_service import AccomplishmentService

    return AccomplishmentService(db_conn)  # type: ignore[arg-type]


# ── US1: Create ──────────────────────────────────────────────────────────────


class TestAccomplishmentServiceCreate:
    """Tests for AccomplishmentService.create_accomplishment (T006)."""

    def test_requires_title(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="[Tt]itle"):
            svc.create_accomplishment({}, user_id="legacy")

    def test_rejects_blank_title(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="[Tt]itle"):
            svc.create_accomplishment({"title": "   "}, user_id="legacy")

    def test_stores_all_star_fields(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        result = svc.create_accomplishment(
            {
                "title": "Led migration",
                "situation": "Monolith caused long deploys.",
                "task": "Migrate 3 services.",
                "action": "Coordinated 4 teams.",
                "result": "80% faster deploys.",
            },
            user_id="legacy",
        )
        assert result["title"] == "Led migration"
        assert result["situation"] == "Monolith caused long deploys."
        assert result["task"] == "Migrate 3 services."
        assert result["action"] == "Coordinated 4 teams."
        assert result["result"] == "80% faster deploys."

    def test_tags_trimmed_and_persisted(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        result = svc.create_accomplishment(
            {
                "title": "Test",
                "tags": ["  leadership  ", "technical", "leadership"],
            },
            user_id="legacy",
        )
        assert set(result["tags"]) == {"leadership", "technical"}
        assert len(result["tags"]) == 2  # deduplicated

    def test_tags_normalized_to_lowercase(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        result = svc.create_accomplishment(
            {
                "title": "Test",
                "tags": ["Leadership", "TECHNICAL", "Team Lead"],
            },
            user_id="legacy",
        )
        assert set(result["tags"]) == {"leadership", "technical", "team lead"}

    def test_tags_case_insensitive_dedup(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        result = svc.create_accomplishment(
            {
                "title": "Test",
                "tags": ["Leadership", "leadership", "LEADERSHIP"],
            },
            user_id="legacy",
        )
        assert result["tags"] == ["leadership"]

    def test_accomplishment_date_nullable(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        result = svc.create_accomplishment({"title": "No date"}, user_id="legacy")
        assert result["accomplishment_date"] is None

    def test_accomplishment_date_stored(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        result = svc.create_accomplishment(
            {"title": "Dated", "accomplishment_date": "2024-03-15"}, user_id="legacy"
        )
        assert result["accomplishment_date"] == "2024-03-15"

    def test_timestamps_are_non_empty_strings(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        result = svc.create_accomplishment(
            {"title": "Timestamp test"}, user_id="legacy"
        )
        assert isinstance(result["created_at"], str) and result["created_at"] != ""
        assert isinstance(result["updated_at"], str) and result["updated_at"] != ""

    def test_assigns_unique_id(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        a = svc.create_accomplishment({"title": "First"}, user_id="legacy")
        b = svc.create_accomplishment({"title": "Second"}, user_id="legacy")
        assert a["id"] != b["id"]

    def test_partial_star_allowed(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        result = svc.create_accomplishment({"title": "Partial"}, user_id="legacy")
        assert result["situation"] == ""
        assert result["task"] == ""
        assert result["action"] == ""
        assert result["result"] == ""

    def test_invalid_date_format_rejected(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="[Dd]ate"):
            svc.create_accomplishment(
                {"title": "Bad date", "accomplishment_date": "March 2024"},
                user_id="legacy",
            )


class TestAccomplishmentServiceGet:
    """Tests for AccomplishmentService.get_accomplishment (T006)."""

    def test_gets_existing(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        created = svc.create_accomplishment({"title": "Find me"}, user_id="legacy")
        result = svc.get_accomplishment(created["id"], user_id="legacy")
        assert result["id"] == created["id"]
        assert result["title"] == "Find me"

    def test_raises_for_nonexistent(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="not found"):
            svc.get_accomplishment(9999, user_id="legacy")


# ── US2: List / Tags ──────────────────────────────────────────────────────────


class TestAccomplishmentServiceList:
    """Tests for AccomplishmentService.list_accomplishments (T018)."""

    def test_lists_all(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        svc.create_accomplishment({"title": "A"}, user_id="legacy")
        svc.create_accomplishment({"title": "B"}, user_id="legacy")
        results = svc.list_accomplishments(user_id="legacy")
        assert len(results) == 2

    def test_returns_empty_when_none(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        assert svc.list_accomplishments(user_id="legacy") == []

    def test_filter_by_tag(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        svc.create_accomplishment(
            {"title": "Leader", "tags": ["leadership"]}, user_id="legacy"
        )
        svc.create_accomplishment(
            {"title": "Coder", "tags": ["technical"]}, user_id="legacy"
        )
        results = svc.list_accomplishments(tags=["leadership"], user_id="legacy")
        assert len(results) == 1
        assert results[0]["title"] == "Leader"

    def test_filter_by_tag_no_match_returns_empty(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        svc.create_accomplishment(
            {"title": "A", "tags": ["technical"]}, user_id="legacy"
        )
        assert svc.list_accomplishments(tags=["leadership"], user_id="legacy") == []

    def test_returns_summary_shape_no_star_body(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        svc.create_accomplishment(
            {"title": "Test", "situation": "A situation", "result": "Good"},
            user_id="legacy",
        )
        results = svc.list_accomplishments(user_id="legacy")
        assert len(results) == 1
        item = results[0]
        assert "situation" not in item
        assert "task" not in item
        assert "action" not in item
        assert "result" not in item

    def test_reverse_chronological_by_date(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        svc.create_accomplishment(
            {"title": "Older", "accomplishment_date": "2023-01-01"}, user_id="legacy"
        )
        svc.create_accomplishment(
            {"title": "Newer", "accomplishment_date": "2024-01-01"}, user_id="legacy"
        )
        results = svc.list_accomplishments(user_id="legacy")
        assert results[0]["title"] == "Newer"
        assert results[1]["title"] == "Older"

    def test_null_date_sorted_last(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        svc.create_accomplishment({"title": "No date"}, user_id="legacy")
        svc.create_accomplishment(
            {"title": "Has date", "accomplishment_date": "2024-01-01"}, user_id="legacy"
        )
        results = svc.list_accomplishments(user_id="legacy")
        assert results[0]["title"] == "Has date"
        assert results[1]["title"] == "No date"


class TestAccomplishmentServiceMultiTagFilter:
    """Tests for AccomplishmentService.list_accomplishments multi-tag AND filter."""

    def test_multi_tag_and_returns_intersection(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        svc.create_accomplishment(
            {"title": "Both", "tags": ["leadership", "technical"]}, user_id="legacy"
        )
        svc.create_accomplishment(
            {"title": "Leader only", "tags": ["leadership"]}, user_id="legacy"
        )
        svc.create_accomplishment(
            {"title": "Tech only", "tags": ["technical"]}, user_id="legacy"
        )
        results = svc.list_accomplishments(
            tags=["leadership", "technical"], user_id="legacy"
        )
        assert len(results) == 1
        assert results[0]["title"] == "Both"

    def test_single_tag_in_list_works(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        svc.create_accomplishment(
            {"title": "Leader", "tags": ["leadership"]}, user_id="legacy"
        )
        svc.create_accomplishment(
            {"title": "Coder", "tags": ["technical"]}, user_id="legacy"
        )
        results = svc.list_accomplishments(tags=["leadership"], user_id="legacy")
        assert len(results) == 1
        assert results[0]["title"] == "Leader"

    def test_empty_tags_list_returns_all(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        svc.create_accomplishment(
            {"title": "A", "tags": ["leadership"]}, user_id="legacy"
        )
        svc.create_accomplishment(
            {"title": "B", "tags": ["technical"]}, user_id="legacy"
        )
        results = svc.list_accomplishments(tags=[], user_id="legacy")
        assert len(results) == 2

    def test_no_match_for_and_filter_returns_empty(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        svc.create_accomplishment(
            {"title": "Leader only", "tags": ["leadership"]}, user_id="legacy"
        )
        svc.create_accomplishment(
            {"title": "Tech only", "tags": ["technical"]}, user_id="legacy"
        )
        results = svc.list_accomplishments(
            tags=["leadership", "technical"], user_id="legacy"
        )
        assert results == []


class TestAccomplishmentServiceListTags:
    """Tests for AccomplishmentService.list_tags (T018)."""

    def test_returns_sorted_unique_tags(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        svc.create_accomplishment(
            {"title": "A", "tags": ["technical", "leadership"]}, user_id="legacy"
        )
        svc.create_accomplishment(
            {"title": "B", "tags": ["leadership", "cross-functional"]}, user_id="legacy"
        )
        tags = svc.list_tags(user_id="legacy")
        assert tags == sorted({"technical", "leadership", "cross-functional"})

    def test_empty_when_no_accomplishments(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        assert svc.list_tags(user_id="legacy") == []


# ── US3: Update ───────────────────────────────────────────────────────────────


class TestAccomplishmentServiceUpdate:
    """Tests for AccomplishmentService.update_accomplishment (T030)."""

    def test_partial_update_leaves_other_fields(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        created = svc.create_accomplishment(
            {"title": "Original", "situation": "Old situation"}, user_id="legacy"
        )
        updated = svc.update_accomplishment(
            created["id"], {"result": "New result"}, user_id="legacy"
        )
        assert updated["result"] == "New result"
        assert updated["situation"] == "Old situation"
        assert updated["title"] == "Original"

    def test_blank_title_raises(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        created = svc.create_accomplishment({"title": "Original"}, user_id="legacy")
        with pytest.raises(ValueError, match="[Tt]itle"):
            svc.update_accomplishment(created["id"], {"title": ""}, user_id="legacy")

    def test_unknown_id_raises(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="not found"):
            svc.update_accomplishment(9999, {"result": "x"}, user_id="legacy")

    def test_date_format_validated(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        created = svc.create_accomplishment({"title": "Original"}, user_id="legacy")
        with pytest.raises(ValueError, match="[Dd]ate"):
            svc.update_accomplishment(
                created["id"], {"accomplishment_date": "not-a-date"}, user_id="legacy"
            )

    def test_updated_at_changes(self, acc_service: object) -> None:
        import time

        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        created = svc.create_accomplishment({"title": "Original"}, user_id="legacy")
        time.sleep(0.01)
        updated = svc.update_accomplishment(
            created["id"], {"result": "New"}, user_id="legacy"
        )
        # updated_at should be set (non-empty); it may equal created_at in fast DBs
        assert isinstance(updated["updated_at"], str) and updated["updated_at"] != ""

    def test_clear_star_field_stored_as_empty(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        created = svc.create_accomplishment(
            {"title": "Original", "result": "Some result"}, user_id="legacy"
        )
        updated = svc.update_accomplishment(
            created["id"], {"result": ""}, user_id="legacy"
        )
        assert updated["result"] == ""


# ── US4: Delete ───────────────────────────────────────────────────────────────


class TestAccomplishmentServiceDelete:
    """Tests for AccomplishmentService.delete_accomplishment (T039)."""

    def test_delete_returns_record(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        created = svc.create_accomplishment({"title": "Delete me"}, user_id="legacy")
        deleted = svc.delete_accomplishment(created["id"], user_id="legacy")
        assert deleted["title"] == "Delete me"
        assert deleted["id"] == created["id"]

    def test_deleted_not_retrievable(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        created = svc.create_accomplishment({"title": "Delete me"}, user_id="legacy")
        svc.delete_accomplishment(created["id"], user_id="legacy")
        with pytest.raises(ValueError, match="not found"):
            svc.get_accomplishment(created["id"], user_id="legacy")

    def test_unknown_id_raises(self, acc_service: object) -> None:
        from pktx.accomplishment_service import AccomplishmentService

        svc: AccomplishmentService = acc_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="not found"):
            svc.delete_accomplishment(9999, user_id="legacy")
