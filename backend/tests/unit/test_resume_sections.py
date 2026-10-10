"""Section registry, stable entry ids, layout and the 033 sections."""

import json
from typing import Any

import pytest

from pktx.models import Resume
from pktx.resume_layout import LIST_ORDER, normalize_layout
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
        assert set(desc) == set(SECTIONS) | {"custom"}
        proj = {f["name"]: f for f in desc["projects"]["fields"]}
        assert "id" not in proj
        assert proj["name"]["required"] is True
        assert proj["url"]["widget"] == "url"
        assert proj["highlights"]["widget"] == "bullets"
        assert proj["description"]["widget"] == "textarea"


class TestLayoutNormalize:
    def test_default_layout_keeps_legacy_visible_and_hides_empty_new(self) -> None:
        layout = normalize_layout([], {"summary": "", "projects": []})
        by = {i["section"]: i for i in layout}
        assert [i["section"] for i in layout][:4] == [
            "summary",
            "experience",
            "education",
            "skills",
        ]
        assert by["experience"]["visible"] is True
        assert by["projects"]["visible"] is False

    def test_new_section_with_content_is_visible(self) -> None:
        layout = normalize_layout([], {"projects": [{"name": "x"}]})
        assert {i["section"]: i["visible"] for i in layout}["projects"] is True

    def test_drops_unknown_and_duplicates_keeps_order(self) -> None:
        layout = normalize_layout(
            [
                {"section": "skills", "visible": False},
                {"section": "nope"},
                {"section": "skills"},
                {"section": "summary", "title": "About"},
            ],
            {},
        )
        assert [i["section"] for i in layout][:2] == ["skills", "summary"]
        assert layout[0]["visible"] is False
        assert layout[1]["title"] == "About"
        assert sum(i["section"] == "skills" for i in layout) == 1

    def test_resume_model_normalizes_layout(self) -> None:
        r = Resume()
        assert [i.section for i in r.layout][0] == "summary"
        assert len(r.layout) == 1 + len(LIST_ORDER)


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

    def test_new_section_becomes_visible_in_layout(
        self, resume_service: ResumeService
    ) -> None:
        resume_service.add_entry("projects", NEW_ENTRIES["projects"], user_id=U)
        data = resume_service.get_resume(user_id=U)["resume_data"]
        layout = {
            i["section"]: i["visible"] for i in Resume(**data).model_dump()["layout"]
        }
        assert layout["projects"] is True
        assert layout["certifications"] is False


class TestContactProfiles:
    def test_profiles_saved_and_validated(self, resume_service: ResumeService) -> None:
        resume_service.update_section(
            "contact",
            {"profiles": [{"label": "GitLab", "url": "gitlab.com/me"}]},
            user_id=U,
        )
        contact = resume_service.get_section("contact", user_id=U)
        assert contact["profiles"] == [
            {"label": "GitLab", "url": "https://gitlab.com/me"}
        ]
        with pytest.raises(ValueError):
            resume_service.update_section(
                "contact",
                {"profiles": [{"label": "x", "url": "javascript:alert(1)"}]},
                user_id=U,
            )

    def test_existing_contact_without_profiles_loads(self) -> None:
        r = Resume.model_validate(
            {"contact": {"name": "Jo", "github": "https://github.com/jo"}}
        )
        assert r.contact.profiles == []


class TestLayout:
    def test_update_layout_order_visibility_title(
        self, resume_service: ResumeService
    ) -> None:
        out = resume_service.update_layout(
            [
                {"section": "skills", "visible": True, "title": "  Tech  "},
                {"section": "experience", "visible": False},
            ],
            user_id=U,
        )
        assert [i["section"] for i in out][:2] == ["skills", "experience"]
        assert out[0]["title"] == "Tech"
        assert out[1]["visible"] is False
        data = resume_service.get_resume(user_id=U)["resume_data"]
        assert data["layout"][0]["section"] == "skills"
        assert len(data["layout"]) == 1 + len(LIST_ORDER)

    def test_rejects_unknown_duplicate_and_bad_types(
        self, resume_service: ResumeService
    ) -> None:
        with pytest.raises(ValueError, match="Unknown layout section"):
            resume_service.update_layout([{"section": "contact"}], user_id=U)
        with pytest.raises(ValueError, match="Duplicate"):
            resume_service.update_layout(
                [{"section": "skills"}, {"section": "skills"}], user_id=U
            )
        with pytest.raises(ValueError, match="title"):
            resume_service.update_layout([{"section": "skills", "title": 5}], user_id=U)
        with pytest.raises(ValueError, match="must not exceed"):
            resume_service.update_layout(
                [{"section": "skills", "title": "x" * 201}], user_id=U
            )

    def test_create_resume_copies_layout(self, resume_service: ResumeService) -> None:
        resume_service.update_layout(
            [{"section": "skills", "visible": False}], user_id=U
        )
        v2 = resume_service.create_resume("Copy", user_id=U)
        assert v2["resume_data"]["layout"][0] == {
            "section": "skills",
            "visible": False,
            "title": None,
        }


class TestCustomSections:
    def test_add_entries_remove(self, resume_service: ResumeService) -> None:
        key = resume_service.add_custom_section("Open Source", user_id=U)
        assert key.startswith("custom:")
        data = resume_service.get_resume(user_id=U)["resume_data"]
        layout = {i["section"]: i["visible"] for i in data["layout"]}
        assert layout[key] is True

        resume_service.add_entry(
            key, {"heading": "Linux", "body": "patches"}, user_id=U
        )
        entry = resume_service.get_section(key, user_id=U)[0]
        assert entry["heading"] == "Linux" and entry["id"]
        resume_service.update_entry(key, entry["id"], {"body": "more"}, user_id=U)
        assert resume_service.get_section(key, user_id=U)[0]["body"] == "more"
        resume_service.remove_entry(key, entry["id"], user_id=U)

        resume_service.remove_custom_section(key, user_id=U)
        data = resume_service.get_resume(user_id=U)["resume_data"]
        assert key not in {i["section"] for i in data["layout"]}
        with pytest.raises(ValueError, match="Unknown custom section"):
            resume_service.add_entry(key, {"heading": "x"}, user_id=U)

    def test_title_validation_and_layout_override(
        self, resume_service: ResumeService
    ) -> None:
        with pytest.raises(ValueError, match="empty"):
            resume_service.add_custom_section("  ", user_id=U)
        key = resume_service.add_custom_section("Talks", user_id=U)
        out = resume_service.update_layout(
            [{"section": key, "title": "Speaking"}], user_id=U
        )
        assert out[0]["title"] == "Speaking"

    def test_remove_non_custom_rejected(self, resume_service: ResumeService) -> None:
        with pytest.raises(ValueError, match="Not a custom section"):
            resume_service.remove_custom_section("skills", user_id=U)


def test_blob_round_trips_through_resume_model(resume_service: ResumeService) -> None:
    resume_service.add_entry("projects", NEW_ENTRIES["projects"], user_id=U)
    blob = resume_service.get_resume(user_id=U)["resume_data"]
    assert json.loads(Resume(**blob).model_dump_json())["projects"][0]["name"] == "pktx"
