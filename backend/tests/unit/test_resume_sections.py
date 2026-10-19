"""Section registry: ordering, drift guard, schema served to the UI."""

import pytest

from pktx.json_resume import Resume
from pktx.resume_sections import (
    ALL_SECTIONS,
    LIST_SECTIONS,
    OBJECT_SECTIONS,
    SECTIONS,
    describe_sections,
    entry_fields,
    section_data,
    section_def,
)


class TestRegistry:
    def test_covers_every_document_section(self) -> None:
        assert set(ALL_SECTIONS) == {f.alias for f in Resume.model_fields.values()}
        assert OBJECT_SECTIONS == ("basics", "meta")

    def test_display_order(self) -> None:
        assert LIST_SECTIONS == (
            "work",
            "education",
            "skills",
            "projects",
            "certificates",
            "awards",
            "publications",
            "volunteer",
            "languages",
            "interests",
            "references",
        )

    def test_primary_field_exists_on_model(self) -> None:
        for d in SECTIONS.values():
            assert d.primary_field in d.model.model_fields, d.key

    def test_section_def_rejects_unknown(self) -> None:
        assert section_def("work").label == "Experience"
        for bad in ("experience", "basics", "contact", ""):
            with pytest.raises(ValueError, match="Invalid section"):
                section_def(bad)


class TestSectionData:
    def test_defaults_by_kind(self) -> None:
        assert section_data({}, "work") == []
        assert section_data({}, "basics") == {}
        assert section_data({"meta": {"version": "v1.0.0"}}, "meta") == {
            "version": "v1.0.0"
        }

    def test_invalid(self) -> None:
        with pytest.raises(ValueError, match="Invalid section"):
            section_data({}, "contact")


class TestDescribe:
    def test_one_entry_per_section_basics_first(self) -> None:
        out = describe_sections()
        assert [d["key"] for d in out] == ["basics", *LIST_SECTIONS]
        assert out[0]["kind"] == "object"
        assert {d["kind"] for d in out[1:]} == {"list"}

    def test_schema_uses_camel_case_and_widgets(self) -> None:
        by_key = {d["key"]: d for d in describe_sections()}
        props = by_key["publications"]["schema"]["properties"]
        assert "releaseDate" in props and props["releaseDate"]["widget"] == "date"
        assert props["summary"]["widget"] == "textarea"
        assert props["url"]["widget"] == "url"
        work = by_key["work"]["schema"]["properties"]
        assert work["highlights"]["widget"] == "bullets"
        assert (
            by_key["interests"]["schema"]["properties"]["keywords"]["widget"] == "tags"
        )
        basics = by_key["basics"]["schema"]
        assert "location" in basics["properties"] and "profiles" in basics["properties"]


def test_schema_titles_are_human_labels() -> None:
    by_key = {d["key"]: d for d in describe_sections()}

    def titles(key: str) -> dict[str, str]:
        return {k: v["title"] for k, v in by_key[key]["schema"]["properties"].items()}

    work = titles("work")
    assert work["name"] == "Company" and work["startDate"] == "Start date"
    assert work["url"] == "URL"
    edu = titles("education")
    assert edu["studyType"] == "Degree" and edu["area"] == "Field of study"
    assert titles("publications")["name"] == "Title"
    assert titles("projects")["keywords"] == "Technologies"
    assert titles("basics")["label"] == "Headline"


def test_entry_fields_lists_aliases_and_arrays() -> None:
    fields = entry_fields(SECTIONS["work"].model)
    assert "startDate" in fields and "highlights[]" in fields
    assert "id" not in fields.split(", ")
