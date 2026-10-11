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
    sections = {s["key"]: s for s in r.json()}
    assert "projects" in sections and "custom" not in sections
    assert sections["projects"]["optional"] is True
    assert sections["experience"]["optional"] is False


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
    assert client.get(f"/api/resumes/{v}/bogus").status_code == 404


def test_optional_section_lifecycle(client) -> None:
    v = client.vid
    put = lambda section, enabled: client.put(  # noqa: E731
        f"/api/resumes/{v}/sections/{section}", json={"enabled": enabled}
    )
    assert put("projects", True).status_code == 200
    data = client.get(f"/api/resumes/{v}").json()["resume_data"]
    assert data["enabled_sections"] == ["projects"]
    assert put("projects", False).status_code == 200
    assert (
        client.get(f"/api/resumes/{v}").json()["resume_data"]["enabled_sections"] == []
    )

    client.post(f"/api/resumes/{v}/awards/entries", json={"title": "Best"})
    assert put("awards", False).status_code == 422  # has entries
    assert put("skills", False).status_code == 422  # core
    assert put("bogus", True).status_code == 422


def test_export_includes_new_sections(client) -> None:
    v = client.vid
    client.post(f"/api/resumes/{v}/awards/entries", json={"title": "Best"})
    export = client.get("/api/export").json()
    data = export["resumes"][0]["resume_data"]
    assert data["awards"][0]["title"] == "Best" and data["awards"][0]["id"]
    assert data["enabled_sections"] == ["awards"]
