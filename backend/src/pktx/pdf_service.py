"""Render a JSON Resume document, or a note as a letter, to PDF.

The source is flattened in Python into a small layout payload (formatted
dates, ready-made headings, empty sections dropped, markdown as a block tree)
and handed to a vendored Typst template through ``sys.inputs``. User text is
only ever data the template reads with ``json()``; it is never spliced into
Typst source, so markup characters print literally.
"""

import datetime
import json
import re
import unicodedata
from collections.abc import Callable, Iterable
from functools import cache
from importlib.resources import as_file, files
from typing import Any, Literal, get_args

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
from pktx.markdown_blocks import parse_markdown
from pktx.resume_sections import SECTIONS

# Listed in picker order; the first is the default.
PdfTheme = Literal["modern", "compact", "classic", "jakes", "executive", "minimal"]
PDF_THEMES: tuple[str, ...] = get_args(PdfTheme)
DEFAULT_PDF_THEME: PdfTheme = "modern"

_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
_MONTH_NAMES = (
    "January February March April May June July August September October "
    "November December"
).split()
_LETTER_COUNTRIES = {"US", "CA"}
_PKG = files("pktx")


_TEMPLATES = _PKG.joinpath("templates")


@cache
def _fonts() -> typst.Fonts:
    """Typst's embedded fonts plus the bundled ones; system fonts never, so the
    output is the same on every host. Scanned once per process."""
    return typst.Fonts(
        include_system_fonts=False, font_paths=[str(_PKG.joinpath("fonts"))]
    )


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


def display_url(url: str) -> str:
    """``https://www.example.com/me/`` -> ``example.com/me``."""
    return re.sub(r"^https?://(www\.)?", "", url).rstrip("/")


def format_phone(phone: str | None, country_code: str | None) -> str | None:
    """Bare 10-digit North American numbers -> ``(360) 555-0100``; else as typed."""
    if (
        phone
        and phone.isdigit()
        and len(phone) == 10
        and paper_for(country_code) == "us-letter"
    ):
        return f"({phone[:3]}) {phone[3:6]}-{phone[6:]}"
    return phone


def _link(text: str | None, url: str | None = None) -> dict[str, str | None]:
    return {"text": text, "url": url}


def _slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def _filename(parts: Iterable[str | None], fallback: str) -> str:
    return f"{_slug(' '.join(p for p in parts if p)) or fallback}.pdf"


def pdf_filename(name: str | None, label: str | None, version_id: int) -> str:
    """``Jane Doe`` + ``Backend`` -> ``jane-doe-backend.pdf`` (ASCII only)."""
    return _filename((name, label), f"resume-{version_id}")


def note_pdf_filename(name: str | None, title: str | None, note_id: int) -> str:
    """``Jane Doe`` + ``Cover letter: Acme`` -> ``jane-doe-cover-letter-acme.pdf``."""
    return _filename((name, title), f"note-{note_id}")


def format_long_date(on: datetime.date) -> str:
    """``2026-11-05`` -> ``November 5, 2026`` (locale-independent)."""
    return f"{_MONTH_NAMES[on.month - 1]} {on.day}, {on.year}"


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
    employer: bool = False,
) -> dict[str, Any]:
    """One block entry: bold heading + right-aligned aside, an italic sub line,
    then a paragraph, bullets and a tag line. Every key is always present.

    ``employer`` marks a role (heading) at an employer (sub); employer-first
    themes swap the two rows."""
    return {
        "heading": heading,
        "url": url,
        "aside": aside,
        "sub": sub,
        "subAside": sub_aside,
        "text": text,
        "bullets": bullets or [],
        "tags": tags,
        "employer": employer,
    }


def _row(label: str | None, value: str | None) -> dict[str, Any]:
    return {"label": label, "value": value}


