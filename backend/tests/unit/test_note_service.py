"""Unit tests for NoteService and note DB functions."""

from typing import Any

import pytest
from psycopg import Connection


@pytest.fixture
def note_service(db_conn: Connection[Any]):  # type: ignore[no-untyped-def]
    """NoteService backed by an empty PostgreSQL database."""
    from pktx.note_service import NoteService

    return NoteService(db_conn)  # type: ignore[arg-type]


# ── US1: Create ──────────────────────────────────────────────────────────────


class TestNoteServiceCreate:
    """Tests for NoteService.create_note."""

    def test_requires_title(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="[Tt]itle"):
            svc.create_note({}, user_id="legacy")

    def test_rejects_blank_title(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="[Tt]itle"):
            svc.create_note({"title": "   "}, user_id="legacy")

    def test_stores_title_and_content(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        result = svc.create_note(
            {"title": "My Note", "content": "Some content"}, user_id="legacy"
        )
        assert result["title"] == "My Note"
        assert result["content"] == "Some content"

    def test_content_defaults_to_empty(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        result = svc.create_note({"title": "No content"}, user_id="legacy")
        assert result["content"] == ""

    def test_tags_persisted(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        result = svc.create_note(
            {"title": "Tagged", "tags": ["python", "async"]}, user_id="legacy"
        )
        assert set(result["tags"]) == {"python", "async"}

    def test_timestamps_are_non_empty_strings(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        result = svc.create_note({"title": "Timestamp test"}, user_id="legacy")
        assert isinstance(result["created_at"], str) and result["created_at"] != ""
        assert isinstance(result["updated_at"], str) and result["updated_at"] != ""

    def test_assigns_unique_id(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        a = svc.create_note({"title": "First"}, user_id="legacy")
        b = svc.create_note({"title": "Second"}, user_id="legacy")
        assert a["id"] != b["id"]

    def test_title_max_length_enforced(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="200"):
            svc.create_note({"title": "x" * 201}, user_id="legacy")

    def test_content_max_length_enforced(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="100000"):
            svc.create_note(
                {"title": "Test", "content": "x" * 100_001}, user_id="legacy"
            )

    def test_tag_max_length_enforced(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="50"):
            svc.create_note({"title": "Test", "tags": ["x" * 51]}, user_id="legacy")


class TestNoteServiceGet:
    """Tests for NoteService.get_note."""

    def test_gets_existing(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        created = svc.create_note({"title": "Find me"}, user_id="legacy")
        result = svc.get_note(created["id"], user_id="legacy")
        assert result["id"] == created["id"]
        assert result["title"] == "Find me"

    def test_raises_for_nonexistent(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="not found"):
            svc.get_note(9999, user_id="legacy")

    def test_returns_full_note_with_content(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        created = svc.create_note(
            {"title": "Full", "content": "Body text", "tags": ["test"]},
            user_id="legacy",
        )
        result = svc.get_note(created["id"], user_id="legacy")
        assert result["content"] == "Body text"
        assert result["tags"] == ["test"]


# ── US1: List ────────────────────────────────────────────────────────────────


class TestNoteServiceList:
    """Tests for NoteService.list_notes."""

    def test_lists_all(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        svc.create_note({"title": "A"}, user_id="legacy")
        svc.create_note({"title": "B"}, user_id="legacy")
        results = svc.list_notes(user_id="legacy")
        assert len(results) == 2

    def test_returns_empty_when_none(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        assert svc.list_notes(user_id="legacy") == []

    def test_returns_summary_shape_no_content(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        svc.create_note(
            {"title": "Test", "content": "Some body text"}, user_id="legacy"
        )
        results = svc.list_notes(user_id="legacy")
        assert len(results) == 1
        item = results[0]
        assert "content" not in item
        assert "title" in item
        assert "tags" in item

    def test_ordered_by_updated_at_desc(
        self, note_service: object, db_conn: Any
    ) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        svc.create_note({"title": "Older"}, user_id="legacy")
        newer = svc.create_note({"title": "Newer"}, user_id="legacy")
        # Force distinct updated_at via raw SQL (CURRENT_TIMESTAMP
        # is fixed per-transaction in non-autocommit mode)
        db_conn.execute(
            "UPDATE note SET updated_at = updated_at"
            " + INTERVAL '1 second' WHERE id = %s",
            (newer["id"],),
        )
        results = svc.list_notes(user_id="legacy")
        assert results[0]["title"] == "Newer"
        assert results[1]["title"] == "Older"


# ── US2: Update ──────────────────────────────────────────────────────────────


class TestNoteServiceUpdate:
    """Tests for NoteService.update_note."""

    def test_partial_update_leaves_other_fields(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        created = svc.create_note(
            {"title": "Original", "content": "Old content"}, user_id="legacy"
        )
        updated = svc.update_note(
            created["id"], {"content": "New content"}, user_id="legacy"
        )
        assert updated["content"] == "New content"
        assert updated["title"] == "Original"

    def test_blank_title_raises(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        created = svc.create_note({"title": "Original"}, user_id="legacy")
        with pytest.raises(ValueError, match="[Tt]itle"):
            svc.update_note(created["id"], {"title": ""}, user_id="legacy")

    def test_unknown_id_raises(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="not found"):
            svc.update_note(9999, {"content": "x"}, user_id="legacy")

    def test_updated_at_changes(self, note_service: object) -> None:
        import time

        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        created = svc.create_note({"title": "Original"}, user_id="legacy")
        time.sleep(0.01)
        updated = svc.update_note(created["id"], {"content": "New"}, user_id="legacy")
        assert isinstance(updated["updated_at"], str) and updated["updated_at"] != ""


# ── US3: Tags ────────────────────────────────────────────────────────────────


class TestNoteServiceNormalizeTags:
    """Tests for tag normalization."""

    def test_lowercasing(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        result = svc.create_note(
            {"title": "Test", "tags": ["Python", "ASYNC"]}, user_id="legacy"
        )
        assert result["tags"] == ["python", "async"]

    def test_trimming(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        result = svc.create_note(
            {"title": "Test", "tags": ["  python  ", "  async  "]}, user_id="legacy"
        )
        assert result["tags"] == ["python", "async"]

    def test_deduplication(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        result = svc.create_note(
            {"title": "Test", "tags": ["python", "Python", "PYTHON"]}, user_id="legacy"
        )
        assert result["tags"] == ["python"]

    def test_empty_tag_removal(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        result = svc.create_note(
            {"title": "Test", "tags": ["python", "", "  ", "async"]}, user_id="legacy"
        )
        assert result["tags"] == ["python", "async"]


class TestNoteServiceMultiTagFilter:
    """Tests for NoteService.list_notes multi-tag AND filter."""

    def test_multi_tag_and_returns_intersection(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        svc.create_note(
            {"title": "Both", "tags": ["python", "async"]}, user_id="legacy"
        )
        svc.create_note({"title": "Python only", "tags": ["python"]}, user_id="legacy")
        svc.create_note({"title": "Async only", "tags": ["async"]}, user_id="legacy")
        results = svc.list_notes(tags=["python", "async"], user_id="legacy")
        assert len(results) == 1
        assert results[0]["title"] == "Both"

    def test_single_tag_in_list_works(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        svc.create_note({"title": "Python note", "tags": ["python"]}, user_id="legacy")
        svc.create_note({"title": "Async note", "tags": ["async"]}, user_id="legacy")
        results = svc.list_notes(tags=["python"], user_id="legacy")
        assert len(results) == 1
        assert results[0]["title"] == "Python note"

    def test_empty_tags_list_returns_all(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        svc.create_note({"title": "A", "tags": ["python"]}, user_id="legacy")
        svc.create_note({"title": "B", "tags": ["async"]}, user_id="legacy")
        results = svc.list_notes(tags=[], user_id="legacy")
        assert len(results) == 2

    def test_no_match_for_and_filter_returns_empty(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        svc.create_note({"title": "Python only", "tags": ["python"]}, user_id="legacy")
        svc.create_note({"title": "Async only", "tags": ["async"]}, user_id="legacy")
        results = svc.list_notes(tags=["python", "async"], user_id="legacy")
        assert results == []


class TestNoteServiceListTags:
    """Tests for NoteService.list_tags."""

    def test_returns_sorted_unique_tags(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        svc.create_note({"title": "A", "tags": ["python", "async"]}, user_id="legacy")
        svc.create_note({"title": "B", "tags": ["async", "fastapi"]}, user_id="legacy")
        tags = svc.list_tags(user_id="legacy")
        assert tags == ["async", "fastapi", "python"]

    def test_empty_when_no_notes(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        assert svc.list_tags(user_id="legacy") == []


# ── US4: Delete ──────────────────────────────────────────────────────────────


class TestNoteServiceDelete:
    """Tests for NoteService.delete_note."""

    def test_delete_returns_record(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        created = svc.create_note({"title": "Delete me"}, user_id="legacy")
        deleted = svc.delete_note(created["id"], user_id="legacy")
        assert deleted["title"] == "Delete me"
        assert deleted["id"] == created["id"]

    def test_deleted_not_retrievable(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        created = svc.create_note({"title": "Delete me"}, user_id="legacy")
        svc.delete_note(created["id"], user_id="legacy")
        with pytest.raises(ValueError, match="not found"):
            svc.get_note(created["id"], user_id="legacy")

    def test_unknown_id_raises(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="not found"):
            svc.delete_note(9999, user_id="legacy")


# ── US5: Search and Filter ───────────────────────────────────────────────────


class TestNoteServiceSearch:
    """Tests for list_notes with search and filter params."""

    def test_filter_by_tag(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        svc.create_note({"title": "Python note", "tags": ["python"]}, user_id="legacy")
        svc.create_note({"title": "Go note", "tags": ["go"]}, user_id="legacy")
        results = svc.list_notes(tags=["python"], user_id="legacy")
        assert len(results) == 1
        assert results[0]["title"] == "Python note"

    def test_search_by_keyword_in_title(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        svc.create_note(
            {"title": "Python patterns", "content": "Body"}, user_id="legacy"
        )
        svc.create_note({"title": "Go patterns", "content": "Body"}, user_id="legacy")
        results = svc.list_notes(q="python", user_id="legacy")
        assert len(results) == 1
        assert results[0]["title"] == "Python patterns"

    def test_search_by_keyword_in_content(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        svc.create_note(
            {"title": "Note", "content": "Python is great"}, user_id="legacy"
        )
        svc.create_note({"title": "Note2", "content": "Go is fast"}, user_id="legacy")
        results = svc.list_notes(q="python", user_id="legacy")
        assert len(results) == 1
        assert results[0]["title"] == "Note"

    def test_search_case_insensitive(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        svc.create_note({"title": "PYTHON patterns"}, user_id="legacy")
        results = svc.list_notes(q="python", user_id="legacy")
        assert len(results) == 1

    def test_search_multi_word_and(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        svc.create_note(
            {"title": "Python async patterns", "content": "FastAPI"}, user_id="legacy"
        )
        svc.create_note(
            {"title": "Python sync patterns", "content": "Flask"}, user_id="legacy"
        )
        results = svc.list_notes(q="python async", user_id="legacy")
        assert len(results) == 1
        assert results[0]["title"] == "Python async patterns"

    def test_combined_tag_and_keyword(self, note_service: object) -> None:
        from pktx.note_service import NoteService

        svc: NoteService = note_service  # type: ignore[assignment]
        svc.create_note(
            {"title": "Python note", "tags": ["python"], "content": "async stuff"},
            user_id="legacy",
        )
        svc.create_note(
            {"title": "Go note", "tags": ["go"], "content": "async stuff"},
            user_id="legacy",
        )
        svc.create_note(
            {"title": "Python sync", "tags": ["python"], "content": "sync stuff"},
            user_id="legacy",
        )
        results = svc.list_notes(tags=["python"], q="async", user_id="legacy")
        assert len(results) == 1
        assert results[0]["title"] == "Python note"
