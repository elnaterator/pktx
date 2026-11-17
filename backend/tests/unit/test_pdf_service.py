"""PDF rendering: layout payloads, formatting helpers and the compiled PDFs."""

import datetime
import io
from typing import Any

import pytest
from pypdf import PdfReader

from pktx.pdf_service import (
    PDF_THEMES,
    build_note_payload,
    build_payload,
    date_range,
    display_url,
    format_date,
    format_long_date,
    format_phone,
    note_pdf_filename,
    paper_for,
    pdf_filename,
    render_note_pdf,
    render_resume_pdf,
)
from pktx.resume_sections import SECTIONS

# One entry per section, each carrying a unique marker word.
_FULL: dict[str, Any] = {
    "basics": {
        "name": "Jane Doe",
        "label": "Staff Engineer",
        "email": "jane@example.com",
        "summary": "Summarymarker text.",
        "location": {"city": "Austin", "countryCode": "US"},
        "profiles": [
            {"network": "GitHub", "username": "jdoe", "url": "https://github.com/jdoe"}
        ],
    },
    "work": [{"name": "Workmarker", "position": "Engineer", "startDate": "2021-03"}],
    "education": [{"institution": "Educationmarker", "studyType": "BS"}],
    "skills": [{"name": "Skillmarker", "keywords": ["Python"]}],
    "projects": [{"name": "Projectmarker"}],
    "certificates": [{"name": "Certmarker"}],
    "awards": [{"title": "Awardmarker"}],
    "publications": [{"name": "Pubmarker"}],
    "volunteer": [{"organization": "Volmarker"}],
    "languages": [{"language": "Langmarker"}],
    "interests": [{"name": "Interestmarker"}],
    "references": [{"name": "Refmarker"}],
}


def _text(pdf: bytes) -> str:
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("2021", "2021"),
        ("2021-03", "Mar 2021"),
        ("2021-12-31", "Dec 2021"),
    ],
)
def test_format_date(value: str | None, expected: str | None) -> None:
    assert format_date(value) == expected


def test_date_range() -> None:
    assert date_range("2020-01", "2021") == "Jan 2020 – 2021"
    assert date_range("2020-01", None) == "Jan 2020 – Present"
    assert date_range(None, "2021-06") == "Jun 2021"
    assert date_range(None, None) is None


@pytest.mark.parametrize(
    ("code", "paper"),
    [("US", "us-letter"), ("ca", "us-letter"), ("DE", "a4"), (None, "a4")],
)
def test_paper_for(code: str | None, paper: str) -> None:
    assert paper_for(code) == paper


def test_pdf_filename() -> None:
    assert (
        pdf_filename("Jane Doe", "Backend / Platform", 3)
        == "jane-doe-backend-platform.pdf"
    )
    assert pdf_filename("Zoë Ñúñez", None, 3) == "zoe-nunez.pdf"
    assert pdf_filename(None, "日本語", 7) == "resume-7.pdf"
    assert pdf_filename('a"b\r\nc', None, 1) == "a-b-c.pdf"


def test_payload_sections_follow_registry_and_drop_empty() -> None:
    payload = build_payload({**_FULL, "awards": [], "interests": []})
    titles = [s["title"] for s in payload["sections"]]
    expected = [
        d.label for k, d in SECTIONS.items() if k not in ("awards", "interests")
    ]
    assert titles == expected
    assert payload["paper"] == "us-letter"
    # Reach line, then online line; profile shown by its short URL.
    assert [[c["text"] for c in g] for g in payload["contact"]] == [
        ["jane@example.com", "Austin, US"],
        ["github.com/jdoe"],
    ]


def test_payload_work_entry_shape() -> None:
    doc = {
        "work": [
            {
                "name": "Acme",
                "position": "Eng",
                "startDate": "2021",
                "highlights": ["a"],
            }
        ]
    }
    (entry,) = build_payload(doc)["sections"][0]["items"]
    assert entry["heading"] == "Eng" and entry["sub"] == "Acme"
    assert entry["aside"] == "2021 – Present" and entry["bullets"] == ["a"]


def test_renders_every_section_in_order() -> None:
    text = _text(render_resume_pdf(_FULL))
    markers = [
        e.get("name") or e.get("title") or e.get("institution")
        or e.get("organization") or e.get("language")
        for key in SECTIONS for e in _FULL[key]
    ]  # fmt: skip
    positions = [text.index(m) for m in markers]
    assert positions == sorted(positions)
    assert "Jane Doe" in text and "Summarymarker" in text