def _work(e: Work) -> dict[str, Any]:
    return _entry(
        e.position or e.name,
        aside=date_range(e.start_date, e.end_date),
        sub=e.name if e.position else None,
        sub_aside=e.location,
        employer=bool(e.position and e.name),
        url=e.url,
        text=_join((e.description, e.summary), "\n"),
        bullets=e.highlights,
    )


def _volunteer(e: Volunteer) -> dict[str, Any]:
    return _entry(
        e.position or e.organization,
        aside=date_range(e.start_date, e.end_date),
        sub=e.organization if e.position else None,
        employer=bool(e.position and e.organization),
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


def _check_theme(theme: str) -> None:
    if theme not in PDF_THEMES:
        raise ValueError(
            f"Unknown theme '{theme}'. Must be one of: {', '.join(PDF_THEMES)}"
        )


def _header(resume: Resume, theme: PdfTheme) -> dict[str, Any]:
    """What every document opens with: theme, paper, name, label, contact."""
    _check_theme(theme)
    b = resume.basics
    loc = b.location
    country = loc.country_code if loc else None
    # Two short lines: how to reach you, then where to find you online.
    reach = [
        _link(b.email, f"mailto:{b.email}" if b.email else None),
        _link(format_phone(b.phone, country)),
        _link(_join((loc.city, loc.region or loc.country_code)) if loc else None),
    ]
    online = [_link(display_url(u), u) for u in (b.url,) if u] + [
        _link(display_url(p.url), p.url)
        if p.url
        else _link(_join((p.network, p.username), ": "))
        for p in b.profiles
    ]
    groups = ([c for c in g if c["text"]] for g in (reach, online))
    return {
        "theme": theme,
        "paper": paper_for(country),
        "name": b.name,
        "label": b.label,
        "contact": [g for g in groups if g],
    }


def build_payload(
    doc: dict[str, Any], theme: PdfTheme = DEFAULT_PDF_THEME
) -> dict[str, Any]:
    """The resume template's input: header plus non-empty sections in registry order."""
    resume: Resume = validate(Resume, doc)
    sections = []
    for key, d in SECTIONS.items():
        layout, build = _LAYOUTS[key]
        items = [build(e) for e in getattr(resume, key)]
        if items:
            sections.append({"title": d.label, "layout": layout, "items": items})
    return {
        **_header(resume, theme),
        "summary": resume.basics.summary,
        "sections": sections,
    }


def build_note_payload(
    content: str,
    resume_doc: dict[str, Any] | None,
    theme: PdfTheme = DEFAULT_PDF_THEME,
    on: datetime.date | None = None,
) -> dict[str, Any]:
    """The letter template's input: the resume's header (blank without a
    resume), the date, and the note's markdown as a block tree."""
    resume: Resume = validate(Resume, resume_doc or {})
    on = on or datetime.datetime.now(datetime.UTC).date()
    return {
        **_header(resume, theme),
        "date": format_long_date(on),
        "blocks": parse_markdown(content),
    }


def _compile(template: str, payload: dict[str, Any]) -> bytes:
    # Compiled from the templates directory so a template can import its
    # siblings (theme.typ).
    with as_file(_TEMPLATES) as root:
        pdf = typst.compile(
            root / template,
            root=root,
            sys_inputs={"data": json.dumps(payload, ensure_ascii=False)},
            font_paths=_fonts(),
        )
    return bytes(pdf)  # pyright: ignore[reportArgumentType]


def render_resume_pdf(
    doc: dict[str, Any], theme: PdfTheme = DEFAULT_PDF_THEME
) -> bytes:
    """Compile a JSON Resume document to PDF bytes."""
    return _compile("resume.typ", build_payload(doc, theme))


def render_note_pdf(
    content: str,
    resume_doc: dict[str, Any] | None,
    theme: PdfTheme = DEFAULT_PDF_THEME,
    on: datetime.date | None = None,
) -> bytes:
    """Compile a note's markdown to a letter: ``resume_doc``'s header, the date
    (``on``, default today in UTC), then the body."""
    return _compile("letter.typ", build_note_payload(content, resume_doc, theme, on))
