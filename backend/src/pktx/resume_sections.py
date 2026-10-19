"""Section registry: one definition per JSON Resume list section.

The service, MCP tools, REST routes and the frontend (via
``GET /api/resumes/schema``) all derive from ``SECTIONS``; dict order is the
display order. Adding a section means adding an ``Entry`` model in
``json_resume``, a ``Resume`` field and one ``SectionDef`` here.
"""

from dataclasses import dataclass
from typing import Any

from pktx.json_resume import (
    Award,
    Basics,
    Certificate,
    Education,
    Entry,
    Interest,
    Language,
    Project,
    Publication,
    Reference,
    Resume,
    Skill,
    Volunteer,
    Work,
)


@dataclass(frozen=True)
class SectionDef:
    key: str
    label: str
    model: type[Entry]
    # Field that titles an entry in lists (the UI falls back to the next filled one).
    primary_field: str


SECTIONS: dict[str, SectionDef] = {
    d.key: d
    for d in (
        SectionDef("work", "Experience", Work, "position"),
        SectionDef("education", "Education", Education, "institution"),
        SectionDef("skills", "Skills", Skill, "name"),
        SectionDef("projects", "Projects", Project, "name"),
        SectionDef("certificates", "Certifications & Licenses", Certificate, "name"),
        SectionDef("awards", "Awards", Award, "title"),
        SectionDef("publications", "Publications & Talks", Publication, "name"),
        SectionDef("volunteer", "Volunteer", Volunteer, "position"),
        SectionDef("languages", "Languages", Language, "language"),
        SectionDef("interests", "Interests", Interest, "name"),
        SectionDef("references", "References", Reference, "name"),
    )
}

LIST_SECTIONS: tuple[str, ...] = tuple(SECTIONS)
# Readable through get_resume(section=...): every list section plus these objects.
OBJECT_SECTIONS: tuple[str, ...] = ("basics", "meta")
ALL_SECTIONS: tuple[str, ...] = (*OBJECT_SECTIONS, *LIST_SECTIONS)

# Fail at import if the registry drifts from the document model.
_doc_fields = {f.alias or n for n, f in Resume.model_fields.items()}
if not set(ALL_SECTIONS) == _doc_fields:
    raise RuntimeError("SECTIONS is out of sync with the Resume model")


def section_def(section: str) -> SectionDef:
    """Definition for a list section key."""
    d = SECTIONS.get(section)
    if d is None:
        raise ValueError(
            f"Invalid section: '{section}'. Must be one of: {', '.join(LIST_SECTIONS)}"
        )
    return d


def section_data(doc: dict[str, Any], section: str) -> Any:
    """One part of a resume document: a list section, ``basics`` or ``meta``."""
    if section not in ALL_SECTIONS:
        raise ValueError(
            f"Invalid section: '{section}'. Must be one of: {', '.join(ALL_SECTIONS)}"
        )
    return doc.get(section, {} if section in OBJECT_SECTIONS else [])


def describe_sections() -> list[dict[str, Any]]:
    """Registry metadata and JSON Schemas served to the frontend."""
    out: list[dict[str, Any]] = [
        {
            "key": "basics",
            "label": "Basics",
            "kind": "object",
            "primaryField": "name",
            "schema": Basics.model_json_schema(by_alias=True),
        }
    ]
    out.extend(
        {
            "key": d.key,
            "label": d.label,
            "kind": "list",
            "primaryField": d.primary_field,
            "schema": d.model.model_json_schema(by_alias=True),
        }
        for d in SECTIONS.values()
    )
    return out


def entry_fields(model: type[Entry]) -> str:
    """Field list for tool docs, e.g. ``name, startDate, highlights[]``."""
    parts = []
    for name, info in model.model_fields.items():
        if name == "id":
            continue
        is_list = "list" in str(info.annotation).lower()
        parts.append(f"{info.alias or name}{'[]' if is_list else ''}")
    return ", ".join(parts)


__all__ = [
    "ALL_SECTIONS",
    "LIST_SECTIONS",
    "OBJECT_SECTIONS",
    "SECTIONS",
    "SectionDef",
    "describe_sections",
    "entry_fields",
    "section_data",
    "section_def",
]
