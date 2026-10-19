"""Unit tests for pktx.json_resume: the JSON Resume models."""

from typing import Any

import pytest

from pktx.json_resume import (
    Basics,
    Resume,
    Work,
    alias_keys,
    dump,
    validate,
)


class TestAliases:
    def test_camel_and_snake_input_both_accepted(self) -> None:
        camel = Work.model_validate({"startDate": "2020-01", "endDate": "2021"})
        snake = Work.model_validate({"start_date": "2020-01", "end_date": "2021"})
        assert camel == snake

    def test_dump_is_camel_case_and_compact(self) -> None:
        w = Work.model_validate(
            {"name": "Acme", "start_date": "2020", "highlights": []}
        )
        assert dump(w) == {"name": "Acme", "startDate": "2020"}

    def test_unknown_keys_ignored(self) -> None:
        r = Resume.model_validate({"basics": {"name": "N", "x": 1}, "weird": []})
        assert dump(r) == {"basics": {"name": "N"}}

    def test_empty_resume_dumps_empty(self) -> None:
        assert dump(Resume()) == {}

    def test_full_spec_sections_present(self) -> None:
        keys = {f.alias for f in Resume.model_fields.values()}
        assert keys == {
            "basics", "work", "volunteer", "education", "awards", "certificates",
            "publications", "skills", "languages", "interests", "references",
            "projects", "meta",
        }  # fmt: skip

    def test_spec_names_roundtrip(self) -> None:
        doc: dict[str, Any] = {
            "basics": {
                "name": "A",
                "location": {
                    "address": "1 Main",
                    "postalCode": "94105",
                    "city": "SF",
                    "countryCode": "US",
                    "region": "CA",
                },
            },
            "education": [{"studyType": "BS", "area": "CS", "score": "4.0"}],
            "publications": [{"name": "P", "releaseDate": "2020-05-01"}],
            "meta": {"canonical": "https://x.example/r.json", "lastModified": "t"},
        }
        assert dump(Resume.model_validate(doc)) == doc


class TestBlanks:
    def test_blank_string_is_absent(self) -> None:
        assert dump(Work.model_validate({"name": "  ", "position": "Dev"})) == {
            "position": "Dev"
        }

    def test_blank_list_items_dropped(self) -> None:
        w = Work.model_validate({"highlights": ["a", " ", ""]})
        assert w.highlights == ["a"]

    def test_strings_trimmed(self) -> None:
        assert Work.model_validate({"name": "  Acme "}).name == "Acme"


class TestDates:
    @pytest.mark.parametrize("value", ["2024", "2024-03", "2024-03-05"])
    def test_partial_iso_accepted(self, value: str) -> None:
        assert Work.model_validate({"startDate": value}).start_date == value

    @pytest.mark.parametrize(
        "value", ["March 2024", "2024-13", "2024/03", "03/2024", "2024-02-30", "24"]
    )
    def test_other_formats_rejected(self, value: str) -> None:
        with pytest.raises(ValueError, match="Date"):
            validate(Work, {"startDate": value})


class TestUrlsAndEmail:
    def test_bare_host_gets_https(self) -> None:
        assert (
            Basics.model_validate({"url": "janedoe.dev"}).url == "https://janedoe.dev"
        )

    @pytest.mark.parametrize("url", ["javascript:alert(1)", "ftp://x.example/f"])
    def test_non_http_urls_rejected(self, url: str) -> None:
        with pytest.raises(ValueError):
            validate(Work, {"url": url})
        with pytest.raises(ValueError):
            validate(Basics, {"profiles": [{"url": url}]})
        with pytest.raises(ValueError):
            validate(Basics, {"image": url})

    def test_email_validated(self) -> None:
        assert Basics.model_validate({"email": "a@b.co"}).email == "a@b.co"
        with pytest.raises(ValueError, match="email"):
            validate(Basics, {"email": "nope"})


class TestLimits:
    def test_name_length_capped(self) -> None:
        with pytest.raises(ValueError, match="200"):
            validate(Work, {"name": "x" * 201})

    def test_bullet_count_capped(self) -> None:
        with pytest.raises(ValueError):
            validate(Work, {"highlights": ["a"] * 101})


class TestHelpers:
    def test_validate_error_is_short_and_located(self) -> None:
        with pytest.raises(ValueError) as exc:
            validate(Resume, {"work": [{"startDate": "bad"}]})
        assert (
            str(exc.value)
            == "work.0.startDate: Date must be YYYY, YYYY-MM or YYYY-MM-DD"
        )

    def test_alias_keys_renames_and_rejects_unknown(self) -> None:
        assert alias_keys(Work, {"start_date": "2020", "name": "A"}) == {
            "startDate": "2020",
            "name": "A",
        }
        with pytest.raises(ValueError, match="Unknown field 'nope'"):
            alias_keys(Work, {"nope": 1})
