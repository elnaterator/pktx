"""Unit tests for pktx.resume_service module (v2 version-aware API)."""

import pytest


class TestResumeServiceGetResume:
    """Tests for ResumeService.get_resume."""

    def test_returns_default_version_with_full_data(
        self, resume_service_with_data: object
    ) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        result = service.get_resume(user_id="legacy")

        assert result["is_default"] is True
        assert result["resume_data"]["contact"]["name"] == "Jane Doe"
        assert result["resume_data"]["summary"] != ""
        assert len(result["resume_data"]["experience"]) == 2
        assert len(result["resume_data"]["education"]) == 2
        assert len(result["resume_data"]["skills"]) == 8

    def test_returns_default_version_on_empty_db(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        result = service.get_resume(user_id="legacy")

        assert result["is_default"] is True
        assert isinstance(result["resume_data"], dict)

    def test_returns_specific_version_by_id(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        # Create a second version
        v2 = service.create_resume("Second Version", user_id="legacy")
        result = service.get_resume(version_id=v2["id"], user_id="legacy")

        assert result["id"] == v2["id"]
        assert result["label"] == "Second Version"

    def test_raises_for_nonexistent_version_id(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="not found"):
            service.get_resume(version_id=9999, user_id="legacy")

    def test_result_contains_metadata_fields(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        result = service.get_resume(user_id="legacy")

        assert "id" in result
        assert "label" in result
        assert "is_default" in result
        assert "resume_data" in result
        assert "created_at" in result
        assert "updated_at" in result


class TestResumeServiceGetSection:
    """Tests for ResumeService.get_section."""

    def test_get_contact_section_returns_dict(
        self, resume_service_with_data: object
    ) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        result = service.get_section("contact", user_id="legacy")

        assert isinstance(result, dict)
        assert result["name"] == "Jane Doe"
        assert result["email"] == "jane@example.com"

    def test_get_summary_section_returns_string(
        self, resume_service_with_data: object
    ) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        result = service.get_section("summary", user_id="legacy")

        assert isinstance(result, str)
        assert "Experienced software engineer" in result

    def test_get_experience_section_returns_list(
        self, resume_service_with_data: object
    ) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        result = service.get_section("experience", user_id="legacy")

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["title"] == "Senior Software Engineer"

    def test_get_education_section_returns_list(
        self, resume_service_with_data: object
    ) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        result = service.get_section("education", user_id="legacy")

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["institution"] == "Stanford University"

    def test_get_skills_section_returns_list(
        self, resume_service_with_data: object
    ) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        result = service.get_section("skills", user_id="legacy")

        assert isinstance(result, list)
        assert len(result) == 8

    def test_get_section_with_version_id(
        self, resume_service_with_data: object
    ) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        default = service.get_resume(user_id="legacy")
        result = service.get_section(
            "contact", version_id=default["id"], user_id="legacy"
        )

        assert result["name"] == "Jane Doe"

    def test_invalid_section_raises_value_error(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="Invalid section"):
            service.get_section("invalid_section", user_id="legacy")


class TestResumeServiceUpdateSection:
    """Tests for ResumeService.update_section."""

    def test_update_contact_merges_fields(
        self, resume_service_with_data: object
    ) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        service.update_section(
            "contact", {"email": "new@example.com"}, user_id="legacy"
        )

        contact = service.get_section("contact", user_id="legacy")
        assert contact["email"] == "new@example.com"
        assert contact["name"] == "Jane Doe"  # preserved

    def test_update_contact_returns_string(
        self, resume_service_with_data: object
    ) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        result = service.update_section(
            "contact", {"phone": "+1-555-9999"}, user_id="legacy"
        )

        assert isinstance(result, str)

    def test_update_summary_replaces_text(
        self, resume_service_with_data: object
    ) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        service.update_section(
            "summary", {"text": "New summary text."}, user_id="legacy"
        )

        summary = service.get_section("summary", user_id="legacy")
        assert summary == "New summary text."

    def test_update_summary_returns_string(
        self, resume_service_with_data: object
    ) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        result = service.update_section(
            "summary", {"text": "Updated."}, user_id="legacy"
        )

        assert isinstance(result, str)

    def test_update_contact_with_multiple_fields(
        self, resume_service_with_data: object
    ) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        service.update_section(
            "contact",
            {"email": "updated@test.com", "phone": "+1-800-0000"},
            user_id="legacy",
        )

        contact = service.get_section("contact", user_id="legacy")
        assert contact["email"] == "updated@test.com"
        assert contact["phone"] == "+1-800-0000"
        assert contact["name"] == "Jane Doe"  # preserved

    def test_update_experience_section_raises(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="Invalid section"):
            service.update_section("experience", {"title": "x"}, user_id="legacy")

    def test_update_summary_empty_text_raises(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="Summary text must not be empty"):
            service.update_section("summary", {"text": ""}, user_id="legacy")


class TestResumeServiceAddEntry:
    """Tests for ResumeService.add_entry."""

    def test_add_experience_prepends(self, resume_service_with_data: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        service.add_entry(
            "experience", {"title": "CTO", "company": "NewCo"}, user_id="legacy"
        )

        experience = service.get_section("experience", user_id="legacy")
        assert len(experience) == 3
        assert experience[0]["title"] == "CTO"
        assert experience[1]["title"] == "Senior Software Engineer"

    def test_add_experience_returns_string(
        self, resume_service_with_data: object
    ) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        result = service.add_entry(
            "experience", {"title": "Intern", "company": "SmallCo"}, user_id="legacy"
        )

        assert isinstance(result, str)

    def test_add_education_prepends(self, resume_service_with_data: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        service.add_entry(
            "education", {"institution": "MIT", "degree": "Ph.D. CS"}, user_id="legacy"
        )

        education = service.get_section("education", user_id="legacy")
        assert len(education) == 3
        assert education[0]["institution"] == "MIT"

    def test_add_skill_appends(self, resume_service_with_data: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        service.add_entry(
            "skills",
            {"name": "Rust", "category": "Programming Languages"},
            user_id="legacy",
        )

        skills = service.get_section("skills", user_id="legacy")
        skill_names = [s["name"] for s in skills]
        assert "Rust" in skill_names
        # Rust should be at the end (appended)
        assert skills[-1]["name"] == "Rust"

    def test_add_skill_rejects_case_insensitive_duplicate(
        self, resume_service_with_data: object
    ) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        with pytest.raises(ValueError, match="already exists"):
            service.add_entry(
                "skills", {"name": "python", "category": "Languages"}, user_id="legacy"
            )

    def test_add_entry_to_empty_db(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        service.add_entry(
            "experience", {"title": "Dev", "company": "Co"}, user_id="legacy"
        )

        experience = service.get_section("experience", user_id="legacy")
        assert len(experience) == 1
        assert experience[0]["title"] == "Dev"

    def test_add_entry_invalid_section_raises(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="Invalid section"):
            service.add_entry("contact", {"name": "x"}, user_id="legacy")

    def test_add_entry_invalid_section_summary_raises(
        self, resume_service: object
    ) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="Invalid section"):
            service.add_entry("summary", {"text": "y"}, user_id="legacy")


class TestResumeServiceUpdateEntry:
    """Tests for ResumeService.update_entry."""

    def test_update_experience_in_place(self, resume_service_with_data: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        service.update_entry(
            "experience", 0, {"title": "Staff Engineer"}, user_id="legacy"
        )

        experience = service.get_section("experience", user_id="legacy")
        assert experience[0]["title"] == "Staff Engineer"
        assert experience[0]["company"] == "Acme Corp"  # preserved

    def test_update_experience_returns_string(
        self, resume_service_with_data: object
    ) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        result = service.update_entry(
            "experience", 0, {"title": "Principal Engineer"}, user_id="legacy"
        )

        assert isinstance(result, str)

    def test_update_education_entry(self, resume_service_with_data: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        service.update_entry(
            "education", 0, {"honors": "Magna Cum Laude"}, user_id="legacy"
        )

        education = service.get_section("education", user_id="legacy")
        assert education[0]["honors"] == "Magna Cum Laude"
        assert education[0]["institution"] == "Stanford University"  # preserved

    def test_update_skill_entry(self, resume_service_with_data: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        service.update_entry("skills", 0, {"name": "Python 3"}, user_id="legacy")

        skills = service.get_section("skills", user_id="legacy")
        assert skills[0]["name"] == "Python 3"

    def test_update_entry_out_of_range_raises(
        self, resume_service_with_data: object
    ) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        with pytest.raises(ValueError, match="out of range"):
            service.update_entry("experience", 99, {"title": "x"}, user_id="legacy")

    def test_update_entry_invalid_section_raises(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="Invalid section"):
            service.update_entry("contact", 0, {"name": "x"}, user_id="legacy")


class TestResumeServiceRemoveEntry:
    """Tests for ResumeService.remove_entry."""

    def test_remove_experience_and_compact(
        self, resume_service_with_data: object
    ) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        service.remove_entry("experience", 0, user_id="legacy")

        experience = service.get_section("experience", user_id="legacy")
        assert len(experience) == 1
        assert experience[0]["title"] == "Software Engineer"

    def test_remove_experience_returns_string(
        self, resume_service_with_data: object
    ) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        result = service.remove_entry("experience", 0, user_id="legacy")

        assert isinstance(result, str)

    def test_remove_education_entry(self, resume_service_with_data: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        service.remove_entry("education", 0, user_id="legacy")

        education = service.get_section("education", user_id="legacy")
        assert len(education) == 1
        assert education[0]["institution"] == "UC Berkeley"

    def test_remove_skill_entry(self, resume_service_with_data: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        initial_skills = service.get_section("skills", user_id="legacy")
        first_skill_name = initial_skills[0]["name"]

        service.remove_entry("skills", 0, user_id="legacy")

        skills = service.get_section("skills", user_id="legacy")
        assert len(skills) == 7
        assert all(s["name"] != first_skill_name for s in skills)

    def test_remove_entry_out_of_range_raises(
        self, resume_service_with_data: object
    ) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        with pytest.raises(ValueError, match="out of range"):
            service.remove_entry("experience", 99, user_id="legacy")

    def test_remove_entry_invalid_section_raises(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="Invalid section"):
            service.remove_entry("contact", 0, user_id="legacy")


class TestResumeServiceListResumes:
    """Tests for ResumeService.list_resumes."""

    def test_returns_list(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        result = service.list_resumes(user_id="legacy")

        assert isinstance(result, list)
        assert len(result) >= 1

    def test_includes_metadata_fields(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        versions = service.list_resumes(user_id="legacy")
        v = versions[0]

        assert "id" in v
        assert "label" in v
        assert "is_default" in v
        assert "app_count" in v

    def test_shows_default_version(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        versions = service.list_resumes(user_id="legacy")
        defaults = [v for v in versions if v["is_default"]]

        assert len(defaults) == 1

    def test_shows_all_versions_after_create(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        service.create_resume("Alpha", user_id="legacy")
        service.create_resume("Beta", user_id="legacy")

        versions = service.list_resumes(user_id="legacy")
        labels = [v["label"] for v in versions]
        assert "Alpha" in labels
        assert "Beta" in labels

    def test_app_count_from_linked_applications(
        self, resume_service: object, db_conn: object
    ) -> None:
        from psycopg import Connection

        from pktx.database import (
            create_application,
            link_insert,
            load_default_resume_version,
        )
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        conn: Connection = db_conn  # type: ignore[assignment]

        default = load_default_resume_version(conn, user_id="legacy")  # type: ignore[arg-type]
        app = create_application(
            conn,  # type: ignore[arg-type]
            {"company": "Co", "position": "Dev"},
            user_id="legacy",
        )
        link_insert(conn, "application", app["id"], "resume", default["id"], "legacy")  # type: ignore[arg-type]

        versions = service.list_resumes(user_id="legacy")
        target = next(v for v in versions if v["id"] == default["id"])
        assert target["app_count"] == 1


class TestResumeServiceCreateResume:
    """Tests for ResumeService.create_resume."""

    def test_creates_copy_of_default(self, resume_service_with_data: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        new_version = service.create_resume("My Custom Resume", user_id="legacy")

        assert new_version["label"] == "My Custom Resume"
        assert new_version["resume_data"]["contact"]["name"] == "Jane Doe"

    def test_new_version_not_default(self, resume_service_with_data: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        new_version = service.create_resume("Side Resume", user_id="legacy")

        assert new_version["is_default"] is False

    def test_empty_label_raises(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="Label must not be empty"):
            service.create_resume("", user_id="legacy")

    def test_whitespace_only_label_raises(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="Label must not be empty"):
            service.create_resume("   ", user_id="legacy")

    def test_label_is_stripped(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        new_version = service.create_resume("  Trimmed Label  ", user_id="legacy")

        assert new_version["label"] == "Trimmed Label"


class TestResumeServiceSetDefault:
    """Tests for ResumeService.set_default."""

    def test_changes_default_version(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        v2 = service.create_resume("Version 2", user_id="legacy")
        service.set_default(v2["id"], user_id="legacy")

        default = service.get_resume(user_id="legacy")
        assert default["id"] == v2["id"]

    def test_returns_confirmation_string(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        v2 = service.create_resume("New Default", user_id="legacy")
        result = service.set_default(v2["id"], user_id="legacy")

        assert isinstance(result, str)
        assert "New Default" in result

    def test_only_one_default_after_change(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        v2 = service.create_resume("Another", user_id="legacy")
        service.set_default(v2["id"], user_id="legacy")

        versions = service.list_resumes(user_id="legacy")
        defaults = [v for v in versions if v["is_default"]]
        assert len(defaults) == 1

    def test_raises_for_nonexistent_id(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="not found"):
            service.set_default(9999, user_id="legacy")


class TestResumeServiceDeleteResume:
    """Tests for ResumeService.delete_resume."""

    def test_removes_version(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        v2 = service.create_resume("Temporary", user_id="legacy")
        service.delete_resume(v2["id"], user_id="legacy")

        versions = service.list_resumes(user_id="legacy")
        ids = [v["id"] for v in versions]
        assert v2["id"] not in ids

    def test_returns_confirmation_string(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        v2 = service.create_resume("To Delete", user_id="legacy")
        result = service.delete_resume(v2["id"], user_id="legacy")

        assert isinstance(result, str)
        assert "To Delete" in result

    def test_raises_when_deleting_last_version(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        default = service.get_resume(user_id="legacy")
        with pytest.raises(ValueError, match="last remaining"):
            service.delete_resume(default["id"], user_id="legacy")


class TestResumeServiceUpdateMetadata:
    """Tests for ResumeService.update_metadata."""

    def test_renames_version(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        default = service.get_resume(user_id="legacy")
        updated = service.update_metadata(
            default["id"], "Renamed Resume", user_id="legacy"
        )

        assert updated["label"] == "Renamed Resume"

    def test_empty_label_raises(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        default = service.get_resume(user_id="legacy")
        with pytest.raises(ValueError, match="Label must not be empty"):
            service.update_metadata(default["id"], "", user_id="legacy")

    def test_raises_for_nonexistent_id(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        with pytest.raises(ValueError, match="not found"):
            service.update_metadata(9999, "Ghost", user_id="legacy")


class TestVersionIsolation:
    """Tests ensuring edits to one version do not affect others."""

    def test_editing_copy_does_not_affect_original(
        self, resume_service_with_data: object
    ) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        default = service.get_resume(user_id="legacy")
        original_name = default["resume_data"]["contact"]["name"]

        # Create a copy and edit it
        copy = service.create_resume("Copy", user_id="legacy")
        service.update_section(
            "contact",
            {"name": "Modified Name"},
            version_id=copy["id"],
            user_id="legacy",
        )

        # Original default should be unchanged
        default_again = service.get_resume(version_id=default["id"], user_id="legacy")
        assert default_again["resume_data"]["contact"]["name"] == original_name

    def test_adding_entry_to_copy_does_not_affect_original(
        self, resume_service_with_data: object
    ) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        default = service.get_resume(user_id="legacy")
        original_exp_count = len(default["resume_data"]["experience"])

        # Create a copy and add an experience entry
        copy = service.create_resume("Copy with Extra Exp", user_id="legacy")
        service.add_entry(
            "experience",
            {"title": "Extra Role", "company": "ExtraCo"},
            version_id=copy["id"],
            user_id="legacy",
        )

        # Original default should be unchanged
        default_again = service.get_resume(version_id=default["id"], user_id="legacy")
        assert len(default_again["resume_data"]["experience"]) == original_exp_count

    def test_removing_entry_from_copy_does_not_affect_original(
        self, resume_service_with_data: object
    ) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service_with_data  # type: ignore[assignment]
        default = service.get_resume(user_id="legacy")
        original_skill_count = len(default["resume_data"]["skills"])

        # Create a copy and remove a skill
        copy = service.create_resume("Copy with Removed Skill", user_id="legacy")
        service.remove_entry("skills", 0, version_id=copy["id"], user_id="legacy")

        # Original default should be unchanged
        default_again = service.get_resume(version_id=default["id"], user_id="legacy")
        assert len(default_again["resume_data"]["skills"]) == original_skill_count


class TestResumeServiceTags:
    """Unit tests for tag normalization in ResumeService."""

    def test_tags_normalized_on_create(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        version = service.create_resume(
            "Tagged", tags=["  Backend  ", "BACKEND", "cloud"], user_id="legacy"
        )
        assert version["tags"] == ["backend", "cloud"]

    def test_tags_50_char_limit_on_create(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        long_tag = "x" * 51
        with pytest.raises(ValueError, match="50 characters"):
            service.create_resume("Tagged", tags=[long_tag], user_id="legacy")

    def test_tags_normalized_on_update_metadata(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        version = service.create_resume("V1", user_id="legacy")
        updated = service.update_metadata(
            version["id"], "V1", tags=["  ML  ", "ml", "data"], user_id="legacy"
        )
        assert updated["tags"] == ["ml", "data"]

    def test_list_tags_returns_merged(self, resume_service: object) -> None:
        from pktx.resume_service import ResumeService

        service: ResumeService = resume_service  # type: ignore[assignment]
        service.create_resume("A", tags=["backend"], user_id="legacy")
        service.create_resume("B", tags=["frontend"], user_id="legacy")
        tags = service.list_tags(user_id="legacy")
        assert "backend" in tags
        assert "frontend" in tags
