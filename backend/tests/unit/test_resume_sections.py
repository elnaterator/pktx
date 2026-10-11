"""Section registry, stable entry ids, optional sections and the 033 sections."""

import json
from typing import Any

import pytest

from pktx.models import Resume
from pktx.resume_order import CORE, LIST_ORDER, OPTIONAL, normalize_enabled
from pktx.resume_sections import (
    ALL_SECTIONS,
    LIST_SECTIONS,
    SECTIONS,
    describe_sections,
)
from pktx.resume_service import ResumeService

U = "legacy"

NEW_ENTRIES: dict[str, dict[str, Any]] = {
    "projects": {"name": "pktx", "url": "github.com/x/pktx", "tech": ["python"]},
    "certifications": {"name": "CKA", "issuer": "CNCF", "credential_id": "42"},
    "awards": {"title": "Best Hack", "issuer": "Acme", "date": "2020"},
    "publications": {"title": "On Registries", "venue": "ICSE"},
    "volunteer": {"role": "Mentor", "organization": "Code Club"},
    "languages": {"language": "Spanish", "proficiency": "Fluent"},
}


class TestRegistry:
    def test_registry_matches_layout_order_and_model(self) -> None:
        assert LIST_SECTIONS == LIST_ORDER
        assert all(k in Resume.model_fields for k in ALL_SECTIONS)

    def test_every_new_section_has_a_sample(self) -> None:
        assert set(NEW_ENTRIES) == set(LIST_SECTIONS) - {
            "experience",
            "education",
            "skills",
        }

    def test_describe_sections_lists_fields_without_id(self) -> None:
        desc = {d["key"]: d for d in describe_sections()}
        assert set(desc) == set(SECTIONS)
        assert [k for k, d in desc.items() if not d["optional"]] == list(CORE)
        proj = {f["name"]: f for f in desc["projects"]["fields"]}
        assert "id" not in proj
        assert proj["name"]["required"] is True
        assert proj["url"]["widget"] == "url"
        assert proj["highlights"]["widget"] == "bullets"
        assert proj["description"]["widget"] == "textarea"


class TestEnabledSections:
    def test_optional_sections_hidden_until_added_or_used(self) -> None:
        assert normalize_enabled([], {"projects": []}) == []
        assert normalize_enabled([], {"projects": [{"name": "x"}]}) == ["projects"]

    def test_fixed_order_and_unknown_dropped(self) -> None:
        out = normalize_enabled(["languages", "nope", "experience", "awards"], {})
        assert out == ["awards", "languages"]
        assert list(OPTIONAL) == [k for k in LIST_ORDER if k not in CORE]

    def test_resume_model_normalizes(self) -> None:
        assert Resume().enabled_sections == []
        r = Resume.model_validate({"enabled_sections": ["languages", "x"]})
        assert r.enabled_sections == ["languages"]


