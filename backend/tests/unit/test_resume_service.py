"""Unit tests for pktx.resume_service: versions and JSON Resume document edits."""

from typing import Any

import pytest

from pktx.resume_service import ResumeService

U = "legacy"


@pytest.fixture
def svc(resume_service: object) -> ResumeService:
    return resume_service  # type: ignore[return-value]


@pytest.fixture
def svc_data(resume_service_with_data: object) -> ResumeService:
    return resume_service_with_data  # type: ignore[return-value]


def _doc(svc: ResumeService, vid: int | None = None) -> dict[str, Any]:
    return svc.get_resume(vid, user_id=U)["data"]


def _default_id(svc: ResumeService) -> int:
    return svc.get_resume(user_id=U)["id"]


class TestGet:
    def test_default_has_envelope_and_document(self, svc_data: ResumeService) -> None:
        r = svc_data.get_resume(user_id=U)
        assert r["is_default"] is True
        assert {"id", "label", "tags", "created_at", "updated_at", "links"} <= set(r)
        assert r["data"]["basics"]["name"] == "Jane Doe"
        assert len(r["data"]["work"]) == 2
        assert len(r["data"]["skills"]) == 3

    def test_empty_default_is_an_object(self, svc: ResumeService) -> None:
        assert isinstance(svc.get_resume(user_id=U)["data"], dict)

    def test_missing_version_raises(self, svc: ResumeService) -> None:
        with pytest.raises(ValueError, match="not found"):
            svc.get_resume(9999, user_id=U)


class TestCreate:
    def test_copies_default(self, svc_data: ResumeService) -> None:
        v = svc_data.create_resume("Copy", user_id=U)
        assert v["is_default"] is False
        assert v["data"] == _doc(svc_data)

    def test_from_json_resume_either_case(self, svc: ResumeService) -> None:
        v = svc.create_resume(
            "Imported",
            user_id=U,
            data={
                "basics": {"name": "Ada"},
                "work": [{"position": "Eng", "start_date": "2020", "endDate": "2021"}],
                "unknown": {"x": 1},
            },
        )
        work = v["data"]["work"][0]
        assert work["startDate"] == "2020" and work["endDate"] == "2021"
        assert work["id"]
        assert "unknown" not in v["data"]

    def test_invalid_data_rejected(self, svc: ResumeService) -> None:
        with pytest.raises(ValueError, match="work.0.startDate"):
            svc.create_resume("Bad", user_id=U, data={"work": [{"startDate": "May"}]})
        with pytest.raises(ValueError, match="JSON object"):
            svc.create_resume("Bad", user_id=U, data=[])  # type: ignore[arg-type]

    @pytest.mark.parametrize("label", ["", "   "])
    def test_empty_label_rejected(self, svc: ResumeService, label: str) -> None:
        with pytest.raises(ValueError, match="Label"):
            svc.create_resume(label, user_id=U)

    def test_label_stripped(self, svc: ResumeService) -> None:
        assert svc.create_resume("  X  ", user_id=U)["label"] == "X"

    def test_import_assigns_unique_ids(self, svc: ResumeService) -> None:
        v = svc.create_resume(
            "Dupes",
            user_id=U,
            data={
                "work": [{"id": "same", "name": "A"}, {"id": "same", "name": "B"}],
                "basics": {"profiles": [{"id": "same", "network": "GH"}]},
            },
        )
        ids = [w["id"] for w in v["data"]["work"]]
        ids.append(v["data"]["basics"]["profiles"][0]["id"])
        assert len(set(ids)) == 3 and ids[0] == "same"


