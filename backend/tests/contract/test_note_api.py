"""Contract tests for note REST API and MCP tools."""

import asyncio
from collections.abc import Generator
from typing import Any

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
def note_service(db_conn: Connection[Any]) -> Any:
    """NoteService for use in MCP tool tests."""
    from pktx.note_service import NoteService

    # Seed the test user
    db_conn.execute(
        "INSERT INTO users (id, email) VALUES (%s, 'test@test.com') "
        "ON CONFLICT (id) DO NOTHING",
        (_TEST_USER,),
    )

    return NoteService(db_conn)  # type: ignore[arg-type]


def _make_note_client(db_conn: Connection[Any]) -> TestClient:
    """TestClient with note routes enabled."""
    from fastapi import FastAPI

    from pktx.api.routes import create_router
    from pktx.note_service import NoteService
    from pktx.resume_service import ResumeService

    svc = ResumeService(db_conn)  # type: ignore[arg-type]
    note_svc = NoteService(db_conn)  # type: ignore[arg-type]
    app = FastAPI()
    app.include_router(create_router(svc, note_service=note_svc))
    return TestClient(app)


# ── US1: Create and View Notes ───────────────────────────────────────────────


class TestRESTCreateGetNote:
    """REST contract tests for POST + GET /api/notes."""

    def test_post_valid_returns_201(self, db_conn: Connection[Any]) -> None:
        client = _make_note_client(db_conn)
        resp = client.post(
            "/api/notes",
            json={"title": "Python patterns", "content": "Async tips"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Python patterns"
        assert data["content"] == "Async tips"
        assert "id" in data

    def test_post_missing_title_returns_422(self, db_conn: Connection[Any]) -> None:
        client = _make_note_client(db_conn)
        resp = client.post("/api/notes", json={"content": "No title"})
        assert resp.status_code == 422

    def test_get_by_id_returns_full_record(self, db_conn: Connection[Any]) -> None:
        client = _make_note_client(db_conn)
        created = client.post(
            "/api/notes",
            json={"title": "Test", "content": "Body text"},
        ).json()
        resp = client.get(f"/api/notes/{created['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == created["id"]
        assert data["content"] == "Body text"

    def test_get_unknown_id_returns_404(self, db_conn: Connection[Any]) -> None:
        client = _make_note_client(db_conn)
        resp = client.get("/api/notes/9999")
        assert resp.status_code == 404

    def test_list_returns_summaries(self, db_conn: Connection[Any]) -> None:
        client = _make_note_client(db_conn)
        client.post("/api/notes", json={"title": "A"})
        client.post("/api/notes", json={"title": "B"})
        resp = client.get("/api/notes")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        for item in data:
            assert "content" not in item
            assert "title" in item

    def test_list_empty_returns_empty_array(self, db_conn: Connection[Any]) -> None:
        client = _make_note_client(db_conn)
        resp = client.get("/api/notes")
        assert resp.status_code == 200
        assert resp.json() == []


# ── US2: Update Notes ────────────────────────────────────────────────────────


class TestRESTPatchNote:
    """REST contract tests for PATCH /api/notes/{id}."""

    def test_patch_returns_200_updated(self, db_conn: Connection[Any]) -> None:
        client = _make_note_client(db_conn)
        created = client.post(
            "/api/notes",
            json={"title": "Original", "content": "Old content"},
        ).json()
        resp = client.patch(
            f"/api/notes/{created['id']}",
            json={"content": "Updated content"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "Updated content"
        assert data["title"] == "Original"

    def test_patch_unknown_id_returns_404(self, db_conn: Connection[Any]) -> None:
        client = _make_note_client(db_conn)
        resp = client.patch("/api/notes/9999", json={"content": "x"})
        assert resp.status_code == 404

    def test_patch_blank_title_returns_422(self, db_conn: Connection[Any]) -> None:
        client = _make_note_client(db_conn)
        created = client.post("/api/notes", json={"title": "Original"}).json()
        resp = client.patch(f"/api/notes/{created['id']}", json={"title": ""})
        assert resp.status_code == 422


# ── US3: Tags ────────────────────────────────────────────────────────────────


class TestRESTNoteTags:
    """REST contract tests for GET /api/notes/tags."""

    def test_get_tags_sorted_unique(self, db_conn: Connection[Any]) -> None:
        client = _make_note_client(db_conn)
        client.post("/api/notes", json={"title": "A", "tags": ["python", "async"]})
        client.post("/api/notes", json={"title": "B", "tags": ["async", "fastapi"]})
        resp = client.get("/api/notes/tags")
        assert resp.status_code == 200
        tags = resp.json()
        assert isinstance(tags, list)
        assert set(tags) == {"python", "async", "fastapi"}
        assert tags == sorted(tags)

    def test_get_tags_empty_when_no_notes(self, db_conn: Connection[Any]) -> None:
        client = _make_note_client(db_conn)
        resp = client.get("/api/notes/tags")
        assert resp.status_code == 200
        assert resp.json() == []


# ── US4: Delete ──────────────────────────────────────────────────────────────


class TestRESTDeleteNote:
    """REST contract tests for DELETE /api/notes/{id}."""

    def test_delete_returns_200_with_message(self, db_conn: Connection[Any]) -> None:
        client = _make_note_client(db_conn)
        created = client.post("/api/notes", json={"title": "Delete me"}).json()
        resp = client.delete(f"/api/notes/{created['id']}")
        assert resp.status_code == 200
        assert "message" in resp.json()

    def test_deleted_not_retrievable(self, db_conn: Connection[Any]) -> None:
        client = _make_note_client(db_conn)
        created = client.post("/api/notes", json={"title": "Gone"}).json()
        client.delete(f"/api/notes/{created['id']}")
        resp = client.get(f"/api/notes/{created['id']}")
        assert resp.status_code == 404

    def test_delete_unknown_returns_404(self, db_conn: Connection[Any]) -> None:
        client = _make_note_client(db_conn)
        resp = client.delete("/api/notes/9999")
        assert resp.status_code == 404


# ── US5: Search and Filter ───────────────────────────────────────────────────


class TestRESTNoteSearch:
    """REST contract tests for GET /api/notes with search params."""

    def test_filter_by_tag(self, db_conn: Connection[Any]) -> None:
        client = _make_note_client(db_conn)
        client.post("/api/notes", json={"title": "Python", "tags": ["python"]})
        client.post("/api/notes", json={"title": "Go", "tags": ["go"]})
        resp = client.get("/api/notes?tag=python")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Python"

    def test_search_by_keyword(self, db_conn: Connection[Any]) -> None:
        client = _make_note_client(db_conn)
        client.post("/api/notes", json={"title": "Python patterns"})
        client.post("/api/notes", json={"title": "Go patterns"})
        resp = client.get("/api/notes?q=python")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Python patterns"

    def test_combined_search_and_filter(self, db_conn: Connection[Any]) -> None:
        client = _make_note_client(db_conn)
        client.post("/api/notes", json={"title": "Python async", "tags": ["python"]})
        client.post("/api/notes", json={"title": "Go async", "tags": ["go"]})
        resp = client.get("/api/notes?q=async&tag=python")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Python async"


class TestRESTNoteMultiTagFilter:
    """REST contract tests for multi-tag AND filter on GET /api/notes."""

    def test_multi_tag_and_returns_intersection(self, db_conn: Connection[Any]) -> None:
        client = _make_note_client(db_conn)
        client.post("/api/notes", json={"title": "Both", "tags": ["python", "async"]})
        client.post("/api/notes", json={"title": "Python only", "tags": ["python"]})
        client.post("/api/notes", json={"title": "Async only", "tags": ["async"]})
        resp = client.get("/api/notes?tag=python&tag=async")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Both"

    def test_single_tag_param_still_works(self, db_conn: Connection[Any]) -> None:
        client = _make_note_client(db_conn)
        client.post("/api/notes", json={"title": "Python note", "tags": ["python"]})
        client.post("/api/notes", json={"title": "Go note", "tags": ["go"]})
        resp = client.get("/api/notes?tag=python")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Python note"

    def test_no_tag_params_returns_all(self, db_conn: Connection[Any]) -> None:
        client = _make_note_client(db_conn)
        client.post("/api/notes", json={"title": "A", "tags": ["python"]})
        client.post("/api/notes", json={"title": "B", "tags": ["go"]})
        resp = client.get("/api/notes")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


# ── US6: MCP Tools ───────────────────────────────────────────────────────────


class TestMCPNoteTools:
    """MCP contract tests for all 5 note tools."""

    def test_create_returns_note(self, note_service: Any) -> None:
        from fastmcp import FastMCP

        from pktx.tools.note_tools import register_note_tools

        mcp = FastMCP("test")
        register_note_tools(mcp, lambda: note_service)

        tool_fn = _get_tool_fn(mcp, "create_note")
        result = tool_fn(title="Test note", content="Body", tags=[])
        assert result["title"] == "Test note"
        assert result["content"] == "Body"
        assert isinstance(result["id"], int)

    def test_create_missing_title_raises(self, note_service: Any) -> None:
        from fastmcp import FastMCP

        from pktx.tools.note_tools import register_note_tools

        mcp = FastMCP("test")
        register_note_tools(mcp, lambda: note_service)

        tool_fn = _get_tool_fn(mcp, "create_note")
        with pytest.raises(ToolError):
            tool_fn(title="", content="", tags=[])

    def test_list_returns_summaries(self, note_service: Any) -> None:
        from fastmcp import FastMCP

        from pktx.tools.note_tools import register_note_tools

        mcp = FastMCP("test")
        register_note_tools(mcp, lambda: note_service)

        note_service.create_note({"title": "A"}, user_id=_TEST_USER)

        list_fn = _get_tool_fn(mcp, "list_notes")
        result = list_fn(tag=None, q=None)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_get_returns_note_dict(self, note_service: Any) -> None:
        from fastmcp import FastMCP

        from pktx.tools.note_tools import register_note_tools

        mcp = FastMCP("test")
        register_note_tools(mcp, lambda: note_service)

        created = note_service.create_note({"title": "Get me"}, user_id=_TEST_USER)
        get_fn = _get_tool_fn(mcp, "get_note")
        result = get_fn(id=created["id"])
        assert isinstance(result, dict)
        assert result["title"] == "Get me"

    def test_get_unknown_raises(self, note_service: Any) -> None:
        from fastmcp import FastMCP

        from pktx.tools.note_tools import register_note_tools

        mcp = FastMCP("test")
        register_note_tools(mcp, lambda: note_service)

        get_fn = _get_tool_fn(mcp, "get_note")
        with pytest.raises(ToolError, match="not found"):
            get_fn(id=9999)

    def test_update_returns_note(self, note_service: Any) -> None:
        from fastmcp import FastMCP

        from pktx.tools.note_tools import register_note_tools

        mcp = FastMCP("test")
        register_note_tools(mcp, lambda: note_service)

        created = note_service.create_note({"title": "Original"}, user_id=_TEST_USER)
        update_fn = _get_tool_fn(mcp, "update_note")
        result = update_fn(id=created["id"], title=None, content="Updated", tags=None)
        assert result["id"] == created["id"]
        assert result["title"] == "Original"
        assert result["content"] == "Updated"

    def test_delete_returns_id_and_title(self, note_service: Any) -> None:
        from fastmcp import FastMCP

        from pktx.tools.note_tools import register_note_tools

        mcp = FastMCP("test")
        register_note_tools(mcp, lambda: note_service)

        created = note_service.create_note({"title": "Delete me"}, user_id=_TEST_USER)
        delete_fn = _get_tool_fn(mcp, "delete_note")
        result = delete_fn(id=created["id"])
        assert result == {"id": created["id"], "title": "Delete me"}

    def test_create_list_update_delete_sequence(self, note_service: Any) -> None:
        from fastmcp import FastMCP

        from pktx.tools.note_tools import register_note_tools

        mcp = FastMCP("test")
        register_note_tools(mcp, lambda: note_service)

        create_fn = _get_tool_fn(mcp, "create_note")
        list_fn = _get_tool_fn(mcp, "list_notes")
        update_fn = _get_tool_fn(mcp, "update_note")
        delete_fn = _get_tool_fn(mcp, "delete_note")
        get_fn = _get_tool_fn(mcp, "get_note")

        # Create
        create_fn(title="Cross-tool test", content="", tags=[])
        # List
        items = list_fn(tag=None, q=None)
        assert len(items) == 1
        note_id = items[0]["id"]
        # Update
        update_fn(id=note_id, title=None, content="Updated", tags=None)
        got = get_fn(id=note_id)
        assert got["content"] == "Updated"
        # Delete
        delete_fn(id=note_id)
        assert list_fn(tag=None, q=None) == []


# ── Helper ────────────────────────────────────────────────────────────────────


def _get_tool_fn(mcp: Any, name: str) -> Any:
    """Extract a registered MCP tool function by name for direct testing."""
    tools = asyncio.run(mcp.list_tools())
    for tool in tools:
        if tool.name == name:
            return tool.fn
    registered = [t.name for t in tools]
    raise KeyError(f"MCP tool '{name}' not found. Registered: {registered}")
