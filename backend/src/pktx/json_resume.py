"""JSON Resume (jsonresume.org, schema v1.0.0) models.

A resume version stores one JSON Resume document. Names follow the spec
(camelCase on the wire, snake_case attributes in Python); the only extension is
a stable ``id`` on every list entry and profile. Every spec field is optional,
unknown keys are ignored, and blank strings are treated as absent.

Always serialize with :func:`dump` so the output is camelCase and compact
(unset fields and empty lists are omitted).
"""

import re
from datetime import date as _date
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)
from pydantic.alias_generators import to_camel
from pydantic.config import JsonDict

from pktx.validation import MAX_LONG, MAX_NAME, MAX_SHORT, validate_http_url

_MAX_BULLET = 2000
_MAX_ITEMS = 100  # per list: profiles, highlights, keywords, ...
_MAX_ENTRIES = 500  # entries per section
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PARTIAL_DATE = re.compile(r"^\d{4}(-(0[1-9]|1[0-2])(-\d{2})?)?$")


def _partial_date(v: str) -> str:
    """Accept ``YYYY``, ``YYYY-MM`` or ``YYYY-MM-DD`` (a real calendar day)."""
    if not _PARTIAL_DATE.match(v):
        raise ValueError("Date must be YYYY, YYYY-MM or YYYY-MM-DD")
    if len(v) == 10:
        try:
            _date.fromisoformat(v)
        except ValueError:
            raise ValueError("Date is not a valid calendar day") from None
    return v


def _email(v: str) -> str:
    if not _EMAIL.match(v):
        raise ValueError("Must be a valid email address")
    return v


def _http_url(v: Any) -> str | None:
    return validate_http_url(v)


Name = Annotated[str, StringConstraints(strip_whitespace=True, max_length=MAX_NAME)]
Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=MAX_SHORT)]
Long = Annotated[str, StringConstraints(strip_whitespace=True, max_length=MAX_LONG)]
Bullet = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=_MAX_BULLET)
]
Url = Annotated[str, BeforeValidator(_http_url)]
PartialDate = Annotated[str, AfterValidator(_partial_date)]
Email = Annotated[str, StringConstraints(max_length=MAX_SHORT), AfterValidator(_email)]


def _title(name: str, _info: Any) -> str:
    """Default UI label: ``start_date`` -> ``Start date``, ``url`` -> ``URL``."""
    return "URL" if name == "url" else name.replace("_", " ").capitalize()


def _field(widget: str | None = None, title: str | None = None) -> Any:
    """Optional field. ``widget`` (a UI hint) and ``title`` (the label) are
    exposed in the JSON Schema served to the frontend."""
    extra: JsonDict | None = {"widget": widget} if widget else None
    return Field(default=None, title=title, json_schema_extra=extra)


def _list_field(widget: str, title: str | None = None) -> Any:
    return Field(
        default_factory=list,
        title=title,
        max_length=_MAX_ITEMS,
        json_schema_extra={"widget": widget},
    )


