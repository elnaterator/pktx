"""Route-wide user-scoping guard (027).

Enumerates EVERY API route on the app and calls it as bob, aimed at alice's
resources. Asserts bob can neither see nor change anything alice owns:

- routes addressing an alice resource by id → 404 (no 403 existence oracle)
- list / tags / search / export routes → no alice marker in the response
- afterwards, alice's rows are byte-for-byte unchanged

A new route that this file does not know how to call fails the test, so new
routes cannot silently skip the check — add it to ``_CASES`` or ``_EXEMPT``.
"""

import json
from typing import Any

from fastapi.routing import APIRoute

from tests.conftest import ALICE, ALICE_MARKER, BOB, snapshot_user_rows
from tests.helpers import build_full_app, user_client

# Routes bob may legitimately call that cannot touch alice's data.
_EXEMPT: set[tuple[str, str]] = {
    ("GET", "/health"),
    ("POST", "/api/webhooks/clerk"),
    # Collection creates make bob-owned rows only.
    ("POST", "/api/resumes"),
    ("POST", "/api/applications"),
    ("POST", "/api/accomplishments"),
    ("POST", "/api/notes"),
    ("POST", "/api/contacts"),
    # Catch-all: unknown /api paths always 404, never touch data.
    ("GET", "/api/{path:path}"),
    ("POST", "/api/{path:path}"),
    ("PUT", "/api/{path:path}"),
    ("PATCH", "/api/{path:path}"),
    ("DELETE", "/api/{path:path}"),
}

# Routes with no alice id in the path: response body must not leak alice data.
_LEAK_CHECK: set[tuple[str, str]] = {
    ("GET", "/api/resumes"),
    ("GET", "/api/resumes/tags"),
    ("GET", "/api/resumes/default"),
    ("GET", "/api/applications"),
    ("GET", "/api/applications/tags"),
    ("GET", "/api/accomplishments"),
    ("GET", "/api/accomplishments/tags"),
    ("GET", "/api/notes"),
    ("GET", "/api/notes/tags"),
    ("GET", "/api/contacts"),
    ("GET", "/api/contacts/tags"),
    ("GET", "/api/communications"),
    ("GET", "/api/tags"),
    ("GET", "/api/search"),
    ("GET", "/api/export"),
}


def _cases(ids: dict[str, Any]) -> dict[tuple[str, str], tuple[str, Any]]:
    """(method, route path) → (concrete url, json body) aimed at alice's ids.

    Bodies are valid so a 404 proves the ownership check, not input validation.
    """
    r, a, c = ids["resume_id"], ids["app_id"], ids["acc_id"]
    n, ct, cm = ids["note_id"], ids["contact_id"], ids["comm_id"]
    exp = {"title": "x", "company": "y"}
    comm = {"type": "email", "direction": "sent", "body": "b", "date": "2024-01-01"}
    link = {"a_type": "note", "a_id": n, "b_type": "contact", "b_id": ct}
    return {
        ("GET", "/api/resumes/{version_id}"): (f"/api/resumes/{r}", None),
        ("PATCH", "/api/resumes/{version_id}"): (f"/api/resumes/{r}", {"label": "x"}),
        ("DELETE", "/api/resumes/{version_id}"): (f"/api/resumes/{r}", None),
        ("POST", "/api/resumes/{version_id}/default"): (
            f"/api/resumes/{r}/default",
            None,
        ),
        ("GET", "/api/resumes/{version_id}/{section}"): (
            f"/api/resumes/{r}/summary",
            None,
        ),
        ("PUT", "/api/resumes/{version_id}/contact"): (
            f"/api/resumes/{r}/contact",
            {"name": "x"},
        ),
        ("PUT", "/api/resumes/{version_id}/summary"): (
            f"/api/resumes/{r}/summary",
            {"text": "x"},
        ),
        ("POST", "/api/resumes/{version_id}/{section}/entries"): (
            f"/api/resumes/{r}/experience/entries",
            exp,
        ),
        ("PUT", "/api/resumes/{version_id}/{section}/entries/{index}"): (
            f"/api/resumes/{r}/experience/entries/0",
            {"title": "x"},
        ),
        ("DELETE", "/api/resumes/{version_id}/{section}/entries/{index}"): (
            f"/api/resumes/{r}/experience/entries/0",
            None,
        ),
        ("GET", "/api/applications/{app_id}"): (f"/api/applications/{a}", None),
        ("PATCH", "/api/applications/{app_id}"): (
            f"/api/applications/{a}",
            {"company": "x"},
        ),
        ("DELETE", "/api/applications/{app_id}"): (f"/api/applications/{a}", None),
        ("GET", "/api/applications/{app_id}/context"): (
            f"/api/applications/{a}/context",
            None,
        ),
        ("GET", "/api/accomplishments/{acc_id}"): (f"/api/accomplishments/{c}", None),
        ("PATCH", "/api/accomplishments/{acc_id}"): (
            f"/api/accomplishments/{c}",
            {"title": "x"},
        ),
        ("DELETE", "/api/accomplishments/{acc_id}"): (
            f"/api/accomplishments/{c}",
            None,
        ),
        ("GET", "/api/notes/{note_id}"): (f"/api/notes/{n}", None),
        ("PATCH", "/api/notes/{note_id}"): (f"/api/notes/{n}", {"title": "x"}),
        ("DELETE", "/api/notes/{note_id}"): (f"/api/notes/{n}", None),
        ("GET", "/api/contacts/{contact_id}"): (f"/api/contacts/{ct}", None),
        ("PATCH", "/api/contacts/{contact_id}"): (
            f"/api/contacts/{ct}",
            {"name": "x"},
        ),
        ("DELETE", "/api/contacts/{contact_id}"): (f"/api/contacts/{ct}", None),
        ("GET", "/api/contacts/{cid}/communications"): (
            f"/api/contacts/{ct}/communications",
            None,
        ),
        ("POST", "/api/contacts/{cid}/communications"): (
            f"/api/contacts/{ct}/communications",
            comm,
        ),
        ("PATCH", "/api/contacts/{cid}/communications/{cmid}"): (
            f"/api/contacts/{ct}/communications/{cm}",
            {"subject": "x"},
        ),
        ("DELETE", "/api/contacts/{cid}/communications/{cmid}"): (
            f"/api/contacts/{ct}/communications/{cm}",
            None,
        ),
        ("POST", "/api/links"): ("/api/links", link),
        # Unlinking alice's link as bob must be a no-op (snapshot proves it).
        ("DELETE", "/api/links"): ("/api/links", link),
    }


