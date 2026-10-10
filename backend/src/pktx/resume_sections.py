"""Section registry: one definition per resume section.

The service, MCP tools, REST routes and the frontend (via
``GET /api/resume-sections``) all derive from ``SECTIONS``. Adding a section
means adding a model in ``models.py``, a ``Resume`` field, a ``LIST_ORDER``
entry in ``resume_layout`` and one ``SectionDef`` here.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

from pktx.models import (
    Award,
    Certification,
    CustomEntry,
    Education,
    Language,
    Project,
    Publication,
    Resume,
    Skill,
    Volunteer,
    WorkExperience,
)
from pktx.resume_layout import CUSTOM_PREFIX, LIST_ORDER


@dataclass(frozen=True)
class SectionDef:
    key: str
    label: str
    model: type[BaseModel]
    summary: Callable[[Any], str]
    # New entries go first (dated sections, newest first) or last.
    insert: Literal["prepend", "append"] = "prepend"
    # Case-insensitive uniqueness on this field (e.g. skill name).
    unique_field: str | None = None
    # Hint for generic UI: how to label an entry in lists.
    primary_field: str | None = None


def _join(a: str, sep: str, b: str | None) -> str:
    return f"{a}{sep}{b}" if b else a


SECTIONS: dict[str, SectionDef] = {
    d.key: d
    for d in (
        SectionDef(
            "experience",
            "Experience",
            WorkExperience,
            lambda e: f"{e.title} at {e.company}",
            primary_field="title",
        ),
        SectionDef(
            "education",
            "Education",
            Education,
            lambda e: f"{e.degree} from {e.institution}",
            primary_field="institution",
        ),
        SectionDef(
            "skills",
            "Skills",
            Skill,
            lambda e: f"{e.name} ({e.category})",
            insert="append",
            unique_field="name",
            primary_field="name",
        ),
        SectionDef(
            "projects",
            "Projects",
            Project,
            lambda e: e.name,
            primary_field="name",
        ),
        SectionDef(
            "certifications",
            "Certifications & Licenses",
            Certification,
            lambda e: _join(e.name, " from ", e.issuer),
            primary_field="name",
        ),
        SectionDef(
            "awards",
            "Awards",
            Award,
            lambda e: e.title,
            primary_field="title",
        ),
        SectionDef(
            "publications",
            "Publications & Talks",
            Publication,
            lambda e: e.title,
            primary_field="title",
        ),
        SectionDef(
            "volunteer",
            "Volunteer",
            Volunteer,
            lambda e: f"{e.role} at {e.organization}",
            primary_field="role",
        ),
        SectionDef(
            "languages",
            "Languages",
            Language,
            lambda e: _join(e.language, " — ", e.proficiency),
            insert="append",
            unique_field="language",
            primary_field="language",
        ),
    )
}

# Entries of user-defined sections (``custom:<id>``) all share this definition.
CUSTOM_DEF = SectionDef(
    "custom",
    "Custom",
    CustomEntry,
    lambda e: e.heading or (e.body or "entry")[:40],
    insert="append",
    primary_field="heading",
)

LIST_SECTIONS: tuple[str, ...] = tuple(SECTIONS)
# Singleton sections are edited in place rather than as entry lists.
SECTION_UPDATE: tuple[str, ...] = ("contact", "summary")
ALL_SECTIONS: tuple[str, ...] = (*SECTION_UPDATE, *LIST_SECTIONS)

# Fail at import if the registry drifts from the model / layout order.
if LIST_SECTIONS != LIST_ORDER:
    raise RuntimeError("resume_layout.LIST_ORDER is out of sync with SECTIONS")
if not all(k in Resume.model_fields for k in ALL_SECTIONS):
    raise RuntimeError("Resume model is missing a registered section field")


def is_custom(section: str) -> bool:
    return section.startswith(CUSTOM_PREFIX)


def section_def(section: str) -> SectionDef:
    """Definition for a list section key (built-in or ``custom:<id>``)."""
    if is_custom(section):
        return CUSTOM_DEF
    d = SECTIONS.get(section)
    if d is None:
        raise ValueError(
            f"Invalid section: '{section}'. "
            f"Must be one of: {', '.join(LIST_SECTIONS)} or custom:<id>"
        )
    return d


# --- Field descriptors for generic UIs ---------------------------------------

_TEXTAREA = {"description", "body"}


@dataclass(frozen=True)
class FieldDef:
    name: str
    label: str
    widget: str  # text | textarea | url | bullets | tags
    required: bool


def _widget(name: str) -> str:
    if name == "highlights":
        return "bullets"
    if name == "tech":
        return "tags"
    if name == "url":
        return "url"
    if name in _TEXTAREA:
        return "textarea"
    return "text"


def fields_for(model: type[BaseModel]) -> list[FieldDef]:
    return [
        FieldDef(
            name=name,
            label=name.replace("_", " ").capitalize(),
            widget=_widget(name),
            required=info.is_required(),
        )
        for name, info in model.model_fields.items()
        if name != "id"
    ]


def describe_sections() -> list[dict[str, Any]]:
    """Registry metadata served to the frontend."""
    out: list[dict[str, Any]] = []
    for d in (*(SECTIONS[k] for k in LIST_SECTIONS), CUSTOM_DEF):
        out.append(
            {
                "key": d.key,
                "label": d.label,
                "primary_field": d.primary_field,
                "unique_field": d.unique_field,
                "insert": d.insert,
                "fields": [f.__dict__ for f in fields_for(d.model)],
            }
        )
    return out


__all__ = [
    "ALL_SECTIONS",
    "CUSTOM_DEF",
    "LIST_SECTIONS",
    "SECTIONS",
    "SECTION_UPDATE",
    "SectionDef",
    "describe_sections",
    "is_custom",
    "section_def",
]
