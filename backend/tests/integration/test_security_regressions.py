"""Regression tests for the 027 security review findings (C1–C3, H5).

Each test failed before its fix. See research/security-review.md.
"""

import inspect
from typing import Any

import pytest

import pktx.database as database
from tests.conftest import ALICE, ALICE_MARKER, BOB
from tests.helpers import build_full_app, user_client

# ---------------------------------------------------------------------------
# C1 — legacy unscoped /api/resume* routes are gone
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "url", "body"),
    [
        ("GET", "/api/resume", None),
        ("GET", "/api/resume/summary", None),
        ("PUT", "/api/resume/contact", {"name": "x"}),
        ("PUT", "/api/resume/summary", {"text": "x"}),
        ("POST", "/api/resume/experience/entries", {"title": "x", "company": "y"}),
        ("PUT", "/api/resume/experience/entries/0", {"title": "x"}),
        ("DELETE", "/api/resume/experience/entries/0", None),
    ],
)
def test_legacy_resume_routes_removed(
    two_users: dict[str, Any], method: str, url: str, body: Any
) -> None:
    bob = user_client(build_full_app(two_users["conn"]), BOB)
    resp = bob.request(method, url, json=body) if body else bob.request(method, url)
    assert resp.status_code == 404
    assert ALICE_MARKER not in resp.text


# ---------------------------------------------------------------------------
# C2 — user scoping fails closed: no data-layer function defaults user_id
# ---------------------------------------------------------------------------


def _public_functions_with_user_id() -> list[tuple[str, inspect.Parameter]]:
    out = []
    for name, fn in inspect.getmembers(database, inspect.isfunction):
        if name.startswith("_") or fn.__module__ != database.__name__:
            continue
        param = inspect.signature(fn).parameters.get("user_id")
        if param is not None:
            out.append((name, param))
    return out


def test_database_user_id_is_required_everywhere() -> None:
    offenders = [
        name
        for name, param in _public_functions_with_user_id()
        if param.default is not inspect.Parameter.empty
        or "None" in str(param.annotation)
    ]
    assert not offenders, f"user_id optional/nullable in: {offenders}"


# ---------------------------------------------------------------------------
# C3 — accomplishment tags are scoped to the caller
# ---------------------------------------------------------------------------


def test_accomplishment_tags_do_not_leak(two_users: dict[str, Any]) -> None:
    bob = user_client(build_full_app(two_users["conn"]), BOB)
    resp = bob.get("/api/accomplishments/tags")
    assert resp.status_code == 200
    assert ALICE_MARKER not in resp.json()


def test_accomplishment_tags_visible_to_owner(two_users: dict[str, Any]) -> None:
    alice = user_client(build_full_app(two_users["conn"]), ALICE)
    assert ALICE_MARKER in alice.get("/api/accomplishments/tags").json()


# ---------------------------------------------------------------------------
# H5 — resume delete works on an autocommit (production-mode) connection
# ---------------------------------------------------------------------------


def _seed_autocommit_user(conn: Any, uid: str) -> tuple[int, int]:
    from pktx.resume_service import ResumeService

    conn.execute("INSERT INTO users (id) VALUES (%s)", (uid,))
    svc = ResumeService(conn)
    first = svc.create_resume("first", user_id=uid)
    second = svc.create_resume("second", user_id=uid)
    svc.set_default(first["id"], user_id=uid)
    return first["id"], second["id"]


def test_delete_non_default_resume_autocommit(autocommit_conn: Any) -> None:
    from pktx.resume_service import ResumeService

    first, second = _seed_autocommit_user(autocommit_conn, "ac_del1")
    ResumeService(autocommit_conn).delete_resume(second, user_id="ac_del1")
    remaining = autocommit_conn.execute(
        "SELECT id, is_default FROM resume_version WHERE user_id = 'ac_del1'"
    ).fetchall()
    assert [(r["id"], r["is_default"]) for r in remaining] == [(first, 1)]


def test_delete_default_resume_promotes_autocommit(autocommit_conn: Any) -> None:
    from pktx.resume_service import ResumeService

    first, second = _seed_autocommit_user(autocommit_conn, "ac_del2")
    ResumeService(autocommit_conn).delete_resume(first, user_id="ac_del2")
    remaining = autocommit_conn.execute(
        "SELECT id, is_default FROM resume_version WHERE user_id = 'ac_del2'"
    ).fetchall()
    assert [(r["id"], r["is_default"]) for r in remaining] == [(second, 1)]
