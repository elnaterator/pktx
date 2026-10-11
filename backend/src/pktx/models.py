"""Pydantic models for pktx resume data."""

import re
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

from pktx.contact_keys import canonical_key, key_kind
from pktx.validation import (
    MAX_NAME,
    MAX_SHORT,
    check_len,
    validate_http_url,
)

RESOURCE_TYPES_LITERAL = Literal[
    "application", "accomplishment", "resume", "note", "contact"
]


class ResourceRef(BaseModel):
    """A reference to any linkable resource."""

    type: RESOURCE_TYPES_LITERAL
    id: int
    name: str
    updated_at: str | None = None


GroupedLinks = dict[str, list[ResourceRef]]


_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_CONTACT_FIELDS = 30

# Pre-key/value contact shape: top-level email/website/... and a profiles list.
LEGACY_CONTACT_KEYS = {
    "email": "Email",
    "website": "Website",
    "linkedin": "LinkedIn",
    "github": "GitHub",
}


class ContactField(BaseModel):
    """One contact detail: a key (preset or custom) and its value."""

    key: str
    value: str

    @field_validator("key", mode="before")
    @classmethod
    def clean_key(cls, v: object) -> str:
        if not isinstance(v, str) or not canonical_key(v):
            raise ValueError("Contact key must not be empty")
        key = canonical_key(v)
        if len(key) > MAX_NAME:
            raise ValueError(f"Contact key must not exceed {MAX_NAME} characters")
        return key

    @model_validator(mode="after")
    def check_value(self) -> "ContactField":
        value = self.value.strip() if isinstance(self.value, str) else ""
        if not value:
            raise ValueError(f"{self.key} must not be empty")
        kind = key_kind(self.key)
        if kind == "url":
            value = validate_http_url(value, self.key) or value
        elif kind == "email":
            if not _EMAIL.match(value):
                raise ValueError(f"{self.key} must be a valid email address")
        check_len(self.key, value, MAX_SHORT)
        self.value = value
        return self


class ContactInfo(BaseModel):
    """Name, phone and location plus any number of key/value details."""

    name: str | None = None
    phone: str | None = None
    location: str | None = None
    fields: list[ContactField] = []

    @model_validator(mode="before")
    @classmethod
    def upgrade_legacy(cls, data: object) -> object:
        """Accept the old shape (email/website/linkedin/github, profiles).

        Legacy keys upsert into ``fields`` (an empty value removes the field), so
        unmigrated blobs and old API/MCP clients keep working.
        """
        if not isinstance(data, dict):
            return data
        data = dict(data)
        fields = [
            dict(f) if isinstance(f, dict) else f for f in data.get("fields") or []
        ]

        def upsert(key: str, value: object) -> None:
            folded = canonical_key(key).lower()
            fields[:] = [
                f
                for f in fields
                if not (
                    isinstance(f, dict)
                    and canonical_key(str(f.get("key", ""))).lower() == folded
                )
            ]
            if isinstance(value, str) and value.strip():
                fields.append({"key": key, "value": value})
            elif value not in (None, ""):
                fields.append({"key": key, "value": value})

        legacy = False
        for old, label in LEGACY_CONTACT_KEYS.items():
            if old in data:
                legacy = True
                upsert(label, data.pop(old))
        if "profiles" in data:
            legacy = True
            for p in data.pop("profiles") or []:
                if isinstance(p, dict):
                    upsert(str(p.get("label", "")), p.get("url"))
        if legacy:
            data["fields"] = fields
        return data

    @model_validator(mode="after")
    def check_fields(self) -> "ContactInfo":
        if len(self.fields) > MAX_CONTACT_FIELDS:
            raise ValueError(f"At most {MAX_CONTACT_FIELDS} contact details allowed")
        seen: set[str] = set()
        for f in self.fields:
            if f.key.lower() in seen:
                raise ValueError(f"Duplicate contact key: '{f.key}'")
            seen.add(f.key.lower())
        return self


class Entry(BaseModel):
    """Base for list-section entries; ``id`` is assigned by the service."""

    id: str | None = None


class _UrlEntry(Entry):
    """Entry with an optional ``url`` restricted to http(s)."""

    @field_validator("url", mode="before", check_fields=False)
    @classmethod
    def http_url_only(cls, v: object) -> str | None:
        return validate_http_url(v)