class TestUpdate:
    def test_label_and_tags(self, svc: ResumeService) -> None:
        v = svc.update_resume(_default_id(svc), user_id=U, label="New", tags=["A "])
        assert v["label"] == "New" and v["tags"] == ["a"]

    def test_omitted_fields_unchanged(self, svc_data: ResumeService) -> None:
        vid = _default_id(svc_data)
        before = _doc(svc_data)
        v = svc_data.update_resume(vid, user_id=U, label="Only label")
        assert v["data"] == before

    def test_nothing_to_update_rejected(self, svc: ResumeService) -> None:
        with pytest.raises(ValueError, match="Nothing to update"):
            svc.update_resume(_default_id(svc), user_id=U)

    def test_data_replaces_whole_document(self, svc_data: ResumeService) -> None:
        vid = _default_id(svc_data)
        v = svc_data.update_resume(vid, user_id=U, data={"basics": {"name": "Z"}})
        assert v["data"] == {"basics": {"name": "Z"}}

    def test_invalid_data_changes_nothing(self, svc_data: ResumeService) -> None:
        vid = _default_id(svc_data)
        before = svc_data.get_resume(vid, user_id=U)
        with pytest.raises(ValueError):
            svc_data.update_resume(
                vid, user_id=U, label="Changed", data={"work": [{"endDate": "x"}]}
            )
        after = svc_data.get_resume(vid, user_id=U)
        assert after["label"] == before["label"] and after["data"] == before["data"]

    def test_set_default_moves_flag(self, svc: ResumeService) -> None:
        other = svc.create_resume("Other", user_id=U)["id"]
        svc.update_resume(other, user_id=U, is_default=True)
        assert svc.get_resume(user_id=U)["id"] == other
        assert [r["is_default"] for r in svc.list_resumes(U)].count(True) == 1

    def test_cannot_unset_default(self, svc: ResumeService) -> None:
        with pytest.raises(ValueError, match="Cannot unset"):
            svc.update_resume(_default_id(svc), user_id=U, is_default=False)

    def test_false_on_non_default_is_noop(self, svc: ResumeService) -> None:
        other = svc.create_resume("Other", user_id=U)["id"]
        assert (
            svc.update_resume(other, user_id=U, is_default=False)["is_default"] is False
        )

    def test_missing_version(self, svc: ResumeService) -> None:
        with pytest.raises(ValueError, match="not found"):
            svc.update_resume(9999, user_id=U, label="x")


class TestDelete:
    def test_deletes_and_returns_summary(self, svc: ResumeService) -> None:
        v = svc.create_resume("Temp", user_id=U)
        assert svc.delete_resume(v["id"], user_id=U) == {"id": v["id"], "label": "Temp"}
        assert v["id"] not in [r["id"] for r in svc.list_resumes(U)]

    def test_last_version_protected(self, svc: ResumeService) -> None:
        with pytest.raises(ValueError, match="last remaining"):
            svc.delete_resume(_default_id(svc), user_id=U)


class TestBasics:
    def test_merges_fields(self, svc_data: ResumeService) -> None:
        vid = _default_id(svc_data)
        out = svc_data.update_basics(vid, {"label": "Staff", "phone": "123"}, user_id=U)
        assert out["label"] == "Staff" and out["phone"] == "123"
        assert out["name"] == "Jane Doe" and out["email"] == "jane@example.com"

    def test_snake_case_keys_accepted(self, svc: ResumeService) -> None:
        out = svc.update_basics(
            _default_id(svc),
            {"location": {"country_code": "US", "postal_code": "1"}},
            user_id=U,
        )
        assert out["location"] == {"countryCode": "US", "postalCode": "1"}

    def test_blank_clears_field(self, svc_data: ResumeService) -> None:
        out = svc_data.update_basics(_default_id(svc_data), {"phone": ""}, user_id=U)
        assert "phone" not in out

    def test_profiles_replaced_and_get_ids(self, svc_data: ResumeService) -> None:
        out = svc_data.update_basics(
            _default_id(svc_data),
            {"profiles": [{"network": "X", "url": "x.com/jane"}]},
            user_id=U,
        )
        assert len(out["profiles"]) == 1
        assert out["profiles"][0]["url"] == "https://x.com/jane"
        assert out["profiles"][0]["id"]

    @pytest.mark.parametrize(
        "patch,match",
        [
            ({}, "At least one"),
            ({"nope": 1}, "Unknown field"),
            ({"email": "bad"}, "email"),
            ({"url": "javascript:alert(1)"}, "url"),
            ({"profiles": [{"url": "ftp://x.io"}]}, "profiles"),
        ],
    )
    def test_invalid_rejected(
        self, svc: ResumeService, patch: dict[str, Any], match: str
    ) -> None:
        with pytest.raises(ValueError, match=match):
            svc.update_basics(_default_id(svc), patch, user_id=U)


