"""Contract tests for accomplishment REST API and MCP tools.

Tests are grouped by user story. Each story's MCP contract tests appear
BEFORE the tool implementations (TDD per Constitution III).
"""

import asyncio
from collections.abc import Generator
from typing import Any

import psycopg
import pytest
from fastmcp.exceptions import ToolError
from psycopg import Connection
from starlette.testclient import TestClient

from pktx.auth import current_user_id_var

# ── Shared fixtures ───────────────────────────────────────────────────────────

_TEST_USER = "test_user"


@pytest.fixture(autouse=True)
def _set_user_context() -> Generator[None, None, None]:
    """Set current_user_id_var for MCP tool handler tests."""
    token = current_user_id_var.set(_TEST_USER)
    try:
        yield
    finally:
        current_user_id_var.reset(token)


@pytest.fixture
def acc_service(db_conn: Connection[Any]) -> Any:
    """AccomplishmentService for use in MCP tool tests."""
    from pktx.accomplishment_service import AccomplishmentService

    # Seed the test user
    db_conn.execute(
        "INSERT INTO users (id, email) VALUES (%s, 'test@test.com') "
        "ON CONFLICT (id) DO NOTHING",
        (_TEST_USER,),
    )

    return AccomplishmentService(db_conn)  # type: ignore[arg-type]


def _make_acc_client(db_conn: Connection[Any]) -> TestClient:
    """TestClient with accomplishment routes enabled."""
    from fastapi import FastAPI

    from pktx.accomplishment_service import AccomplishmentService
    from pktx.api.routes import create_router
    from pktx.resume_service import ResumeService

    svc = ResumeService(db_conn)  # type: ignore[arg-type]
    app_acc_svc = AccomplishmentService(db_conn)  # type: ignore[arg-type]
    app = FastAPI()
    app.include_router(create_router(svc, acc_service=app_acc_svc))
    return TestClient(app)


# ── US1: Record a New Accomplishment ─────────────────────────────────────────


class TestMCPCreateGetAccomplishment:
    """T008 — MCP contract tests for create_accomplishment + get_accomplishment."""

    def test_create_returns_accomplishment(self, acc_service: Any) -> None:
        from fastmcp import FastMCP

        from pktx.tools.accomplishment_tools import register_accomplishment_tools

        mcp = FastMCP("test")
        register_accomplishment_tools(mcp, lambda: acc_service)

        # Call the underlying function directly
        tool_fn = _get_tool_fn(mcp, "create_accomplishment")
        result = tool_fn(
            title="Led platform migration",
            situation="Monolith",
            task="",
            action="",
            result="",
            accomplishment_date=None,
            tags=[],
        )
        assert result["title"] == "Led platform migration"
        assert result["situation"] == "Monolith"
        assert isinstance(result["id"], int)

    def test_create_missing_title_raises(self, acc_service: Any) -> None:
        from fastmcp import FastMCP

        from pktx.tools.accomplishment_tools import register_accomplishment_tools

        mcp = FastMCP("test")
        register_accomplishment_tools(mcp, lambda: acc_service)

        tool_fn = _get_tool_fn(mcp, "create_accomplishment")
        with pytest.raises(ToolError):
            tool_fn(
                title="",
                situation="",
                task="",
                action="",
                result="",
                accomplishment_date=None,
                tags=[],
            )

    def test_get_returns_accomplishment_dict(self, acc_service: Any) -> None:
        from fastmcp import FastMCP

        from pktx.tools.accomplishment_tools import register_accomplishment_tools

        mcp = FastMCP("test")
        register_accomplishment_tools(mcp, lambda: acc_service)

        create_fn = _get_tool_fn(mcp, "create_accomplishment")
        get_fn = _get_tool_fn(mcp, "get_accomplishment")

        create_fn(
            title="Test acc",
            situation="",
            task="",
            action="",
            result="",
            accomplishment_date=None,
            tags=[],
        )
        # Get ID from the service
        accs = acc_service.list_accomplishments(user_id=_TEST_USER)
        assert len(accs) == 1
        acc_id = accs[0]["id"]

        result = get_fn(id=acc_id)
        assert isinstance(result, dict)
        assert result["title"] == "Test acc"

    def test_get_unknown_id_raises(self, acc_service: Any) -> None:
        from fastmcp import FastMCP

        from pktx.tools.accomplishment_tools import register_accomplishment_tools

        mcp = FastMCP("test")
        register_accomplishment_tools(mcp, lambda: acc_service)

        tool_fn = _get_tool_fn(mcp, "get_accomplishment")
        with pytest.raises(ToolError):
            tool_fn(id=9999)


