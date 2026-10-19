"""REST contract for resumes: envelope CRUD and the JSON Resume ``data`` routes."""

from typing import Any

import pytest
from fastapi import FastAPI
from psycopg import Connection
from starlette.testclient import TestClient

from pktx.api.routes import create_router
from pktx.resume_service import ResumeService


@pytest.fixture
def client(db_conn_with_data: Connection[Any]) -> TestClient:
    app = FastAPI()
    app.include_router(create_router(ResumeService(db_conn_with_data)))  # type: ignore[arg-type]
    c = TestClient(app)
    c.vid = c.get("/api/resumes").json()[0]["id"]  # type: ignore[attr-defined]
    return c


def _url(c: TestClient, tail: str = "") -> str:
    return f"/api/resumes/{c.vid}{tail}"  # type: ignore[attr-defined]


class TestEnvelope:
    def test_list(self, client: TestClient) -> None:
        rows = client.get("/api/resumes").json()
        assert len(rows) == 1 and rows[0]["is_default"] is True
        assert "data" not in rows[0]

    def test_get(self, client: TestClient) -> None:
        r = client.get(_url(client)).json()
        assert {"id", "label", "tags", "is_default", "data", "links"} <= set(r)
        assert "resume_data" not in r
        assert r["data"]["basics"]["name"] == "Jane Doe"
        assert r["data"]["work"][0]["startDate"] == "2021-01"

    def test_get_not_found(self, client: TestClient) -> None:
        assert client.get("/api/resumes/9999").status_code == 404

    def test_default_route_removed(self, client: TestClient) -> None:
        assert client.get("/api/resumes/default").status_code == 422

    def test_create_copies_default(self, client: TestClient) -> None:
        r = client.post("/api/resumes", json={"label": "Copy", "tags": ["A"]})
        assert r.status_code == 201
        body = r.json()
        assert body["tags"] == ["a"] and body["is_default"] is False
        assert body["data"] == client.get(_url(client)).json()["data"]

    def test_create_from_json_resume(self, client: TestClient) -> None:
        r = client.post(
            "/api/resumes",
            json={
                "label": "Imported",
                "data": {"basics": {"name": "Ada"}, "work": [{"name": "X"}]},
            },
        )
        assert r.status_code == 201, r.text
        assert r.json()["data"]["work"][0]["id"]

    @pytest.mark.parametrize(
        "body",
        [{}, {"label": "  "}, {"label": "x", "data": {"work": [{"startDate": "May"}]}}],
    )
    def test_create_invalid_422(self, client: TestClient, body: dict) -> None:
        assert client.post("/api/resumes", json=body).status_code == 422

    def test_create_unknown_field_422(self, client: TestClient) -> None:
        r = client.post("/api/resumes", json={"label": "x", "resume_data": {}})
        assert r.status_code == 422 and "resume_data" in r.json()["detail"]

    def test_patch_label_tags(self, client: TestClient) -> None:
        r = client.patch(_url(client), json={"label": "New", "tags": ["x"]})
        assert r.status_code == 200
        assert r.json()["label"] == "New" and r.json()["tags"] == ["x"]

    def test_patch_empty_422(self, client: TestClient) -> None:
        assert client.patch(_url(client), json={}).status_code == 422

    def test_patch_is_default(self, client: TestClient) -> None:
        other = client.post("/api/resumes", json={"label": "B"}).json()["id"]
        r = client.patch(f"/api/resumes/{other}", json={"is_default": True})
        assert r.status_code == 200 and r.json()["is_default"] is True
        assert client.get(_url(client)).json()["is_default"] is False

    def test_cannot_unset_default(self, client: TestClient) -> None:
        r = client.patch(_url(client), json={"is_default": False})
        assert r.status_code == 422

    def test_set_default_post_route_removed(self, client: TestClient) -> None:
        assert client.post(_url(client, "/default")).status_code in (404, 405)

    def test_delete(self, client: TestClient) -> None:
        other = client.post("/api/resumes", json={"label": "B"}).json()["id"]
        assert client.delete(f"/api/resumes/{other}").status_code == 200
        assert client.get(f"/api/resumes/{other}").status_code == 404

    def test_delete_last_409(self, client: TestClient) -> None:
        assert client.delete(_url(client)).status_code == 409

    def test_tags(self, client: TestClient) -> None:
        client.patch(_url(client), json={"tags": ["b", "a"]})
        assert client.get("/api/resumes/tags").json() == ["a", "b"]