class TestEntryIds:
    def test_add_assigns_stable_id_and_returns_it(
        self, resume_service: ResumeService
    ) -> None:
        msg = resume_service.add_entry(
            "experience", {"title": "Dev", "company": "Acme"}, user_id=U
        )
        entry = resume_service.get_section("experience", user_id=U)[0]
        assert entry["id"] and f"id={entry['id']}" in msg

    def test_update_and_remove_by_id(self, resume_service: ResumeService) -> None:
        for t in ("A", "B"):
            resume_service.add_entry(
                "experience", {"title": t, "company": "Co"}, user_id=U
            )
        entries = resume_service.get_section("experience", user_id=U)
        b = next(e for e in entries if e["title"] == "B")
        resume_service.update_entry("experience", b["id"], {"title": "B2"}, user_id=U)
        entries = resume_service.get_section("experience", user_id=U)
        assert {e["title"] for e in entries} == {"A", "B2"}
        assert next(e for e in entries if e["title"] == "B2")["id"] == b["id"]
        resume_service.remove_entry("experience", b["id"], user_id=U)
        assert [
            e["title"] for e in resume_service.get_section("experience", user_id=U)
        ] == ["A"]

    def test_update_cannot_change_id(self, resume_service: ResumeService) -> None:
        resume_service.add_entry("skills", {"name": "Go"}, user_id=U)
        sid = resume_service.get_section("skills", user_id=U)[0]["id"]
        resume_service.update_entry("skills", sid, {"id": "hacked"}, user_id=U)
        assert resume_service.get_section("skills", user_id=U)[0]["id"] == sid

    def test_legacy_index_still_works(self, resume_service: ResumeService) -> None:
        resume_service.add_entry("skills", {"name": "Go"}, user_id=U)
        resume_service.update_entry("skills", 0, {"category": "Lang"}, user_id=U)
        resume_service.update_entry("skills", "0", {"category": "Lang2"}, user_id=U)
        assert resume_service.get_section("skills", user_id=U)[0]["category"] == "Lang2"
        resume_service.remove_entry("skills", 0, user_id=U)
        assert resume_service.get_section("skills", user_id=U) == []

    def test_unknown_id_and_bad_index(self, resume_service: ResumeService) -> None:
        with pytest.raises(ValueError, match="entry with id"):
            resume_service.remove_entry("skills", "deadbeef", user_id=U)
        with pytest.raises(ValueError, match="out of range"):
            resume_service.remove_entry("skills", 3, user_id=U)

    def test_legacy_entries_without_id_addressable_by_index(
        self, resume_service: ResumeService, db_conn: Any
    ) -> None:
        from pktx.database import update_resume_version_data

        vid = resume_service.get_resume(user_id=U)["id"]
        update_resume_version_data(
            db_conn,
            vid,
            {"education": [{"institution": "MIT", "degree": "BS"}]},
            user_id=U,
        )
        resume_service.update_entry("education", 0, {"degree": "MS"}, user_id=U)
        assert resume_service.get_section("education", user_id=U)[0]["degree"] == "MS"


class TestNewSections:
    @pytest.mark.parametrize("section", sorted(NEW_ENTRIES))
    def test_add_update_remove(
        self, resume_service: ResumeService, section: str
    ) -> None:
        resume_service.add_entry(section, NEW_ENTRIES[section], user_id=U)
        entry = resume_service.get_section(section, user_id=U)[0]
        assert entry["id"]
        field = next(iter(NEW_ENTRIES[section]))
        resume_service.update_entry(section, entry["id"], {field: "Changed"}, user_id=U)
        assert resume_service.get_section(section, user_id=U)[0][field] == "Changed"
        resume_service.remove_entry(section, entry["id"], user_id=U)
        assert resume_service.get_section(section, user_id=U) == []

    def test_urls_normalized_and_validated(self, resume_service: ResumeService) -> None:
        resume_service.add_entry("projects", NEW_ENTRIES["projects"], user_id=U)
        url = resume_service.get_section("projects", user_id=U)[0]["url"]
        assert url == "https://github.com/x/pktx"
        for section in ("projects", "certifications", "publications"):
            with pytest.raises(ValueError, match="http"):
                resume_service.add_entry(
                    section,
                    {**NEW_ENTRIES[section], "url": "javascript:alert(1)"},
                    user_id=U,
                )

    def test_length_limits(self, resume_service: ResumeService) -> None:
        with pytest.raises(ValueError, match="must not exceed"):
            resume_service.add_entry("awards", {"title": "x" * 201}, user_id=U)
        # Long free text is allowed for description bodies.
        resume_service.add_entry(
            "projects", {"name": "p", "description": "d" * 5000}, user_id=U
        )

    def test_required_fields(self, resume_service: ResumeService) -> None:
        with pytest.raises(ValueError):
            resume_service.add_entry("projects", {"description": "no name"}, user_id=U)

    def test_languages_unique_case_insensitive(
        self, resume_service: ResumeService
    ) -> None:
        resume_service.add_entry("languages", {"language": "French"}, user_id=U)
        with pytest.raises(ValueError, match="already exists"):
            resume_service.add_entry("languages", {"language": "french"}, user_id=U)

    def test_invalid_section(self, resume_service: ResumeService) -> None:
        with pytest.raises(ValueError, match="Invalid section"):
            resume_service.add_entry("hobbies", {}, user_id=U)

    def test_adding_an_entry_shows_the_section(
        self, resume_service: ResumeService
    ) -> None:
        resume_service.add_entry("projects", NEW_ENTRIES["projects"], user_id=U)
        data = resume_service.get_resume(user_id=U)["resume_data"]
        assert data["enabled_sections"] == ["projects"]


