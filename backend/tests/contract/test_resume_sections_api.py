"""REST contract for registry-driven resume sections, entry ids and layout."""

from typing import Any

import pytest
from psycopg import Connection

from tests.helpers import build_full_app, user_client

USER = "sections_user"


@pytest.fixture
def client(db_conn: Connection[Any]):
    db_conn.execute("INSERT INTO users (id) VALUES (%s)", (USER,))
    app = build_full_app(db_conn)
    c = user_client(app, USER)
    r = c.post("/api/resumes", json={"label": "Main"})
    assert r.status_code == 201, r.text
    c.vid = r.json()["id"]  # type: ignore[attr-defined]
    return c


def test_sections_metadata(client) -> None:
    r = client.get("/api/resume-sections")
    assert r.status_code == 200
    keys = [s["key"] for s in r.json()]
    assert "projects" in keys and "certifications" in keys and keys[-1] == "custom"


def test_new_section_crud_by_id(client) -> None:
    v = client.vid
    r = client.post(
        f"/api/resumes/{v}/projects/entries",
        json={"name": "pktx", "url": "github.com/x/pktx"},
    )
    assert r.status_code == 201, r.text
    entries = client.get(f"/api/resumes/{v}/projects").json()
    eid = entries[0]["id"]
    assert entries[0]["url"] == "https://github.com/x/pktx"

    r = client.put(f"/api/resumes/{v}/projects/entries/{eid}", json={"name": "pktx2"})
    assert r.status_code == 200, r.text
    assert client.get(f"/api/resumes/{v}/projects").json()[0]["name"] == "pktx2"

    r = client.delete(f"/api/resumes/{v}/projects/entries/{eid}")
    assert r.status_code == 200
    assert client.get(f"/api/resumes/{v}/projects").json() == []


def test_error_mapping(client) -> None:
    v = client.vid
    assert client.post(f"/api/resumes/{v}/bogus/entries", json={}).status_code == 400
    assert (
        client.post(
            f"/api/resumes/{v}/projects/entries", json={"name": "x", "url": "ftp://x"}
        ).status_code
        == 422
    )
    assert client.delete(f"/api/resumes/{v}/projects/entries/nope").status_code == 404
    assert client.delete(f"/api/resumes/{v}/projects/entries/7").status_code == 404
    assert client.get(f"/api/resumes/{v}/custom:zzz").status_code == 404


def test_layout_and_resume_payload(client) -> None:
    v = client.vid
    r = client.put(
        f"/api/resumes/{v}/layout",
        json={"layout": [{"section": "skills", "visible": False, "title": "Tech"}]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["layout"][0] == {
        "section": "skills",
        "visible": False,
        "title": "Tech",
    }
    detail = client.get(f"/api/resumes/{v}").json()["resume_data"]
    assert detail["layout"][0]["section"] == "skills"
    assert "projects" in detail and "custom_sections" in detail
    assert (
        client.put(
            f"/api/resumes/{v}/layout", json={"layout": [{"section": "x"}]}
        ).status_code
        == 422
    )


def test_custom_section_lifecycle(client) -> None:
    v = client.vid
    r = client.post(f"/api/resumes/{v}/custom-sections", json={"title": "Talks"})
    assert r.status_code == 201
    key = r.json()["section"]
    assert (
        client.post(
            f"/api/resumes/{v}/{key}/entries", json={"heading": "KubeCon"}
        ).status_code
        == 201
    )
    assert client.get(f"/api/resumes/{v}/{key}").json()[0]["heading"] == "KubeCon"
    detail = client.get(f"/api/resumes/{v}").json()["resume_data"]
    assert detail["custom_sections"][key.split(":")[1]]["title"] == "Talks"

    r = client.delete(f"/api/resumes/{v}/custom-sections/{key.split(':')[1]}")
    assert r.status_code == 200
    assert client.get(f"/api/resumes/{v}/{key}").status_code == 404


def test_export_includes_new_sections(client) -> None:
    v = client.vid
    client.post(f"/api/resumes/{v}/awards/entries", json={"title": "Best"})
    client.post(f"/api/resumes/{v}/custom-sections", json={"title": "Extra"})
    export = client.get("/api/export").json()
    data = export["resumes"][0]["resume_data"]
    assert data["awards"][0]["title"] == "Best" and data["awards"][0]["id"]
    assert data["layout"] and data["custom_sections"]