class TestSchema:
    def test_sections_with_schema_and_widgets(self, client: TestClient) -> None:
        r = client.get("/api/resumes/schema")
        assert r.status_code == 200
        sections = {s["key"]: s for s in r.json()}
        assert list(sections)[0] == "basics"
        assert sections["basics"]["kind"] == "object"
        assert sections["work"]["kind"] == "list"
        assert sections["work"]["label"] == "Experience"
        props = sections["work"]["schema"]["properties"]
        assert "startDate" in props and "id" in props
        assert props["highlights"]["widget"] == "bullets"
        assert props["startDate"]["widget"] == "date"
        assert (
            sections["skills"]["schema"]["properties"]["keywords"]["widget"] == "tags"
        )
        assert {"interests", "references", "certificates"} <= set(sections)

    def test_old_routes_gone(self, client: TestClient) -> None:
        assert client.get("/api/resume-sections").status_code == 404
        assert client.get("/api/resume-contact-keys").status_code == 404


class TestData:
    def test_replace_document(self, client: TestClient) -> None:
        r = client.put(_url(client, "/data"), json={"basics": {"name": "Z"}, "x": 1})
        assert r.status_code == 200, r.text
        assert r.json()["data"] == {"basics": {"name": "Z"}}

    def test_replace_invalid_422_and_unchanged(self, client: TestClient) -> None:
        before = client.get(_url(client)).json()["data"]
        r = client.put(_url(client, "/data"), json={"basics": {"email": "nope"}})
        assert r.status_code == 422 and "basics.email" in r.json()["detail"]
        assert client.get(_url(client)).json()["data"] == before

    def test_patch_basics(self, client: TestClient) -> None:
        r = client.patch(_url(client, "/data/basics"), json={"label": "Staff"})
        assert r.status_code == 200
        assert r.json()["label"] == "Staff" and r.json()["name"] == "Jane Doe"

    def test_patch_basics_validation(self, client: TestClient) -> None:
        url = _url(client, "/data/basics")
        assert client.patch(url, json={}).status_code == 422
        assert client.patch(url, json={"url": "javascript:x"}).status_code == 422
        assert client.patch(url, json={"bogus": 1}).status_code == 422

    def test_entry_crud(self, client: TestClient) -> None:
        r = client.post(
            _url(client, "/data/projects"),
            json={"name": "pktx", "url": "github.com/x/pktx", "keywords": ["py"]},
        )
        assert r.status_code == 201, r.text
        entry = r.json()
        assert entry["id"] and entry["url"] == "https://github.com/x/pktx"

        eurl = _url(client, f"/data/projects/{entry['id']}")
        r = client.patch(eurl, json={"name": "pktx2"})
        assert r.status_code == 200 and r.json()["name"] == "pktx2"
        assert r.json()["keywords"] == ["py"]

        assert client.delete(eurl).status_code == 204
        assert client.delete(eurl).status_code == 404
        assert "projects" not in client.get(_url(client)).json()["data"]

    def test_add_position_query(self, client: TestClient) -> None:
        r = client.post(
            _url(client, "/data/work") + "?position=0", json={"position": "First"}
        )
        assert r.status_code == 201
        work = client.get(_url(client)).json()["data"]["work"]
        assert work[0]["id"] == r.json()["id"]

    def test_add_bad_position_422(self, client: TestClient) -> None:
        url = _url(client, "/data/work")
        assert client.post(url + "?position=99", json={"name": "x"}).status_code == 422
        assert client.post(url + "?position=-1", json={"name": "x"}).status_code == 422

    def test_reorder(self, client: TestClient) -> None:
        r = client.put(_url(client, "/data/work/order"), json={"ids": ["w2", "w1"]})
        assert r.status_code == 200
        assert [w["id"] for w in r.json()] == ["w2", "w1"]
        work = client.get(_url(client)).json()["data"]["work"]
        assert [w["id"] for w in work] == ["w2", "w1"]

    @pytest.mark.parametrize(
        "body", [{"ids": ["w1"]}, {"ids": ["w1", "w1"]}, {}, {"x": 1}]
    )
    def test_reorder_invalid_422(self, client: TestClient, body: dict) -> None:
        assert (
            client.put(_url(client, "/data/work/order"), json=body).status_code == 422
        )

    @pytest.mark.parametrize(
        "method,tail",
        [
            ("post", "/data/bogus"),
            ("post", "/data/basics"),
            ("patch", "/data/bogus/x"),
            ("delete", "/data/bogus/x"),
            ("put", "/data/bogus/order"),
        ],
    )
    def test_unknown_section_404(
        self, client: TestClient, method: str, tail: str
    ) -> None:
        kwargs = {} if method == "delete" else {"json": {"ids": []}}
        r = getattr(client, method)(_url(client, tail), **kwargs)
        assert r.status_code == 404

    def test_index_is_not_an_id(self, client: TestClient) -> None:
        r = client.patch(_url(client, "/data/work/0"), json={"name": "x"})
        assert r.status_code == 404

    def test_entry_validation_422(self, client: TestClient) -> None:
        url = _url(client, "/data/work")
        assert client.post(url, json={}).status_code == 422
        assert client.post(url, json={"startDate": "May 2020"}).status_code == 422
        assert client.post(url, json={"url": "ftp://x.io"}).status_code == 422
        assert client.post(url, json={"bogus": 1, "name": "x"}).status_code == 422

    def test_removed_routes_gone(self, client: TestClient) -> None:
        assert client.put(_url(client, "/contact"), json={"name": "x"}).status_code in (
            404,
            405,
        )
        assert client.put(_url(client, "/summary"), json={"text": "x"}).status_code in (
            404,
            405,
        )
        assert client.get(_url(client, "/work")).status_code in (404, 405)
        assert client.put(_url(client, "/sections/awards"), json={}).status_code in (
            404,
            405,
        )
        assert client.post(_url(client, "/work/entries"), json={}).status_code in (
            404,
            405,
        )

    def test_malformed_json_422(self, client: TestClient) -> None:
        r = client.post(
            _url(client, "/data/work"),
            content=b"{bad",
            headers={"content-type": "application/json"},
        )
        assert r.status_code == 422