class TestRESTCreateGetAccomplishment:
    """T007 — REST contract tests for POST + GET /api/accomplishments/{id}."""

    def test_post_valid_returns_201(self, db_conn: Connection[Any]) -> None:
        client = _make_acc_client(db_conn)
        resp = client.post(
            "/api/accomplishments",
            json={"title": "Led migration", "situation": "Slow deploys"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Led migration"
        assert data["situation"] == "Slow deploys"
        assert "id" in data

    def test_post_missing_title_returns_422(self, db_conn: Connection[Any]) -> None:
        client = _make_acc_client(db_conn)
        resp = client.post("/api/accomplishments", json={"situation": "No title"})
        assert resp.status_code == 422

    def test_get_by_id_returns_full_record(self, db_conn: Connection[Any]) -> None:
        client = _make_acc_client(db_conn)
        created = client.post(
            "/api/accomplishments",
            json={"title": "Test", "result": "Great outcome"},
        ).json()
        resp = client.get(f"/api/accomplishments/{created['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == created["id"]
        assert data["result"] == "Great outcome"

    def test_get_unknown_id_returns_404(self, db_conn: Connection[Any]) -> None:
        client = _make_acc_client(db_conn)
        resp = client.get("/api/accomplishments/9999")
        assert resp.status_code == 404


# ── US2: View and Browse Accomplishments ─────────────────────────────────────


class TestMCPListAccomplishments:
    """T020 — MCP contract test for list_accomplishments tool."""

    def test_list_no_args_returns_summaries(self, acc_service: Any) -> None:
        from fastmcp import FastMCP

        from pktx.tools.accomplishment_tools import register_accomplishment_tools

        mcp = FastMCP("test")
        register_accomplishment_tools(mcp, lambda: acc_service)

        acc_service.create_accomplishment(
            {"title": "A", "tags": ["leadership"]}, user_id=_TEST_USER
        )
        acc_service.create_accomplishment(
            {"title": "B", "tags": ["technical"]}, user_id=_TEST_USER
        )

        list_fn = _get_tool_fn(mcp, "list_accomplishments")
        result = list_fn(tag=None, q=None)
        assert isinstance(result, list)
        assert len(result) == 2
        # Summary shape — no STAR body
        for item in result:
            assert "situation" not in item
            assert "title" in item

    def test_list_with_tag_returns_matching(self, acc_service: Any) -> None:
        from fastmcp import FastMCP

        from pktx.tools.accomplishment_tools import register_accomplishment_tools

        mcp = FastMCP("test")
        register_accomplishment_tools(mcp, lambda: acc_service)

        acc_service.create_accomplishment(
            {"title": "Leader", "tags": ["leadership"]}, user_id=_TEST_USER
        )
        acc_service.create_accomplishment(
            {"title": "Coder", "tags": ["technical"]}, user_id=_TEST_USER
        )

        list_fn = _get_tool_fn(mcp, "list_accomplishments")
        result = list_fn(tag="leadership", q=None)
        assert len(result) == 1
        assert result[0]["title"] == "Leader"

    def test_list_empty_returns_empty_list(self, acc_service: Any) -> None:
        from fastmcp import FastMCP

        from pktx.tools.accomplishment_tools import register_accomplishment_tools

        mcp = FastMCP("test")
        register_accomplishment_tools(mcp, lambda: acc_service)

        list_fn = _get_tool_fn(mcp, "list_accomplishments")
        result = list_fn(tag=None, q=None)
        assert result == []

    def test_list_no_match_returns_empty_not_error(self, acc_service: Any) -> None:
        from fastmcp import FastMCP

        from pktx.tools.accomplishment_tools import register_accomplishment_tools

        mcp = FastMCP("test")
        register_accomplishment_tools(mcp, lambda: acc_service)

        acc_service.create_accomplishment(
            {"title": "A", "tags": ["technical"]}, user_id=_TEST_USER
        )
        list_fn = _get_tool_fn(mcp, "list_accomplishments")
        result = list_fn(tag="nonexistent", q=None)
        assert result == []


class TestRESTListTagsAccomplishments:
    """T019 — REST contract tests for GET /api/accomplishments and /tags."""

    def test_list_returns_summaries(self, db_conn: Connection[Any]) -> None:
        client = _make_acc_client(db_conn)
        client.post("/api/accomplishments", json={"title": "A"})
        client.post("/api/accomplishments", json={"title": "B"})
        resp = client.get("/api/accomplishments")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        # Summary shape
        for item in data:
            assert "situation" not in item
            assert "title" in item

    def test_list_empty_returns_empty_array(self, db_conn: Connection[Any]) -> None:
        client = _make_acc_client(db_conn)
        resp = client.get("/api/accomplishments")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_filter_by_tag(self, db_conn: Connection[Any]) -> None:
        client = _make_acc_client(db_conn)
        client.post(
            "/api/accomplishments", json={"title": "Leader", "tags": ["leadership"]}
        )
        client.post(
            "/api/accomplishments", json={"title": "Coder", "tags": ["technical"]}
        )
        resp = client.get("/api/accomplishments?tag=leadership")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Leader"

    def test_list_tag_no_match_empty_not_error(
        self, db_conn: psycopg.Connection
    ) -> None:
        client = _make_acc_client(db_conn)
        client.post("/api/accomplishments", json={"title": "A", "tags": ["technical"]})
        resp = client.get("/api/accomplishments?tag=nonexistent")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_tags_returns_sorted_unique_list(
        self, db_conn: psycopg.Connection
    ) -> None:
        client = _make_acc_client(db_conn)
        client.post(
            "/api/accomplishments",
            json={"title": "A", "tags": ["technical", "leadership"]},
        )
        client.post("/api/accomplishments", json={"title": "B", "tags": ["leadership"]})
        resp = client.get("/api/accomplishments/tags")
        assert resp.status_code == 200
        tags = resp.json()
        assert isinstance(tags, list)
        assert set(tags) == {"technical", "leadership"}
        assert tags == sorted(tags)

    def test_get_tags_empty_when_no_accomplishments(
        self, db_conn: psycopg.Connection
    ) -> None:
        client = _make_acc_client(db_conn)
        resp = client.get("/api/accomplishments/tags")
        assert resp.status_code == 200
        assert resp.json() == []


class TestRESTMultiTagFilterAccomplishments:
    """REST contract tests for multi-tag AND filter on GET /api/accomplishments."""

    def test_multi_tag_and_returns_intersection(self, db_conn: Connection[Any]) -> None:
        client = _make_acc_client(db_conn)
        client.post(
            "/api/accomplishments",
            json={"title": "Both", "tags": ["leadership", "technical"]},
        )
        client.post(
            "/api/accomplishments",
            json={"title": "Leader only", "tags": ["leadership"]},
        )
        client.post(
            "/api/accomplishments", json={"title": "Tech only", "tags": ["technical"]}
        )
        resp = client.get("/api/accomplishments?tag=leadership&tag=technical")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Both"

    def test_single_tag_param_still_works(self, db_conn: Connection[Any]) -> None:
        client = _make_acc_client(db_conn)
        client.post(
            "/api/accomplishments", json={"title": "Leader", "tags": ["leadership"]}
        )
        client.post(
            "/api/accomplishments", json={"title": "Coder", "tags": ["technical"]}
        )
        resp = client.get("/api/accomplishments?tag=leadership")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Leader"

    def test_no_tag_params_returns_all(self, db_conn: Connection[Any]) -> None:
        client = _make_acc_client(db_conn)
        client.post("/api/accomplishments", json={"title": "A", "tags": ["leadership"]})
        client.post("/api/accomplishments", json={"title": "B", "tags": ["technical"]})
        resp = client.get("/api/accomplishments")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


# ── US3: Edit ─────────────────────────────────────────────────────────────────


class TestMCPUpdateAccomplishment:
    """T032 — MCP contract test for update_accomplishment tool."""

    def test_partial_update_returns_accomplishment(self, acc_service: Any) -> None:
        from fastmcp import FastMCP

        from pktx.tools.accomplishment_tools import register_accomplishment_tools

        mcp = FastMCP("test")
        register_accomplishment_tools(mcp, lambda: acc_service)

        created = acc_service.create_accomplishment(
            {"title": "Original"}, user_id=_TEST_USER
        )
        update_fn = _get_tool_fn(mcp, "update_accomplishment")
        result = update_fn(
            id=created["id"],
            title=None,
            situation=None,
            task=None,
            action=None,
            result="New result",
            accomplishment_date=None,
            tags=None,
        )
        assert result["id"] == created["id"]
        assert result["title"] == "Original"
        assert result["result"] == "New result"

    def test_unknown_id_raises(self, acc_service: Any) -> None:
        from fastmcp import FastMCP

        from pktx.tools.accomplishment_tools import register_accomplishment_tools

        mcp = FastMCP("test")
        register_accomplishment_tools(mcp, lambda: acc_service)

        update_fn = _get_tool_fn(mcp, "update_accomplishment")
        with pytest.raises(ToolError):
            update_fn(
                id=9999,
                title=None,
                situation=None,
                task=None,
                action=None,
                result="x",
                accomplishment_date=None,
                tags=None,
            )

    def test_blank_title_raises(self, acc_service: Any) -> None:
        from fastmcp import FastMCP

        from pktx.tools.accomplishment_tools import register_accomplishment_tools

        mcp = FastMCP("test")
        register_accomplishment_tools(mcp, lambda: acc_service)

        created = acc_service.create_accomplishment(
            {"title": "Original"}, user_id=_TEST_USER
        )
        update_fn = _get_tool_fn(mcp, "update_accomplishment")
        with pytest.raises(ToolError):
            update_fn(
                id=created["id"],
                title="",
                situation=None,
                task=None,
                action=None,
                result=None,
                accomplishment_date=None,
                tags=None,
            )


class TestRESTUpdateAccomplishment:
    """T031 — REST contract test for PATCH /api/accomplishments/{id}."""

    def test_patch_returns_200_with_updated_record(
        self, db_conn: psycopg.Connection
    ) -> None:
        client = _make_acc_client(db_conn)
        created = client.post(
            "/api/accomplishments",
            json={"title": "Original", "situation": "Old situation"},
        ).json()
        resp = client.patch(
            f"/api/accomplishments/{created['id']}",
            json={"result": "Updated result"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"] == "Updated result"
        assert data["situation"] == "Old situation"

    def test_patch_unknown_id_returns_404(self, db_conn: Connection[Any]) -> None:
        client = _make_acc_client(db_conn)
        resp = client.patch("/api/accomplishments/9999", json={"result": "x"})
        assert resp.status_code == 404

    def test_patch_blank_title_returns_422(self, db_conn: Connection[Any]) -> None:
        client = _make_acc_client(db_conn)
        created = client.post("/api/accomplishments", json={"title": "Original"}).json()
        resp = client.patch(f"/api/accomplishments/{created['id']}", json={"title": ""})
        assert resp.status_code == 422


# ── US4: Delete ───────────────────────────────────────────────────────────────


class TestMCPDeleteAccomplishment:
    """T041 — MCP contract test for delete_accomplishment tool."""

    def test_delete_returns_id_and_title(self, acc_service: Any) -> None:
        from fastmcp import FastMCP

        from pktx.tools.accomplishment_tools import register_accomplishment_tools

        mcp = FastMCP("test")
        register_accomplishment_tools(mcp, lambda: acc_service)

        created = acc_service.create_accomplishment(
            {"title": "Delete me"}, user_id=_TEST_USER
        )
        delete_fn = _get_tool_fn(mcp, "delete_accomplishment")
        result = delete_fn(id=created["id"])
        assert result == {"id": created["id"], "title": "Delete me"}

    def test_delete_unknown_id_raises(self, acc_service: Any) -> None:
        from fastmcp import FastMCP

        from pktx.tools.accomplishment_tools import register_accomplishment_tools

        mcp = FastMCP("test")
        register_accomplishment_tools(mcp, lambda: acc_service)

        delete_fn = _get_tool_fn(mcp, "delete_accomplishment")
        with pytest.raises(ToolError):
            delete_fn(id=9999)


class TestRESTDeleteAccomplishment:
    """T040 — REST contract test for DELETE /api/accomplishments/{id}."""

    def test_delete_returns_200_with_message(self, db_conn: Connection[Any]) -> None:
        client = _make_acc_client(db_conn)
        created = client.post(
            "/api/accomplishments", json={"title": "Delete me"}
        ).json()
        resp = client.delete(f"/api/accomplishments/{created['id']}")
        assert resp.status_code == 200
        assert "message" in resp.json()

    def test_deleted_not_retrievable(self, db_conn: Connection[Any]) -> None:
        client = _make_acc_client(db_conn)
        created = client.post("/api/accomplishments", json={"title": "Gone"}).json()
        client.delete(f"/api/accomplishments/{created['id']}")
        resp = client.get(f"/api/accomplishments/{created['id']}")
        assert resp.status_code == 404

    def test_second_delete_returns_404(self, db_conn: Connection[Any]) -> None:
        client = _make_acc_client(db_conn)
        created = client.post("/api/accomplishments", json={"title": "Gone"}).json()
        client.delete(f"/api/accomplishments/{created['id']}")
        resp = client.delete(f"/api/accomplishments/{created['id']}")
        assert resp.status_code == 404

    def test_delete_unknown_returns_404(self, db_conn: Connection[Any]) -> None:
        client = _make_acc_client(db_conn)
        resp = client.delete("/api/accomplishments/9999")
        assert resp.status_code == 404


# ── US5: MCP cross-tool integration ──────────────────────────────────────────


class TestMCPCrossToolIntegration:
    """T048 — MCP cross-tool integration tests."""

    def test_create_list_update_delete_sequence(self, acc_service: Any) -> None:
        from fastmcp import FastMCP

        from pktx.tools.accomplishment_tools import register_accomplishment_tools

        mcp = FastMCP("test")
        register_accomplishment_tools(mcp, lambda: acc_service)

        create_fn = _get_tool_fn(mcp, "create_accomplishment")
        list_fn = _get_tool_fn(mcp, "list_accomplishments")
        update_fn = _get_tool_fn(mcp, "update_accomplishment")
        delete_fn = _get_tool_fn(mcp, "delete_accomplishment")
        get_fn = _get_tool_fn(mcp, "get_accomplishment")

        # Create
        create_result = create_fn(
            title="Cross-tool test",
            situation="",
            task="",
            action="",
            result="",
            accomplishment_date=None,
            tags=[],
        )
        acc_id = create_result["id"]

        # List — entry appears
        list_result = list_fn(tag=None, q=None)
        assert [a["id"] for a in list_result] == [acc_id]

        # Update
        update_result = update_fn(
            id=acc_id,
            title=None,
            situation=None,
            task=None,
            action=None,
            result="Updated",
            accomplishment_date=None,
            tags=None,
        )
        assert update_result["result"] == "Updated"

        # List — verify update reflected (via get)
        get_result = get_fn(id=acc_id)
        assert get_result["result"] == "Updated"

        # Delete
        delete_result = delete_fn(id=acc_id)
        assert delete_result == {"id": acc_id, "title": "Cross-tool test"}

        # List — entry gone
        list_after = list_fn(tag=None, q=None)
        assert list_after == []

    def test_all_errors_raise_tool_error(self, acc_service: Any) -> None:
        from fastmcp import FastMCP

        from pktx.tools.accomplishment_tools import register_accomplishment_tools

        mcp = FastMCP("test")
        register_accomplishment_tools(mcp, lambda: acc_service)

        get_fn = _get_tool_fn(mcp, "get_accomplishment")
        update_fn = _get_tool_fn(mcp, "update_accomplishment")
        delete_fn = _get_tool_fn(mcp, "delete_accomplishment")
        create_fn = _get_tool_fn(mcp, "create_accomplishment")

        calls = [
            lambda: get_fn(id=9999),
            lambda: update_fn(
                id=9999,
                title=None,
                situation=None,
                task=None,
                action=None,
                result="x",
                accomplishment_date=None,
                tags=None,
            ),
            lambda: delete_fn(id=9999),
            lambda: create_fn(
                title="",
                situation="",
                task="",
                action="",
                result="",
                accomplishment_date=None,
                tags=[],
            ),
        ]
        for call in calls:
            with pytest.raises(ToolError):
                call()


# ── Helper ────────────────────────────────────────────────────────────────────


def _get_tool_fn(mcp: Any, name: str) -> Any:
    """Extract a registered MCP tool function by name for direct testing."""
    tools = asyncio.run(mcp.list_tools())
    for tool in tools:
        if tool.name == name:
            return tool.fn
    registered = [t.name for t in tools]
    raise KeyError(f"MCP tool '{name}' not found. Registered: {registered}")