class JRModel(BaseModel):
    """Base: camelCase aliases, snake_case input accepted, unknown keys ignored."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
        field_title_generator=_title,
    )

    @model_validator(mode="before")
    @classmethod
    def _blank_is_absent(cls, data: Any) -> Any:
        """Treat ``""`` as unset and drop blank list items (common in imports)."""
        if not isinstance(data, dict):
            return data
        clean: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, str):
                value = value.strip() or None
            elif isinstance(value, list) and all(isinstance(i, str) for i in value):
                value = [i.strip() for i in value if i.strip()]
            clean[key] = value
        return clean


class Entry(JRModel):
    """List entry; ``id`` is assigned by the service."""

    id: str | None = None


class Location(JRModel):
    address: Short | None = _field()
    postal_code: Name | None = _field()
    city: Name | None = _field()
    country_code: Name | None = _field()
    region: Name | None = _field()


class Profile(Entry):
    network: Name | None = _field()
    username: Name | None = _field()
    url: Url | None = _field("url")


class Basics(JRModel):
    name: Name | None = _field()
    label: Name | None = _field(title="Headline")
    image: Url | None = _field("url", title="Image URL")
    email: Email | None = _field("email")
    phone: Name | None = _field()
    url: Url | None = _field("url", title="Website")
    summary: Long | None = _field("textarea")
    location: Location | None = None
    profiles: list[Profile] = Field(default_factory=list, max_length=_MAX_ITEMS)


class Work(Entry):
    name: Name | None = _field(title="Company")
    location: Short | None = _field()
    description: Short | None = _field(title="Company description")
    position: Name | None = _field()
    url: Url | None = _field("url")
    start_date: PartialDate | None = _field("date")
    end_date: PartialDate | None = _field("date")
    summary: Long | None = _field("textarea")
    highlights: list[Bullet] = _list_field("bullets")


class Volunteer(Entry):
    organization: Name | None = _field()
    position: Name | None = _field()
    url: Url | None = _field("url")
    start_date: PartialDate | None = _field("date")
    end_date: PartialDate | None = _field("date")
    summary: Long | None = _field("textarea")
    highlights: list[Bullet] = _list_field("bullets")


class Education(Entry):
    institution: Name | None = _field()
    url: Url | None = _field("url")
    area: Name | None = _field(title="Field of study")
    study_type: Name | None = _field(title="Degree")
    start_date: PartialDate | None = _field("date")
    end_date: PartialDate | None = _field("date")
    score: Name | None = _field(title="Score / GPA")
    courses: list[Name] = _list_field("tags")


class Award(Entry):
    title: Name | None = _field()
    date: PartialDate | None = _field("date")
    awarder: Name | None = _field()
    summary: Long | None = _field("textarea")


class Certificate(Entry):
    name: Name | None = _field()
    date: PartialDate | None = _field("date")
    url: Url | None = _field("url")
    issuer: Name | None = _field()


class Publication(Entry):
    name: Name | None = _field(title="Title")
    publisher: Name | None = _field()
    release_date: PartialDate | None = _field("date", title="Release date")
    url: Url | None = _field("url")
    summary: Long | None = _field("textarea")


class Skill(Entry):
    name: Name | None = _field()
    level: Name | None = _field()
    keywords: list[Name] = _list_field("tags")


class Language(Entry):
    language: Name | None = _field()
    fluency: Name | None = _field()


class Interest(Entry):
    name: Name | None = _field()
    keywords: list[Name] = _list_field("tags")


class Reference(Entry):
    name: Name | None = _field()
    reference: Long | None = _field("textarea")


class Project(Entry):
    name: Name | None = _field()
    description: Long | None = _field("textarea")
    highlights: list[Bullet] = _list_field("bullets")
    keywords: list[Name] = _list_field("tags", title="Technologies")
    start_date: PartialDate | None = _field("date")
    end_date: PartialDate | None = _field("date")
    url: Url | None = _field("url")
    roles: list[Name] = _list_field("tags")
    entity: Name | None = _field(title="Organization")
    type: Name | None = _field()


class Meta(JRModel):
    canonical: Url | None = _field("url", title="Canonical URL")
    version: Name | None = _field()
    last_modified: Name | None = _field()


def _entries() -> Any:
    return Field(default_factory=list, max_length=_MAX_ENTRIES)


class Resume(JRModel):
    """A whole JSON Resume document."""

    basics: Basics = Field(default_factory=Basics)
    work: list[Work] = _entries()
    volunteer: list[Volunteer] = _entries()
    education: list[Education] = _entries()
    awards: list[Award] = _entries()
    certificates: list[Certificate] = _entries()
    publications: list[Publication] = _entries()
    skills: list[Skill] = _entries()
    languages: list[Language] = _entries()
    interests: list[Interest] = _entries()
    references: list[Reference] = _entries()
    projects: list[Project] = _entries()
    meta: Meta | None = None


def dump(model: BaseModel) -> dict[str, Any]:
    """Compact camelCase JSON: unset fields and empty lists are omitted."""
    return model.model_dump(mode="json", by_alias=True, exclude_defaults=True)


def alias_keys(model: type[BaseModel], data: dict[str, Any]) -> dict[str, Any]:
    """Rename snake_case keys to their camelCase alias.

    Lets a partial update merge into a stored (camelCase) entry without leaving
    both spellings of one field behind. Unknown keys raise ``ValueError``.
    """
    by_name = {n: f.alias or n for n, f in model.model_fields.items()}
    known = set(by_name.values())
    out: dict[str, Any] = {}
    for key, value in data.items():
        alias = by_name.get(key, key)
        if alias not in known:
            raise ValueError(
                f"Unknown field '{key}'. Valid fields: {', '.join(sorted(known))}"
            )
        out[alias] = value
    return out


def validate(model: type[BaseModel], data: Any) -> Any:
    """``model.model_validate`` raising a short ``ValueError`` (one line per issue)."""
    try:
        return model.model_validate(data)
    except ValidationError as e:
        issues = []
        for err in e.errors():
            where = ".".join(str(p) for p in err["loc"])
            msg = err["msg"].removeprefix("Value error, ")
            issues.append(f"{where}: {msg}" if where else msg)
        raise ValueError("; ".join(issues)) from None