# Routes whose bob-call is allowed to "succeed" because it is a scoped no-op.
_NOOP_OK: set[tuple[str, str]] = {("DELETE", "/api/links")}


def _walk(routes: list[Any]) -> list[APIRoute]:
    """Flatten routes, descending into included routers.

    FastAPI ≥0.14x wraps ``include_router`` results in an ``_IncludedRouter``
    exposing the source router as ``original_router`` (routers here are
    included without a prefix, so route paths are already absolute).
    """
    out: list[APIRoute] = []
    for route in routes:
        if isinstance(route, APIRoute):
            out.append(route)
        elif hasattr(route, "original_router"):
            out.extend(_walk(route.original_router.routes))
    return out


def _api_routes(app: Any) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for route in _walk(app.routes):
        for method in sorted((route.methods or set()) - {"HEAD", "OPTIONS"}):
            out.append((method, route.path))
    return out


def test_route_walker_finds_routes(two_users: dict[str, Any]) -> None:
    """Guard the guard: the walker must actually see the API surface."""
    keys = _api_routes(build_full_app(two_users["conn"]))
    assert ("GET", "/api/resumes/{version_id}") in keys
    assert len(keys) > 40


def test_every_route_is_user_scoped(two_users: dict[str, Any]) -> None:
    conn = two_users["conn"]
    app = build_full_app(conn)
    bob = user_client(app, BOB)
    cases = _cases(two_users)
    before = snapshot_user_rows(conn, ALICE)

    unknown: list[tuple[str, str]] = []
    failures: list[str] = []

    for key in _api_routes(app):
        method, path = key
        if key in _EXEMPT:
            continue
        if key in _LEAK_CHECK:
            resp = bob.request(method, path)
            if ALICE_MARKER in resp.text:
                failures.append(f"{method} {path} leaked alice data: {resp.text[:200]}")
            continue
        if key not in cases:
            unknown.append(key)
            continue
        url, body = cases[key]
        resp = (
            bob.request(method, url, json=body)
            if body is not None
            else bob.request(method, url)
        )
        if key in _NOOP_OK:
            if resp.status_code >= 500:
                failures.append(f"{method} {url} → {resp.status_code}")
            continue
        if resp.status_code != 404:
            failures.append(
                f"{method} {url} → {resp.status_code} (want 404): {resp.text[:200]}"
            )
        if ALICE_MARKER in resp.text:
            failures.append(f"{method} {url} leaked alice data in error body")

    after = snapshot_user_rows(conn, ALICE)

    assert not unknown, f"routes missing from scoping test: {unknown}"
    assert not failures, "\n".join(failures)
    assert json.dumps(before, default=str) == json.dumps(after, default=str), (
        "bob's requests modified alice's rows"
    )
