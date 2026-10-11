"""Unit tests for pktx.models module."""

import pytest
from pydantic import ValidationError


class TestContactInfo:
    """Contact = name/phone/location plus key/value fields."""

    def test_empty(self) -> None:
        from pktx.models import ContactInfo

        contact = ContactInfo()
        assert contact.name is None and contact.phone is None
        assert contact.location is None and contact.fields == []

    def test_fields_validated_by_key_kind(self) -> None:
        from pktx.models import ContactInfo

        c = ContactInfo.model_validate(
            {
                "name": "Jane",
                "fields": [
                    {"key": "linked in", "value": "linkedin.com/in/jane"},
                    {"key": "Email", "value": " jane@example.com "},
                    {"key": "Pronouns", "value": "she/her"},
                ],
            }
        )
        assert [(f.key, f.value) for f in c.fields] == [
            ("LinkedIn", "https://linkedin.com/in/jane"),
            ("Email", "jane@example.com"),
            ("Pronouns", "she/her"),
        ]

    @pytest.mark.parametrize(
        "field",
        [
            {"key": "GitHub", "value": "javascript:alert(1)"},
            {"key": "Email", "value": "not-an-email"},
            {"key": "", "value": "x"},
            {"key": "Custom", "value": "  "},
            {"key": "Custom", "value": "x" * 501},
            {"key": "k" * 201, "value": "x"},
        ],
    )
    def test_invalid_fields_rejected(self, field: dict) -> None:
        from pktx.models import ContactInfo

        with pytest.raises(ValidationError):
            ContactInfo.model_validate({"fields": [field]})

    def test_duplicate_keys_rejected_case_insensitively(self) -> None:
        from pktx.models import ContactInfo

        with pytest.raises(ValidationError, match="Duplicate"):
            ContactInfo.model_validate(
                {
                    "fields": [
                        {"key": "Pronouns", "value": "a"},
                        {"key": "pronouns", "value": "b"},
                    ]
                }
            )

    def test_too_many_fields_rejected(self) -> None:
        from pktx.models import ContactInfo

        fields = [{"key": f"k{i}", "value": "v"} for i in range(31)]
        with pytest.raises(ValidationError, match="At most"):
            ContactInfo.model_validate({"fields": fields})

    def test_legacy_shape_upgrades(self) -> None:
        from pktx.models import ContactInfo

        c = ContactInfo.model_validate(
            {
                "name": "Jane",
                "email": "jane@example.com",
                "github": "github.com/jane",
                "profiles": [{"label": "GitLab", "url": "https://gitlab.com/jane"}],
            }
        )
        assert {f.key: f.value for f in c.fields} == {
            "Email": "jane@example.com",
            "GitHub": "https://github.com/jane",
            "GitLab": "https://gitlab.com/jane",
        }

    def test_legacy_key_overrides_and_empty_removes(self) -> None:
        from pktx.models import ContactInfo

        base = {"fields": [{"key": "Email", "value": "old@example.com"}]}
        c = ContactInfo.model_validate({**base, "email": "new@example.com"})
        assert [(f.key, f.value) for f in c.fields] == [("Email", "new@example.com")]
        c = ContactInfo.model_validate({**base, "email": None})
        assert c.fields == []


class TestContactKeys:
    def test_presets_start_with_common_links(self) -> None:
        from pktx.contact_keys import CONTACT_KEYS

        keys = [c.key for c in CONTACT_KEYS]
        assert keys[:5] == ["Email", "Website", "LinkedIn", "GitHub", "GitLab"]

    def test_canonical_and_kind(self) -> None:
        from pktx.contact_keys import canonical_key, key_kind

        assert canonical_key("  git   hub ") == "GitHub"
        assert canonical_key("  Pronouns ") == "Pronouns"
        assert key_kind("github") == "url"
        assert key_kind("EMAIL") == "email"
        assert key_kind("Pronouns") == "text"


