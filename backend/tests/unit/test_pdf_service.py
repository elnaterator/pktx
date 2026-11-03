"""Resume PDF rendering: layout payload, formatting helpers and the compiled PDF."""

import io
from typing import Any

import pytest
from pypdf import PdfReader

from pktx.pdf_service import (
    build_payload,
    date_range,
    format_date,
    paper_for,
    pdf_filename,
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
    assert [c["text"] for c in payload["contact"]] == [
        "jane@example.com",
        "Austin, US",
        "GitHub: jdoe",
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