class WorkExperience(Entry):
    """A single work experience entry."""

    title: str
    company: str
    start_date: str | None = None
    end_date: str | None = None
    location: str | None = None
    highlights: list[str] = []


class Education(Entry):
    """A single education entry."""

    institution: str
    degree: str
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    honors: str | None = None
    highlights: list[str] = []


class Skill(Entry):
    """A single skill with a name and optional category."""

    name: str
    category: str | None = "Other"

    @field_validator("category", mode="before")
    @classmethod
    def default_empty_category(cls, v: str | None) -> str:
        if not v:
            return "Other"
        return v


class Project(_UrlEntry):
    """A personal, open-source or side project."""

    name: str
    description: str | None = None
    url: str | None = None
    tech: list[str] = []
    start_date: str | None = None
    end_date: str | None = None
    highlights: list[str] = []


class Certification(_UrlEntry):
    """A certification or license."""

    name: str
    issuer: str | None = None
    issued: str | None = None
    expires: str | None = None
    credential_id: str | None = None
    url: str | None = None


class Award(Entry):
    """An award or honor."""

    title: str
    issuer: str | None = None
    date: str | None = None
    description: str | None = None


class Publication(_UrlEntry):
    """A publication, talk or patent."""

    title: str
    venue: str | None = None
    date: str | None = None
    url: str | None = None
    description: str | None = None


class Volunteer(Entry):
    """A volunteer or community role."""

    role: str
    organization: str
    start_date: str | None = None
    end_date: str | None = None
    location: str | None = None
    highlights: list[str] = []


class Language(Entry):
    """A spoken language with optional proficiency."""

    language: str
    proficiency: str | None = None


class Resume(BaseModel):
    """Aggregate resume model combining all sections."""

    contact: ContactInfo = ContactInfo()
    summary: str = ""
    experience: list[WorkExperience] = []
    education: list[Education] = []
    skills: list[Skill] = []
    projects: list[Project] = []
    certifications: list[Certification] = []
    awards: list[Award] = []
    publications: list[Publication] = []
    volunteer: list[Volunteer] = []
    languages: list[Language] = []
    # Optional sections the user added (shown in fixed order, see resume_order).
    enabled_sections: list[str] = []

    @model_validator(mode="after")
    def _normalize_enabled(self) -> "Resume":
        from pktx.resume_order import normalize_enabled

        self.enabled_sections = normalize_enabled(
            self.enabled_sections, self.model_dump(exclude={"enabled_sections"})
        )
        return self


class ResumeVersion(BaseModel):
    """A versioned resume with metadata."""

    id: int
    label: str
    is_default: bool = False
    resume_data: Resume = Resume()
    tags: list[str] = []
    created_at: str = ""
    updated_at: str = ""
    links: GroupedLinks = {}


class ResumeVersionSummary(BaseModel):
    """Resume version metadata for list views (no resume_data)."""

    id: int
    label: str
    is_default: bool = False
    app_count: int = 0
    tags: list[str] = []
    created_at: str = ""
    updated_at: str = ""
    link_count: int = 0


class SearchResult(BaseModel):
    """A unified search result across all resource types."""

    type: str
    id: int
    title: str
    subtitle: str | None = None
    snippet: str | None = None
    tags: list[str] = []
    url: str


APPLICATION_STATUSES = (
    "Interested",
    "Applied",
    "Phone Screen",
    "Interview",
    "Offer",
    "Accepted",
    "Rejected",
    "Withdrawn",
)

COMMUNICATION_TYPES = ("email", "phone", "interview_note", "other")
COMMUNICATION_DIRECTIONS = ("sent", "received")
COMMUNICATION_STATUSES = ("draft", "ready", "sent", "archived")


class Application(BaseModel):
    """A job application."""

    id: int
    company: str
    position: str
    description: str = ""
    status: str = "Interested"
    url: str | None = None
    notes: str = ""
    tags: list[str] = []
    created_at: str = ""
    updated_at: str = ""
    links: GroupedLinks = {}

    @field_validator("url", mode="before")
    @classmethod
    def http_url_only(cls, v: object) -> str | None:
        return validate_http_url(v, "url")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in APPLICATION_STATUSES:
            valid = ", ".join(APPLICATION_STATUSES)
            raise ValueError(f"Invalid status: '{v}'. Must be one of: {valid}")
        return v