class TestWorkExperience:
    """Tests for WorkExperience model — title and company required."""

    def test_valid_experience(self) -> None:
        from pktx.models import WorkExperience

        exp = WorkExperience(
            title="Software Engineer",
            company="Acme Corp",
            start_date="2021-01",
            end_date="present",
            location="SF, CA",
            highlights=["Built things"],
        )
        assert exp.title == "Software Engineer"
        assert exp.company == "Acme Corp"

    def test_minimal_experience(self) -> None:
        from pktx.models import WorkExperience

        exp = WorkExperience(title="Engineer", company="Co")
        assert exp.start_date is None
        assert exp.highlights == []

    def test_missing_title_raises(self) -> None:
        from pktx.models import WorkExperience

        with pytest.raises(ValidationError):
            WorkExperience(company="Acme Corp")  # type: ignore[call-arg]

    def test_missing_company_raises(self) -> None:
        from pktx.models import WorkExperience

        with pytest.raises(ValidationError):
            WorkExperience(title="Engineer")  # type: ignore[call-arg]


class TestEducation:
    """Tests for Education model — institution and degree required."""

    def test_valid_education(self) -> None:
        from pktx.models import Education

        edu = Education(
            institution="Stanford University",
            degree="M.S. Computer Science",
            field="Computer Science",
            start_date="2016-09",
            end_date="2018-05",
            honors="Dean's List",
        )
        assert edu.institution == "Stanford University"
        assert edu.degree == "M.S. Computer Science"

    def test_minimal_education(self) -> None:
        from pktx.models import Education

        edu = Education(institution="MIT", degree="B.S.")
        assert edu.field is None
        assert edu.honors is None

    def test_missing_institution_raises(self) -> None:
        from pktx.models import Education

        with pytest.raises(ValidationError):
            Education(degree="B.S.")  # type: ignore[call-arg]

    def test_missing_degree_raises(self) -> None:
        from pktx.models import Education

        with pytest.raises(ValidationError):
            Education(institution="MIT")  # type: ignore[call-arg]

    def test_highlights_defaults_to_empty_list(self) -> None:
        from pktx.models import Education

        edu = Education(institution="MIT", degree="B.S.")
        assert edu.highlights == []

    def test_highlights_with_values(self) -> None:
        from pktx.models import Education

        edu = Education(
            institution="UC Berkeley",
            degree="B.S. CS",
            highlights=["Dean's List", "Thesis on X"],
        )
        assert edu.highlights == ["Dean's List", "Thesis on X"]

    def test_highlights_preserved_in_serialization(self) -> None:
        from pktx.models import Education

        edu = Education(
            institution="MIT",
            degree="B.S.",
            highlights=["Dean's List", "Graduated with Honors"],
        )
        data = edu.model_dump()
        assert data["highlights"] == ["Dean's List", "Graduated with Honors"]


class TestSkill:
    """Tests for Skill model — name required, category defaults to 'Other'."""

    def test_skill_with_category(self) -> None:
        from pktx.models import Skill

        skill = Skill(name="Python", category="Programming Languages")
        assert skill.name == "Python"
        assert skill.category == "Programming Languages"

    def test_skill_defaults_category_to_other(self) -> None:
        from pktx.models import Skill

        skill = Skill(name="Python")
        assert skill.category == "Other"

    def test_missing_name_raises(self) -> None:
        from pktx.models import Skill

        with pytest.raises(ValidationError):
            Skill()  # type: ignore[call-arg]

    def test_empty_category_defaults_to_other(self) -> None:
        from pktx.models import Skill

        skill = Skill(name="Python", category="")
        assert skill.category == "Other"

    def test_none_category_defaults_to_other(self) -> None:
        from pktx.models import Skill

        skill = Skill(name="Python", category=None)
        assert skill.category == "Other"


class TestResume:
    """Tests for Resume aggregate model with empty defaults."""

    def test_empty_resume(self) -> None:
        from pktx.models import Resume

        resume = Resume()
        assert resume.contact.name is None
        assert resume.summary == ""
        assert resume.experience == []
        assert resume.education == []
        assert resume.skills == []

    def test_resume_with_data(self) -> None:
        from pktx.models import ContactInfo, Education, Resume, Skill, WorkExperience

        resume = Resume(
            contact=ContactInfo(name="Jane"),
            summary="A summary",
            experience=[WorkExperience(title="Eng", company="Co")],
            education=[Education(institution="MIT", degree="BS")],
            skills=[Skill(name="Python")],
        )
        assert resume.contact.name == "Jane"
        assert len(resume.experience) == 1
        assert len(resume.education) == 1
        assert len(resume.skills) == 1