JSON_RESUME_SAMPLE: dict[str, Any] = {
    "basics": {
        "name": "John Doe",
        "label": "Programmer",
        "image": "https://example.com/john.jpg",
        "email": "john@gmail.com",
        "phone": "(912) 555-4321",
        "url": "https://johndoe.com",
        "summary": "A summary of John Doe...",
        "location": {
            "address": "2712 Broadway St",
            "postalCode": "CA 94115",
            "city": "San Francisco",
            "countryCode": "US",
            "region": "California",
        },
        "profiles": [
            {
                "network": "Twitter",
                "username": "john",
                "url": "https://twitter.com/john",
            }
        ],
    },
    "work": [
        {
            "name": "Company",
            "position": "President",
            "url": "https://company.com",
            "startDate": "2013-01-01",
            "endDate": "2014-01-01",
            "summary": "Description...",
            "highlights": ["Started the company"],
        }
    ],
    "volunteer": [
        {
            "organization": "Organization",
            "position": "Volunteer",
            "url": "https://organization.com/",
            "startDate": "2012-01-01",
            "endDate": "2013-01-01",
            "summary": "Description...",
            "highlights": ["Awarded 'Volunteer of the Month'"],
        }
    ],
    "education": [
        {
            "institution": "University",
            "url": "https://institution.com/",
            "area": "Software Development",
            "studyType": "Bachelor",
            "startDate": "2011-01-01",
            "endDate": "2013-01-01",
            "score": "4.0",
            "courses": ["DB1101 - Basic SQL"],
        }
    ],
    "awards": [
        {
            "title": "Award",
            "date": "2014-11-01",
            "awarder": "Company",
            "summary": "There is no spoon.",
        }
    ],
    "certificates": [
        {
            "name": "Certificate",
            "date": "2021-11-07",
            "issuer": "Company",
            "url": "https://certificate.com",
        }
    ],
    "publications": [
        {
            "name": "Publication",
            "publisher": "Company",
            "releaseDate": "2014-10-01",
            "url": "https://publication.com",
            "summary": "Description...",
        }
    ],
    "skills": [
        {"name": "Web Development", "level": "Master", "keywords": ["HTML", "CSS"]}
    ],
    "languages": [{"language": "English", "fluency": "Native speaker"}],
    "interests": [{"name": "Wildlife", "keywords": ["Ferrets", "Unicorns"]}],
    "references": [{"name": "Jane Doe", "reference": "Reference..."}],
    "projects": [
        {
            "name": "Project",
            "startDate": "2019-01-01",
            "endDate": "2021-01-01",
            "description": "Description...",
            "highlights": ["Won award at AIHacks 2016"],
            "url": "https://project.com/",
            "roles": ["Team Lead"],
            "entity": "Entity",
            "type": "application",
            "keywords": ["x"],
        }
    ],
    "meta": {
        "canonical": "https://example.com/resume.json",
        "version": "v1.0.0",
        "lastModified": "2017-12-24T15:53:00",
    },
}


def _strip_ids(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip_ids(v) for k, v in value.items() if k != "id"}
    if isinstance(value, list):
        return [_strip_ids(v) for v in value]
    return value


def test_jsonresume_sample_round_trips(client: TestClient) -> None:
    sample = {"$schema": "https://example.com/schema.json", **JSON_RESUME_SAMPLE}
    r = client.put(_url(client, "/data"), json=sample)
    assert r.status_code == 200, r.text
    stored = client.get(_url(client)).json()["data"]
    assert _strip_ids(stored) == JSON_RESUME_SAMPLE
    ids = [e["id"] for k, v in stored.items() if isinstance(v, list) for e in v]
    ids += [p["id"] for p in stored["basics"]["profiles"]]
    assert all(ids) and len(set(ids)) == len(ids)

    # Export carries the document unchanged.
    # (Stored shape == wire shape, so a second import is a fixed point.)
    again = client.put(_url(client, "/data"), json=stored).json()["data"]
    assert again == stored