class TestContactFields:
    def test_fields_saved_normalized_and_replaced(
        self, resume_service: ResumeService
    ) -> None:
        resume_service.update_section(
            "contact",
            {
                "fields": [
                    {"key": "gitlab", "value": "gitlab.com/me"},
                    {"key": "Pronouns", "value": "they/them"},
                ]
            },
            user_id=U,
        )
        contact = resume_service.get_section("contact", user_id=U)
        assert contact["fields"] == [
            {"key": "GitLab", "value": "https://gitlab.com/me"},
            {"key": "Pronouns", "value": "they/them"},
        ]
        # `fields` is the full list: sending a shorter one removes the rest.
        resume_service.update_section(
            "contact", {"fields": [{"key": "Email", "value": "a@b.co"}]}, user_id=U
        )
        contact = resume_service.get_section("contact", user_id=U)
        assert contact["fields"] == [{"key": "Email", "value": "a@b.co"}]

    def test_invalid_field_rejected_and_nothing_saved(
        self, resume_service: ResumeService
    ) -> None:
        with pytest.raises(ValueError):
            resume_service.update_section(
                "contact",
                {"fields": [{"key": "GitHub", "value": "javascript:alert(1)"}]},
                user_id=U,
            )
        contact = resume_service.get_section("contact", user_id=U)
        assert not contact or not contact.get("fields")

    def test_legacy_keys_still_accepted(self, resume_service: ResumeService) -> None:
        resume_service.update_section(
            "contact", {"github": "github.com/me", "email": "me@x.io"}, user_id=U
        )
        contact = resume_service.get_section("contact", user_id=U)
        assert {f["key"]: f["value"] for f in contact["fields"]} == {
            "GitHub": "https://github.com/me",
            "Email": "me@x.io",
        }
        resume_service.update_section("contact", {"github": ""}, user_id=U)
        contact = resume_service.get_section("contact", user_id=U)
        assert [f["key"] for f in contact["fields"]] == ["Email"]

    def test_name_phone_location_limits(self, resume_service: ResumeService) -> None:
        with pytest.raises(ValueError, match="must not exceed"):
            resume_service.update_section("contact", {"phone": "1" * 501}, user_id=U)

    def test_existing_contact_without_fields_loads(self) -> None:
        r = Resume.model_validate({"contact": {"name": "Jo"}})
        assert r.contact.fields == []


class TestOptionalSections:
    def test_add_then_remove_empty_section(self, resume_service: ResumeService) -> None:
        resume_service.set_section_enabled("awards", True, user_id=U)
        resume_service.set_section_enabled("projects", True, user_id=U)
        data = resume_service.get_resume(user_id=U)["resume_data"]
        assert data["enabled_sections"] == ["projects", "awards"]  # fixed order
        resume_service.set_section_enabled("awards", False, user_id=U)
        data = resume_service.get_resume(user_id=U)["resume_data"]
        assert data["enabled_sections"] == ["projects"]

    def test_cannot_remove_section_with_entries(
        self, resume_service: ResumeService
    ) -> None:
        resume_service.add_entry("awards", NEW_ENTRIES["awards"], user_id=U)
        with pytest.raises(ValueError, match="has entries"):
            resume_service.set_section_enabled("awards", False, user_id=U)

    def test_core_and_unknown_sections_rejected(
        self, resume_service: ResumeService
    ) -> None:
        with pytest.raises(ValueError, match="always shown"):
            resume_service.set_section_enabled("skills", False, user_id=U)
        with pytest.raises(ValueError, match="Invalid section"):
            resume_service.set_section_enabled("hobbies", True, user_id=U)

    def test_create_resume_copies_enabled_sections(
        self, resume_service: ResumeService
    ) -> None:
        resume_service.set_section_enabled("languages", True, user_id=U)
        v2 = resume_service.create_resume("Copy", user_id=U)
        assert v2["resume_data"]["enabled_sections"] == ["languages"]


def test_blob_round_trips_through_resume_model(resume_service: ResumeService) -> None:
    resume_service.add_entry("projects", NEW_ENTRIES["projects"], user_id=U)
    blob = resume_service.get_resume(user_id=U)["resume_data"]
    assert json.loads(Resume(**blob).model_dump_json())["projects"][0]["name"] == "pktx"