def test_empty_sections_hidden() -> None:
    text = _text(render_resume_pdf({"basics": {"name": "Jane"}, "work": []}))
    assert "Jane" in text
    assert "EXPERIENCE" not in text and "SUMMARY" not in text


def test_entry_order_kept() -> None:
    doc = {"work": [{"name": "Zeta"}, {"name": "Alpha"}, {"name": "Mid"}]}
    text = _text(render_resume_pdf(doc))
    assert text.index("Zeta") < text.index("Alpha") < text.index("Mid")


def test_empty_document_renders() -> None:
    assert render_resume_pdf({}).startswith(b"%PDF-")


def test_typst_markup_is_literal() -> None:
    hostile = '#eval("1+1") *b* _i_ $x$ [y] @ref <lbl> \\ `code` = H'
    text = _text(render_resume_pdf({"basics": {"name": hostile, "summary": hostile}}))
    for token in ('#eval("1+1")', "*b*", "$x$", "[y]", "@ref", "<lbl>", "`code`"):
        assert token in text


def test_invalid_document_rejected() -> None:
    with pytest.raises(ValueError):
        build_payload({"work": [{"startDate": "March"}]})


@pytest.mark.parametrize(
    ("code", "size"), [("US", (612, 792)), ("DE", (595, 842)), (None, (595, 842))]
)
def test_page_size_in_pdf(code: str | None, size: tuple[int, int]) -> None:
    doc = {"basics": {"location": {"countryCode": code}} if code else {}}
    box = PdfReader(io.BytesIO(render_resume_pdf(doc))).pages[0].mediabox
    assert (round(box.width), round(box.height)) == size


def test_display_url() -> None:
    assert display_url("https://www.example.com/me/") == "example.com/me"
    assert display_url("http://linkedin.com/in/x") == "linkedin.com/in/x"


@pytest.mark.parametrize(
    ("phone", "country", "expected"),
    [
        ("3605550100", "US", "(360) 555-0100"),
        ("3605550100", None, "3605550100"),
        ("+1 360 555 0100", "US", "+1 360 555 0100"),
        (None, "US", None),
    ],
)
def test_format_phone(phone: str | None, country: str | None, expected: str) -> None:
    assert format_phone(phone, country) == expected


def test_contact_groups_drop_empty_lines() -> None:
    payload = build_payload({"basics": {"email": "a@b.co"}})
    assert payload["contact"] == [[{"text": "a@b.co", "url": "mailto:a@b.co"}]]
    assert build_payload({})["contact"] == []


@pytest.mark.parametrize("theme", PDF_THEMES)
def test_every_theme_renders_everything(theme: str) -> None:
    text = _text(render_resume_pdf(_FULL, theme))  # type: ignore[arg-type]
    assert "Jane Doe" in text and "Refmarker" in text


def test_unknown_theme_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown theme"):
        build_payload({}, "fancy")  # type: ignore[arg-type]


def test_multi_page_footer_only_when_needed() -> None:
    one = _text(render_resume_pdf({"basics": {"name": "Jane"}}))
    assert "of 1" not in one
    long = {"basics": {"name": "Jane"}, "work": [{"name": f"Co{i}"} for i in range(80)]}
    pages = PdfReader(io.BytesIO(render_resume_pdf(long))).pages
    assert len(pages) > 1
    footer = " ".join(pages[1].extract_text().split())
    assert f"Jane · 2 of {len(pages)}" in footer


def test_modern_is_the_default_and_listed_first() -> None:
    assert build_payload({})["theme"] == "modern" == PDF_THEMES[0]


def test_employer_flag_only_for_role_at_employer() -> None:
    doc = {
        "work": [{"name": "Acme", "position": "Eng"}, {"name": "Solo"}],
        "volunteer": [{"organization": "Club", "position": "Mentor"}],
        "education": [{"institution": "Uni", "studyType": "BS"}],
    }
    flags = {
        s["title"]: [e["employer"] for e in s["items"]]
        for s in build_payload(doc)["sections"]
    }
    assert flags == {
        "Experience": [True, False],
        "Volunteer": [True],
        "Education": [False],
    }


