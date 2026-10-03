"""Unit tests for ContactService and contact DB functions."""

from typing import Any

import pytest
from psycopg import Connection


@pytest.fixture
def contact_service(db_conn: Connection[Any]):  # type: ignore[no-untyped-def]
    """ContactService backed by an empty PostgreSQL database."""
    from pktx.contact_service import ContactService

    return ContactService(db_conn)  # type: ignore[arg-type]


# ── Create ──────────────────────────────────────────────────────────────────


class TestContactServiceCreate:
    def test_requires_name(self, contact_service: object) -> None:
        from pktx.contact_service import ContactService

        svc: ContactService = contact_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="[Nn]ame"):
            svc.create_contact({}, user_id="legacy")

    def test_rejects_blank_name(self, contact_service: object) -> None:
        from pktx.contact_service import ContactService

        svc: ContactService = contact_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="[Nn]ame"):
            svc.create_contact({"name": "   "}, user_id="legacy")

    def test_stores_name(self, contact_service: object) -> None:
        from pktx.contact_service import ContactService

        svc: ContactService = contact_service  # type: ignore[assignment]
        result = svc.create_contact({"name": "Alice Smith"}, user_id="legacy")
        assert result["name"] == "Alice Smith"

    def test_optional_fields_default_none(self, contact_service: object) -> None:
        from pktx.contact_service import ContactService

        svc: ContactService = contact_service  # type: ignore[assignment]
        result = svc.create_contact({"name": "Bob"}, user_id="legacy")
        assert result["email"] is None
        assert result["phone"] is None
        assert result["company"] is None
        assert result["title"] is None
        assert result["relationship"] is None

    def test_notes_defaults_empty(self, contact_service: object) -> None:
        from pktx.contact_service import ContactService

        svc: ContactService = contact_service  # type: ignore[assignment]
        result = svc.create_contact({"name": "Carol"}, user_id="legacy")
        assert result["notes"] == ""

    def test_tags_persisted(self, contact_service: object) -> None:
        from pktx.contact_service import ContactService

        svc: ContactService = contact_service  # type: ignore[assignment]
        result = svc.create_contact(
            {"name": "Dave", "tags": ["recruiter", "ml"]}, user_id="legacy"
        )
        assert set(result["tags"]) == {"recruiter", "ml"}

    def test_timestamps_non_empty(self, contact_service: object) -> None:
        from pktx.contact_service import ContactService

        svc: ContactService = contact_service  # type: ignore[assignment]
        result = svc.create_contact({"name": "Eve"}, user_id="legacy")
        assert result["created_at"]
        assert result["updated_at"]

    def test_rejects_oversized_notes(self, contact_service: object) -> None:
        from pktx.contact_service import ContactService

        svc: ContactService = contact_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="[Nn]otes"):
            svc.create_contact(
                {"name": "Frank", "notes": "x" * 100_001}, user_id="legacy"
            )

    def test_rejects_invalid_date_format(self, contact_service: object) -> None:
        from pktx.contact_service import ContactService

        svc: ContactService = contact_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            svc.create_contact(
                {"name": "Grace", "followup_date": "not-a-date"}, user_id="legacy"
            )

    def test_accepts_valid_iso_date(self, contact_service: object) -> None:
        from pktx.contact_service import ContactService

        svc: ContactService = contact_service  # type: ignore[assignment]
        result = svc.create_contact(
            {"name": "Hank", "followup_date": "2025-06-01"}, user_id="legacy"
        )
        assert result["followup_date"] == "2025-06-01"

    def test_accepts_empty_string_date_as_none(self, contact_service: object) -> None:
        from pktx.contact_service import ContactService

        svc: ContactService = contact_service  # type: ignore[assignment]
        result = svc.create_contact(
            {"name": "Iris", "followup_date": ""}, user_id="legacy"
        )
        assert result["followup_date"] is None


# ── Tag normalization ────────────────────────────────────────────────────────


class TestNormalizeTags:
    def test_lowercases_tags(self, contact_service: object) -> None:
        from pktx.contact_service import ContactService

        svc: ContactService = contact_service  # type: ignore[assignment]
        result = svc.create_contact(
            {"name": "X", "tags": ["PYTHON", "ML"]}, user_id="legacy"
        )
        assert result["tags"] == ["python", "ml"]

    def test_trims_whitespace(self, contact_service: object) -> None:
        from pktx.contact_service import ContactService

        svc: ContactService = contact_service  # type: ignore[assignment]
        result = svc.create_contact(
            {"name": "X", "tags": [" golang ", "  rust  "]}, user_id="legacy"
        )
        assert result["tags"] == ["golang", "rust"]

    def test_deduplicates(self, contact_service: object) -> None:
        from pktx.contact_service import ContactService

        svc: ContactService = contact_service  # type: ignore[assignment]
        result = svc.create_contact(
            {"name": "X", "tags": ["go", "Go", " go "]}, user_id="legacy"
        )
        assert result["tags"] == ["go"]

    def test_rejects_tag_over_50_chars(self, contact_service: object) -> None:
        from pktx.contact_service import ContactService

        svc: ContactService = contact_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="50"):
            svc.create_contact({"name": "X", "tags": ["a" * 51]}, user_id="legacy")


# ── Update ──────────────────────────────────────────────────────────────────


class TestContactServiceUpdate:
    def test_update_name(self, contact_service: object) -> None:
        from pktx.contact_service import ContactService

        svc: ContactService = contact_service  # type: ignore[assignment]
        c = svc.create_contact({"name": "Alice"}, user_id="legacy")
        updated = svc.update_contact(c["id"], {"name": "Alice B"}, user_id="legacy")
        assert updated["name"] == "Alice B"

    def test_rejects_blank_name_on_update(self, contact_service: object) -> None:
        from pktx.contact_service import ContactService

        svc: ContactService = contact_service  # type: ignore[assignment]
        c = svc.create_contact({"name": "Alice"}, user_id="legacy")
        with pytest.raises(ValueError, match="[Nn]ame"):
            svc.update_contact(c["id"], {"name": "  "}, user_id="legacy")

    def test_update_not_found(self, contact_service: object) -> None:
        from pktx.contact_service import ContactService

        svc: ContactService = contact_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="not found"):
            svc.update_contact(9999, {"name": "X"}, user_id="legacy")
