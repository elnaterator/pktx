"""Render a JSON Resume document as a PDF.

The document is flattened in Python into a small layout payload (formatted
dates, ready-made headings, empty sections dropped) and handed to a vendored
Typst template through ``sys.inputs``. User text is only ever data the template
reads with ``json()``; it is never spliced into Typst source, so markup
characters print literally.
"""

import json
import re
import unicodedata
from collections.abc import Callable, Iterable
from functools import cache
from importlib.resources import files
from typing import Any

import typst

from pktx.json_resume import (
    Award,
    Certificate,
    Education,
    Interest,
    Language,
    Project,
    Publication,
    Reference,
    Resume,
    Skill,
    Volunteer,
    Work,
    validate,
)
from pktx.resume_sections import SECTIONS

_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
_LETTER_COUNTRIES = {"US", "CA"}


@cache
def _template() -> bytes:
    return files("pktx").joinpath("templates/resume.typ").read_bytes()


def format_date(value: str | None) -> str | None:
    """``2021`` -> ``2021``; ``2021-03`` and ``2021-03-14`` -> ``Mar 2021``."""
    if not value:
        return None
    year, _, rest = value.partition("-")
    if not rest:
        return year
    return f"{_MONTHS[int(rest[:2]) - 1]} {year}"


def date_range(start: str | None, end: str | None) -> str | None:
    """A period; a start without an end is ongoing ("Present")."""
    if start:
        return f"{format_date(start)} – {format_date(end) or 'Present'}"
    return format_date(end)


def paper_for(country_code: str | None) -> str:
    return "us-letter" if (country_code or "").upper() in _LETTER_COUNTRIES else "a4"


def _slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def pdf_filename(name: str | None, label: str | None, version_id: int) -> str:
    """``Jane Doe`` + ``Backend`` -> ``jane-doe-backend.pdf`` (ASCII only)."""
    slug = _slug(" ".join(p for p in (name, label) if p))
    return f"{slug or f'resume-{version_id}'}.pdf"


def _join(parts: Iterable[str | None], sep: str = ", ") -> str | None:
    return sep.join(p for p in parts if p) or None


def _entry(
    heading: str | None,
    *,
    url: str | None = None,
    aside: str | None = None,
    sub: str | None = None,
    sub_aside: str | None = None,
    text: str | None = None,
    bullets: list[str] | None = None,
    tags: str | None = None,
) -> dict[str, Any]:
    """One block entry: bold heading + right-aligned aside, an italic sub line,
    then a paragraph, bullets and a tag line. Every key is always present."""
    return {
        "heading": heading,
        "url": url,
        "aside": aside,
        "sub": sub,
        "subAside": sub_aside,
        "text": text,
        "bullets": bullets or [],
        "tags": tags,
    }


def _row(label: str | None, value: str | None) -> dict[str, Any]:
    return {"label": label, "value": value}


def _work(e: Work) -> dict[str, Any]:
    return _entry(
        e.position or e.name,
        aside=date_range(e.start_date, e.end_date),
        sub=e.name if e.position else None,
        sub_aside=e.location,
        url=e.url,
        text=_join((e.description, e.summary), "\n"),
        bullets=e.highlights,
    )


def _volunteer(e: Volunteer) -> dict[str, Any]:
    return _entry(
        e.position or e.organization,
        aside=date_range(e.start_date, e.end_date),
        sub=e.organization if e.position else None,
        url=e.url,
        text=e.summary,
        bullets=e.highlights,
    )


def _education(e: Education) -> dict[str, Any]:
    return _entry(
        e.institution,
        url=e.url,
        aside=date_range(e.start_date, e.end_date),
        sub=_join((e.study_type, e.area), " in "),
        sub_aside=e.score,
        tags=f"Courses: {courses}" if (courses := _join(e.courses)) else None,
    )


def _project(e: Project) -> dict[str, Any]:
    return _entry(
        e.name,
        url=e.url,
        aside=date_range(e.start_date, e.end_date),
        sub=_join((_join(e.roles), e.entity, e.type), " · "),
        text=e.description,
        bullets=e.highlights,
        tags=_join(e.keywords),
    )


def _certificate(e: Certificate) -> dict[str, Any]:
    return _entry(e.name, url=e.url, aside=format_date(e.date), sub=e.issuer)


def _award(e: Award) -> dict[str, Any]:
    return _entry(e.title, aside=format_date(e.date), sub=e.awarder, text=e.summary)


def _publication(e: Publication) -> dict[str, Any]:
    return _entry(
        e.name,
        url=e.url,
        aside=format_date(e.release_date),
        sub=e.publisher,
        text=e.summary,
    )


def _reference(e: Reference) -> dict[str, Any]:
    return _entry(e.name, text=e.reference)


def _skill(e: Skill) -> dict[str, Any]:
    level = f"({e.level})" if e.level else None
    return _row(_join((e.name, level), " "), _join(e.keywords))


def _language(e: Language) -> dict[str, Any]:
    return _row(e.language, e.fluency)


def _interest(e: Interest) -> dict[str, Any]:
    return _row(e.name, _join(e.keywords))


# section key -> (layout, entry builder). "rows" is a compact label/value table.
_LAYOUTS: dict[str, tuple[str, Callable[[Any], dict[str, Any]]]] = {
    "work": ("entries", _work),
    "education": ("entries", _education),
    "skills": ("rows", _skill),
    "projects": ("entries", _project),
    "certificates": ("entries", _certificate),
    "awards": ("entries", _award),
    "publications": ("entries", _publication),
    "volunteer": ("entries", _volunteer),
    "languages": ("rows", _language),
    "interests": ("rows", _interest),
    "references": ("entries", _reference),
}

# Fail at import if a section has no PDF layout.
if set(_LAYOUTS) != set(SECTIONS):
    raise RuntimeError("pdf_service._LAYOUTS is out of sync with SECTIONS")


def build_payload(doc: dict[str, Any]) -> dict[str, Any]:
    """The template's input: basics plus non-empty sections in registry order."""
    resume: Resume = validate(Resume, doc)
    b = resume.basics
    loc = b.location
    contact = [
        {"text": b.email, "url": f"mailto:{b.email}" if b.email else None},
        {"text": b.phone, "url": None},
        {
            "text": _join((loc.city, loc.region, loc.country_code)) if loc else None,
            "url": None,
        },
        {"text": b.url, "url": b.url},
        *(
            {"text": _join((p.network, p.username), ": ") or p.url, "url": p.url}
            for p in b.profiles
        ),
    ]
    sections = []
    for key, d in SECTIONS.items():
        layout, build = _LAYOUTS[key]
        items = [build(e) for e in getattr(resume, key)]
        if items:
            sections.append({"title": d.label, "layout": layout, "items": items})
    return {
        "paper": paper_for(loc.country_code if loc else None),
        "name": b.name,
        "label": b.label,
        "contact": [c for c in contact if c["text"]],
        "summary": b.summary,
        "sections": sections,
    }


def render_resume_pdf(doc: dict[str, Any]) -> bytes:
    """Compile a JSON Resume document to PDF bytes (system fonts ignored, so
    the output is the same on every host)."""
    payload = json.dumps(build_payload(doc), ensure_ascii=False)
    pdf = typst.compile(
        _template(), sys_inputs={"resume": payload}, ignore_system_fonts=True
    )
    return bytes(pdf)  # pyright: ignore[reportArgumentType]