class ApplicationSummary(BaseModel):
    """Application summary for list views (no description/notes)."""

    id: int
    company: str
    position: str
    status: str = "Interested"
    url: str | None = None
    tags: list[str] = []
    created_at: str = ""
    updated_at: str = ""
    link_count: int = 0


class Accomplishment(BaseModel):
    """A career accomplishment in STAR format."""

    id: int
    title: str
    situation: str = ""
    task: str = ""
    action: str = ""
    result: str = ""
    accomplishment_date: str | None = None
    tags: list[str] = []
    created_at: str = ""
    updated_at: str = ""
    links: GroupedLinks = {}


class AccomplishmentSummary(BaseModel):
    """Accomplishment summary for list views (STAR body omitted)."""

    id: int
    title: str
    accomplishment_date: str | None = None
    tags: list[str] = []
    created_at: str = ""
    updated_at: str = ""
    link_count: int = 0


class Note(BaseModel):
    """A personal context note."""

    id: int
    title: str
    content: str = ""
    tags: list[str] = []
    created_at: str = ""
    updated_at: str = ""
    links: GroupedLinks = {}


class NoteSummary(BaseModel):
    """Note summary for list views (content omitted)."""

    id: int
    title: str
    tags: list[str] = []
    created_at: str = ""
    updated_at: str = ""
    link_count: int = 0


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Contact(BaseModel):
    """A networking or relationship contact."""

    id: int
    name: str
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    title: str | None = None
    relationship: str | None = None
    linkedin_url: str | None = None
    location: str | None = None
    last_contacted_date: str | None = None
    followup_date: str | None = None
    notes: str = ""
    tags: list[str] = []
    created_at: str = ""
    updated_at: str = ""
    links: GroupedLinks = {}

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Name is required and must not be blank")
        if len(v.strip()) > 255:
            raise ValueError("Name must not exceed 255 characters")
        return v.strip()

    @field_validator("linkedin_url", mode="before")
    @classmethod
    def http_url_only(cls, v: object) -> str | None:
        return validate_http_url(v, "linkedin_url")

    @field_validator("last_contacted_date", "followup_date", mode="before")
    @classmethod
    def validate_date(cls, v: str | None) -> str | None:
        if v is not None and v != "" and not _ISO_DATE_RE.match(v):
            raise ValueError(f"Date must be in YYYY-MM-DD format, got: '{v}'")
        return v or None


class ContactSummary(BaseModel):
    """Contact summary for list views (notes omitted)."""

    id: int
    name: str
    company: str | None = None
    title: str | None = None
    relationship: str | None = None
    followup_date: str | None = None
    tags: list[str] = []
    updated_at: str = ""
    link_count: int = 0


class Communication(BaseModel):
    """A communication entry attached to a networking contact."""

    id: int
    contact_ref_id: int
    type: str
    direction: str
    subject: str = ""
    body: str
    date: str
    status: str = "sent"
    tags: list[str] = []
    created_at: str = ""

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in COMMUNICATION_TYPES:
            raise ValueError(
                f"Invalid type: '{v}'. Must be one of: {', '.join(COMMUNICATION_TYPES)}"
            )
        return v

    @field_validator("direction")
    @classmethod
    def validate_direction(cls, v: str) -> str:
        if v not in COMMUNICATION_DIRECTIONS:
            valid = ", ".join(COMMUNICATION_DIRECTIONS)
            raise ValueError(f"Invalid direction: '{v}'. Must be one of: {valid}")
        return v

    @field_validator("status")
    @classmethod
    def validate_comm_status(cls, v: str) -> str:
        if v not in COMMUNICATION_STATUSES:
            valid = ", ".join(COMMUNICATION_STATUSES)
            raise ValueError(f"Invalid status: '{v}'. Must be one of: {valid}")
        return v


class CommunicationSearchResult(BaseModel):
    """Communication with parent context for cross-resource search results."""

    id: int
    parent_type: str
    parent_id: int
    parent_name: str
    contact_ref_id: int
    type: str
    direction: str
    subject: str = ""
    body: str
    date: str
    status: str = "sent"
    tags: list[str] = []
    created_at: str = ""
