"""Unit tests for pktx.validation — shared tag / URL / length validators (027)."""

from typing import Any

import pytest

from pktx.validation import check_len, normalize_tags, validate_http_url


class TestNormalizeTags:
    def test_none_means_no_tags(self) -> None:
        assert normalize_tags(None) == []

    def test_trims_lowercases_skips_empty_and_dedupes_in_order(self) -> None:
        assert normalize_tags([" Python ", "go", "PYTHON", "", "  "]) == [
            "python",
            "go",
        ]

    @pytest.mark.parametrize(
        "value",
        [
            "backend",  # a bare string must not be split into characters
            [1],
            ["ok", None],
            {"a": 1},
            42,
        ],
    )
    def test_rejects_non_list_of_strings(self, value: Any) -> None:
        with pytest.raises(ValueError, match="list of strings"):
            normalize_tags(value)

    def test_rejects_tag_over_50_chars(self) -> None:
        assert normalize_tags(["x" * 50]) == ["x" * 50]
        with pytest.raises(ValueError, match="50 characters"):
            normalize_tags(["x" * 51])

    def test_rejects_more_than_50_tags(self) -> None:
        assert len(normalize_tags([f"t{i}" for i in range(50)])) == 50
        with pytest.raises(ValueError, match="At most 50 tags"):
            normalize_tags([f"t{i}" for i in range(51)])


class TestValidateHttpUrl:
    @pytest.mark.parametrize("value", [None, "", "   "])
    def test_empty_is_none(self, value: Any) -> None:
        assert validate_http_url(value) is None

    @pytest.mark.parametrize(
        "value",
        ["https://example.com", "http://example.com/a?b=c", "HTTPS://Example.com"],
    )
    def test_accepts_http_and_https(self, value: str) -> None:
        assert validate_http_url(value) == value

    @pytest.mark.parametrize(
        "value",
        [
            "javascript:alert(1)",
            "JaVaScRiPt:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "ftp://example.com/file",
            "mailto:a@b.c",
            "//example.com",
            "example.com",
            "https://",
            123,
        ],
    )
    def test_rejects_non_http_urls(self, value: Any) -> None:
        with pytest.raises(ValueError):
            validate_http_url(value)

    def test_rejects_over_2048_chars(self) -> None:
        url = "https://example.com/" + "a" * 2048
        with pytest.raises(ValueError, match="2048"):
            validate_http_url(url)


class TestCheckLen:
    def test_allows_at_limit_and_non_strings(self) -> None:
        check_len("title", "x" * 10, 10)
        check_len("title", None, 10)

    def test_rejects_over_limit_naming_the_field(self) -> None:
        with pytest.raises(ValueError, match="title must not exceed 10"):
            check_len("title", "x" * 11, 10)
