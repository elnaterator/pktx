"""Pydantic models for pktx resume data."""

import re
from typing import Literal

from pydantic import BaseModel, field_validator

from pktx.json_resume import Resume
from pktx.validation import (
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


class ResumeVersion(BaseModel):
    """A versioned resume with metadata."""

    id: int
    label: str
    is_default: bool = False
    data: Resume = Resume()
    tags: list[str] = []
    created_at: str = ""
    updated_at: str = ""
    links: GroupedLinks = {}


class ResumeVersionSummary(BaseModel):
    """Resume version metadata for list views (no document)."""

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
