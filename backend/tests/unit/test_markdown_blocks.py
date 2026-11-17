"""Markdown -> block tree: every node type, nesting, and safe degradation."""

from typing import Any

import pytest

from pktx.markdown_blocks import parse_markdown


def _t(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


def _p(*inlines: dict[str, Any]) -> dict[str, Any]:
    return {"type": "paragraph", "inlines": list(inlines)}


@pytest.mark.parametrize("source", ["", "   ", "\n\n"])
def test_blank_is_empty(source: str) -> None:
    assert parse_markdown(source) == []


def test_paragraphs_and_soft_break() -> None:
    assert parse_markdown("one\ntwo\n\nthree") == [_p(_t("one two")), _p(_t("three"))]


def test_hard_break() -> None:
    assert parse_markdown("one  \ntwo") == [_p(_t("one"), {"type": "break"}, _t("two"))]


def test_inline_styles() -> None:
    assert parse_markdown("a **b _c_** `d`") == [
        _p(
            _t("a "),
            {
                "type": "strong",
                "inlines": [_t("b "), {"type": "emph", "inlines": [_t("c")]}],
            },
            _t(" "),
            {"type": "code", "text": "d"},
        )
    ]


@pytest.mark.parametrize(
    ("source", "level"), [("# h", 1), ("## h", 2), ("### h", 3), ("##### h", 3)]
)
def test_heading_levels_cap_at_three(source: str, level: int) -> None:
    assert parse_markdown(source) == [
        {"type": "heading", "level": level, "inlines": [_t("h")]}
    ]


@pytest.mark.parametrize(
    "url", ["https://example.com/a", "http://example.com", "mailto:jane@example.com"]
)
def test_safe_link(url: str) -> None:
    assert parse_markdown(f"[site]({url})") == [
        _p({"type": "link", "url": url, "inlines": [_t("site")]})
    ]


@pytest.mark.parametrize("url", ["ftp://example.com/x", "/relative", "#anchor"])
def test_other_link_targets_become_plain_text(url: str) -> None:
    assert parse_markdown(f"see [site]({url}) now") == [_p(_t("see site now"))]


def test_script_link_is_never_a_link() -> None:
    blocks = parse_markdown("[x](javascript:alert(1))")
    assert "link" not in str(blocks)


def test_raw_html_is_literal_text() -> None:
    assert parse_markdown("a <b>bold</b> <script>x</script>") == [
        _p(_t("a <b>bold</b> <script>x</script>"))
    ]
    assert parse_markdown("<div>block</div>") == [_p(_t("<div>block</div>"))]


def test_image_becomes_alt_text() -> None:
    assert parse_markdown("![a logo](https://example.com/l.png)") == [_p(_t("a logo"))]


def test_lists_nested() -> None:
    assert parse_markdown("3. a\n   - n\n4. b") == [
        {
            "type": "list",
            "ordered": True,
            "start": 3,
            "items": [
                [
                    _p(_t("a")),
                    {
                        "type": "list",
                        "ordered": False,
                        "start": 1,
                        "items": [[_p(_t("n"))]],
                    },
                ],
                [_p(_t("b"))],
            ],
        }
    ]


def test_quote_code_rule() -> None:
    assert parse_markdown("> q\n\n```py\nx = 1\n```\n\n    y = 2\n\n---") == [
        {"type": "quote", "blocks": [_p(_t("q"))]},
        {"type": "code", "text": "x = 1"},
        {"type": "code", "text": "y = 2"},
        {"type": "rule"},
    ]


def test_typst_markup_is_untouched_text() -> None:
    source = "#let x = 1 $y$ @ref <label> [box]"
    assert parse_markdown(source) == [_p(_t(source))]