def test_jakes_puts_employer_row_first() -> None:
    doc = {"work": [{"name": "Acme", "position": "Engineer", "startDate": "2020"}]}
    text = _text(render_resume_pdf(doc, "jakes"))
    assert text.index("Acme") < text.index("Engineer")
    text = _text(render_resume_pdf(doc, "modern"))
    assert text.index("Engineer") < text.index("Acme")


# ── Notes as letters ──────────────────────────────────────────────────────────

_DAY = datetime.date(2026, 11, 5)
_LETTER = """Dear Hiring Manager,

A **Boldmarker** and *Italicmarker* with `Codemarker` and [Linkmarker](https://example.com).

# Headingone
## Headingtwo
##### Headingdeep

- Bulletmarker
  - Nestedmarker

3. Orderedmarker

> Quotemarker

```
Fencemarker
```

---

Sincerely,\\
Jane
"""
_LETTER_MARKERS = (
    "Dear Hiring Manager,",
    "Boldmarker",
    "Italicmarker",
    "Codemarker",
    "Linkmarker",
    "Headingone",
    "Headingtwo",
    "Headingdeep",
    "Bulletmarker",
    "Nestedmarker",
    "Orderedmarker",
    "Quotemarker",
    "Fencemarker",
    "Sincerely,",
)


def test_format_long_date() -> None:
    assert format_long_date(_DAY) == "November 5, 2026"


def test_note_filename() -> None:
    assert (
        note_pdf_filename("Jané Doe", "Cover letter: Acme", 7)
        == "jane-doe-cover-letter-acme.pdf"
    )
    assert note_pdf_filename(None, "Cover letter", 7) == "cover-letter.pdf"
    assert note_pdf_filename(None, "日本", 7) == "note-7.pdf"


def test_note_payload_shares_the_resume_header() -> None:
    resume, note = build_payload(_FULL), build_note_payload("Hi", _FULL, on=_DAY)
    for key in ("theme", "paper", "name", "label", "contact"):
        assert note[key] == resume[key]
    assert note["date"] == "November 5, 2026"
    assert note["blocks"] == [
        {"type": "paragraph", "inlines": [{"type": "text", "text": "Hi"}]}
    ]


@pytest.mark.parametrize("theme", PDF_THEMES)
def test_letter_renders_every_construct_in_every_theme(theme: str) -> None:
    text = _text(render_note_pdf(_LETTER, _FULL, theme, _DAY))  # type: ignore[arg-type]
    for marker in (
        "Jane Doe",
        "jane@example.com",
        "November 5, 2026",
        *_LETTER_MARKERS,
    ):
        assert marker in text, marker
    assert "3." in text  # ordered lists keep their start
    assert "**" not in text and "```" not in text and "##" not in text


@pytest.mark.parametrize("theme", PDF_THEMES)
def test_letter_without_resume_has_no_header(theme: str) -> None:
    pdf = render_note_pdf("Bodymarker", None, theme, _DAY)  # type: ignore[arg-type]
    assert _text(pdf).split() == ["November", "5,", "2026", "Bodymarker"]
    box = PdfReader(io.BytesIO(pdf)).pages[0].mediabox
    assert (round(box.width), round(box.height)) == (595, 842)  # A4


def test_empty_letter_is_header_and_date() -> None:
    text = _text(render_note_pdf("", _FULL, on=_DAY))
    assert "Jane Doe" in text and "November 5, 2026" in text


def test_letter_text_is_data_not_markup() -> None:
    hostile = (
        '#import "x" $1+1$ @ref <label> [box] \\ #panic()\n\n'
        "<script>alert(1)</script>\n\n"
        "[bad](javascript:alert(1)) `#raw`"
    )
    text = _text(render_note_pdf(hostile, _FULL, on=_DAY))
    for literal in ("#import", "$1+1$", "@ref", "<label>", "[box]", "#panic()"):
        assert literal in text, literal
    assert "<script>alert(1)</script>" in text
    assert "#raw" in text


def test_letter_unknown_theme_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown theme"):
        render_note_pdf("x", _FULL, "fancy")  # type: ignore[arg-type]


def test_letter_date_defaults_to_today() -> None:
    today = datetime.datetime.now(datetime.UTC).date()
    assert build_note_payload("x", None)["date"] == format_long_date(today)