class TestAddEntry:
    def test_appends_and_returns_entry_with_id(self, svc_data: ResumeService) -> None:
        vid = _default_id(svc_data)
        e = svc_data.add_entry(
            vid, "work", {"position": "CTO", "start_date": "2024-01"}, user_id=U
        )
        assert e["id"] and e["startDate"] == "2024-01"
        assert _doc(svc_data)["work"][-1] == e

    def test_position_inserts(self, svc_data: ResumeService) -> None:
        vid = _default_id(svc_data)
        e = svc_data.add_entry(
            vid, "work", {"position": "First"}, user_id=U, position=0
        )
        assert [w["id"] for w in _doc(svc_data)["work"]][0] == e["id"]

    @pytest.mark.parametrize("position", [-1, 3, "0"])
    def test_bad_position_rejected(
        self, svc_data: ResumeService, position: Any
    ) -> None:
        with pytest.raises(ValueError, match="Position"):
            svc_data.add_entry(
                _default_id(svc_data),
                "work",
                {"name": "x"},
                user_id=U,
                position=position,
            )

    def test_into_empty_section(self, svc: ResumeService) -> None:
        e = svc.add_entry(
            _default_id(svc),
            "projects",
            {"name": "pktx", "keywords": ["py"]},
            user_id=U,
        )
        assert _doc(svc)["projects"] == [e]

    @pytest.mark.parametrize(
        "section,entry",
        [
            ("work", {"position": "x"}),
            ("education", {"institution": "x", "studyType": "BS"}),
            ("skills", {"name": "Langs", "keywords": ["Go"]}),
            ("projects", {"name": "x", "roles": ["lead"], "type": "app"}),
            ("certificates", {"name": "CKA", "issuer": "CNCF", "date": "2024"}),
            ("awards", {"title": "t", "awarder": "a"}),
            ("publications", {"name": "n", "releaseDate": "2020-05-01"}),
            ("volunteer", {"organization": "o", "position": "p"}),
            ("languages", {"language": "Spanish", "fluency": "Fluent"}),
            ("interests", {"name": "Climbing", "keywords": ["rock"]}),
            ("references", {"name": "A B", "reference": "Great."}),
        ],
    )
    def test_every_section(
        self, svc: ResumeService, section: str, entry: dict[str, Any]
    ) -> None:
        e = svc.add_entry(_default_id(svc), section, entry, user_id=U)
        assert {k: v for k, v in e.items() if k != "id"} == entry

    @pytest.mark.parametrize(
        "section,entry,match",
        [
            ("work", {}, "at least one field"),
            ("work", {"name": "  "}, "at least one field"),
            ("work", {"startDate": "May 2020"}, "startDate"),
            ("work", {"name": "x", "bogus": 1}, "Unknown field 'bogus'"),
            ("work", {"url": "javascript:x"}, "url"),
            ("work", {"name": "x" * 201}, "200"),
            ("nope", {"name": "x"}, "Invalid section"),
            ("basics", {"name": "x"}, "Invalid section"),
        ],
    )
    def test_invalid_rejected(
        self, svc: ResumeService, section: str, entry: dict[str, Any], match: str
    ) -> None:
        with pytest.raises(ValueError, match=match):
            svc.add_entry(_default_id(svc), section, entry, user_id=U)

    def test_client_supplied_id_ignored(self, svc: ResumeService) -> None:
        e = svc.add_entry(
            _default_id(svc), "awards", {"id": "mine", "title": "t"}, user_id=U
        )
        assert e["id"] != "mine"


class TestUpdateEntry:
    def test_partial_update_keeps_other_fields(self, svc_data: ResumeService) -> None:
        vid = _default_id(svc_data)
        e = svc_data.update_entry(vid, "work", "w1", {"position": "Staff"}, user_id=U)
        assert e["position"] == "Staff" and e["name"] == "Acme Corp"
        assert e["id"] == "w1"
        assert _doc(svc_data)["work"][0] == e

    def test_snake_case_does_not_duplicate_camel(self, svc_data: ResumeService) -> None:
        e = svc_data.update_entry(
            _default_id(svc_data), "work", "w1", {"start_date": "2022"}, user_id=U
        )
        assert e["startDate"] == "2022" and "start_date" not in e

    def test_blank_clears_field(self, svc_data: ResumeService) -> None:
        e = svc_data.update_entry(
            _default_id(svc_data), "work", "w2", {"endDate": ""}, user_id=U
        )
        assert "endDate" not in e

    def test_cannot_empty_an_entry(self, svc: ResumeService) -> None:
        vid = _default_id(svc)
        e = svc.add_entry(vid, "awards", {"title": "t"}, user_id=U)
        with pytest.raises(ValueError, match="at least one field"):
            svc.update_entry(vid, "awards", e["id"], {"title": ""}, user_id=U)

    def test_id_in_patch_ignored(self, svc_data: ResumeService) -> None:
        e = svc_data.update_entry(
            _default_id(svc_data), "work", "w1", {"id": "x", "name": "N"}, user_id=U
        )
        assert e["id"] == "w1"

    def test_unknown_id_not_found(self, svc_data: ResumeService) -> None:
        with pytest.raises(ValueError, match="not found"):
            svc_data.update_entry(
                _default_id(svc_data), "work", "nope", {"name": "x"}, user_id=U
            )

    def test_numeric_index_is_not_an_id(self, svc_data: ResumeService) -> None:
        with pytest.raises(ValueError, match="not found"):
            svc_data.update_entry(
                _default_id(svc_data), "work", "0", {"name": "x"}, user_id=U
            )

    def test_invalid_value_leaves_entry_untouched(
        self, svc_data: ResumeService
    ) -> None:
        vid = _default_id(svc_data)
        before = _doc(svc_data)
        with pytest.raises(ValueError):
            svc_data.update_entry(vid, "work", "w1", {"startDate": "bad"}, user_id=U)
        assert _doc(svc_data) == before


class TestRemoveEntry:
    def test_removes_and_returns_entry(self, svc_data: ResumeService) -> None:
        vid = _default_id(svc_data)
        removed = svc_data.remove_entry(vid, "work", "w1", user_id=U)
        assert removed["id"] == "w1"
        assert [w["id"] for w in _doc(svc_data)["work"]] == ["w2"]

    def test_last_entry_drops_section(self, svc_data: ResumeService) -> None:
        vid = _default_id(svc_data)
        for sid in ("s1", "s2", "s3"):
            svc_data.remove_entry(vid, "skills", sid, user_id=U)
        assert "skills" not in _doc(svc_data)

    def test_unknown_id_not_found(self, svc_data: ResumeService) -> None:
        with pytest.raises(ValueError, match="not found"):
            svc_data.remove_entry(_default_id(svc_data), "work", "nope", user_id=U)

    def test_invalid_section(self, svc: ResumeService) -> None:
        with pytest.raises(ValueError, match="Invalid section"):
            svc.remove_entry(_default_id(svc), "contact", "x", user_id=U)


class TestReorder:
    def test_reorders(self, svc_data: ResumeService) -> None:
        vid = _default_id(svc_data)
        out = svc_data.reorder_entries(vid, "work", ["w2", "w1"], user_id=U)
        assert [w["id"] for w in out] == ["w2", "w1"]
        assert [w["id"] for w in _doc(svc_data)["work"]] == ["w2", "w1"]

    @pytest.mark.parametrize(
        "ids",
        [["w1"], ["w1", "w1"], ["w1", "w2", "w3"], ["w1", "x"], "w1w2", []],
    )
    def test_must_be_exact_permutation(self, svc_data: ResumeService, ids: Any) -> None:
        with pytest.raises(ValueError, match="exactly once"):
            svc_data.reorder_entries(_default_id(svc_data), "work", ids, user_id=U)

    def test_empty_section_accepts_empty_list(self, svc: ResumeService) -> None:
        assert svc.reorder_entries(_default_id(svc), "awards", [], user_id=U) == []


class TestListAndIsolation:
    def test_list_metadata(self, svc: ResumeService) -> None:
        row = svc.list_resumes(U)[0]
        assert {"id", "label", "is_default", "tags", "app_count", "link_count"} <= set(
            row
        )
        assert "data" not in row

    def test_app_count_from_linked_applications(
        self, svc: ResumeService, db_conn: Any
    ) -> None:
        from pktx.database import create_application, link_insert

        vid = _default_id(svc)
        app = create_application(db_conn, {"company": "Co", "position": "Dev"}, U)
        link_insert(db_conn, "application", app["id"], "resume", vid, U)
        target = next(v for v in svc.list_resumes(U) if v["id"] == vid)
        assert target["app_count"] == 1

    def test_editing_copy_does_not_affect_original(
        self, svc_data: ResumeService
    ) -> None:
        original = _default_id(svc_data)
        copy = svc_data.create_resume("Copy", user_id=U)["id"]
        svc_data.update_basics(copy, {"name": "Changed"}, user_id=U)
        svc_data.add_entry(copy, "work", {"name": "New"}, user_id=U)
        svc_data.remove_entry(copy, "education", "e1", user_id=U)
        doc = _doc(svc_data, original)
        assert doc["basics"]["name"] == "Jane Doe"
        assert len(doc["work"]) == 2 and len(doc["education"]) == 2


class TestTags:
    def test_normalized_on_create_and_update(self, svc: ResumeService) -> None:
        v = svc.create_resume("T", user_id=U, tags=["  Backend ", "backend", "API"])
        assert v["tags"] == ["backend", "api"]
        assert svc.update_resume(v["id"], user_id=U, tags=["X"])["tags"] == ["x"]

    def test_tag_length_limit(self, svc: ResumeService) -> None:
        with pytest.raises(ValueError, match="50"):
            svc.create_resume("T", user_id=U, tags=["t" * 51])

    def test_list_tags(self, svc: ResumeService) -> None:
        svc.create_resume("A", user_id=U, tags=["b", "a"])
        svc.create_resume("B", user_id=U, tags=["c", "a"])
        assert svc.list_tags(U) == ["a", "b", "c"]
