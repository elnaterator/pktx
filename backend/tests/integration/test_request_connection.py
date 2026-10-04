"""027 / H6, M10–M13, 8b: per-request pooled connection, auth wiring, body cap.

Runs against the real production composition: ``create_app(pool=...)`` builds
services on a ``RequestConnection`` over a real ``ConnectionPool`` from
``init_pool`` (``autocommit=False`` + ``check``), wrapped in
``DBSessionMiddleware``. Writes are real commits, so every test only creates
users whose ids start with ``ac_``; they are deleted (cascade) on teardown.
"""

import asyncio
import base64
import contextvars
import json
import threading
import time
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import httpx
import psycopg
import pytest
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from starlette.testclient import TestClient

from pktx.db import RequestConnection
from tests.helpers import gen_rsa_key_pair, make_token, public_key_to_jwk

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _admin(pg_dsn: str) -> psycopg.Connection[Any]:
    return psycopg.connect(pg_dsn, row_factory=dict_row, autocommit=True)  # type: ignore[call-overload]


def _user_exists(pg_dsn: str, uid: str) -> bool:
    with _admin(pg_dsn) as c:
        return (
            c.execute("SELECT 1 FROM users WHERE id = %s", (uid,)).fetchone()
            is not None
        )


@pytest.fixture
def pool(
    _schema_applied: None, pg_dsn: str
) -> Generator[ConnectionPool[Any], None, None]:
    from pktx.database import init_pool

    p = init_pool(pg_dsn, 1, 4)
    try:
        yield p
    finally:
        p.close()
        with _admin(pg_dsn) as c:
            c.execute("DELETE FROM users WHERE id LIKE 'ac\\_%%'")


@pytest.fixture(autouse=True)
def _no_cors_no_frontend(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    monkeypatch.delenv("PKTX_CORS_ORIGINS", raising=False)
    monkeypatch.setenv("PKTX_FRONTEND_DIR", str(tmp_path / "missing"))


def _with_test_routes(app: FastAPI, pool: ConnectionPool[Any]) -> FastAPI:
    """Prepend test-only routes that write through a RequestConnection."""
    conn = RequestConnection(pool)
    r = APIRouter()

    def _insert(uid: str) -> None:
        conn.execute("INSERT INTO users (id) VALUES (%s)", (uid,))

    @r.post("/t/ok/{uid}")
    def ok(uid: str) -> dict[str, str]:
        _insert(uid)
        return {"status": "ok"}

    @r.post("/t/raise/{uid}")
    def boom(uid: str) -> dict[str, str]:
        _insert(uid)
        raise RuntimeError("handler failed after write")

    @r.post("/t/500/{uid}")
    def five_hundred(uid: str) -> JSONResponse:
        _insert(uid)
        return JSONResponse({"detail": "nope"}, status_code=500)

    @r.post("/t/http-error/{uid}")
    def http_error(uid: str) -> dict[str, str]:
        _insert(uid)
        raise HTTPException(status_code=503, detail="unavailable")

    @r.get("/t/pid")
    def pid() -> dict[str, int]:
        row = conn.execute("SELECT pg_backend_pid() AS pid").fetchone()
        return {"pid": row["pid"]}

    @r.post("/t/async/{uid}")
    async def async_write(uid: str) -> dict[str, str]:
        await asyncio.to_thread(_insert, uid)
        return {"status": "ok"}

    for route in reversed(r.routes):
        app.router.routes.insert(0, route)
    return app


@pytest.fixture
def app(pool: ConnectionPool[Any]) -> FastAPI:
    from pktx.server import create_app

    return _with_test_routes(create_app(pool=pool), pool)


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# Transaction per request
# ---------------------------------------------------------------------------


class TestTransactionPerRequest:
    def test_commit_on_success(self, client: TestClient, pg_dsn: str) -> None:
        assert client.post("/t/ok/ac_commit").status_code == 200
        assert _user_exists(pg_dsn, "ac_commit")

    def test_commit_from_async_handler_thread(
        self, client: TestClient, pg_dsn: str
    ) -> None:
        assert client.post("/t/async/ac_async").status_code == 200
        assert _user_exists(pg_dsn, "ac_async")

    def test_rollback_on_raised_exception(
        self, client: TestClient, pg_dsn: str
    ) -> None:
        assert client.post("/t/raise/ac_raise").status_code == 500
        assert not _user_exists(pg_dsn, "ac_raise")

    def test_rollback_on_5xx_response(self, client: TestClient, pg_dsn: str) -> None:
        assert client.post("/t/500/ac_500").status_code == 500
        assert not _user_exists(pg_dsn, "ac_500")

    def test_rollback_on_5xx_http_exception(
        self, client: TestClient, pg_dsn: str
    ) -> None:
        assert client.post("/t/http-error/ac_503").status_code == 503
        assert not _user_exists(pg_dsn, "ac_503")

    def test_connection_returned_to_pool(
        self, client: TestClient, pool: ConnectionPool[Any]
    ) -> None:
        for path in ("/t/ok/ac_ret1", "/t/raise/ac_ret2", "/t/500/ac_ret3"):
            client.post(path)
        stats = pool.get_stats()
        assert stats["pool_size"] == stats["pool_available"]

    def test_outside_scope_raises(self, pool: ConnectionPool[Any]) -> None:
        def _run() -> None:
            with pytest.raises(RuntimeError, match="outside a request"):
                RequestConnection(pool).execute("SELECT 1")

        contextvars.Context().run(_run)


class TestLazyCheckout:
    def test_health_never_checks_out(
        self, client: TestClient, pool: ConnectionPool[Any]
    ) -> None:
        spy = MagicMock(wraps=pool.getconn)
        pool.getconn = spy  # type: ignore[method-assign]
        assert client.get("/health").status_code == 200
        assert client.get("/some/static/path").status_code == 404
        spy.assert_not_called()
        assert client.get("/t/pid").status_code == 200
        spy.assert_called_once()

    def test_dead_connection_replaced_on_next_request(
        self, pg_dsn: str, _schema_applied: None
    ) -> None:
        from pktx.database import init_pool
        from pktx.server import create_app

        p = init_pool(pg_dsn, 1, 1)
        try:
            app = _with_test_routes(create_app(pool=p), p)
            with TestClient(app, raise_server_exceptions=False) as c:
                first = c.get("/t/pid").json()["pid"]
                with _admin(pg_dsn) as admin:
                    admin.execute("SELECT pg_terminate_backend(%s)", (first,))
                time.sleep(0.2)
                resp = c.get("/t/pid")
                assert resp.status_code == 200
                assert resp.json()["pid"] != first
        finally:
            p.close()

    async def test_concurrent_requests_get_distinct_connections(
        self, app: FastAPI, pool: ConnectionPool[Any]
    ) -> None:
        barrier = threading.Barrier(2, timeout=10)
        conn = RequestConnection(pool)

        @app.get("/t/held")
        def held() -> dict[str, int]:
            row = conn.execute("SELECT pg_backend_pid() AS pid").fetchone()
            barrier.wait()  # both requests hold a connection at the same time
            return {"pid": row["pid"]}

        app.router.routes.insert(0, app.router.routes.pop())
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as ac:
            r1, r2 = await asyncio.gather(ac.get("/t/held"), ac.get("/t/held"))
        assert r1.status_code == r2.status_code == 200
        assert r1.json()["pid"] != r2.json()["pid"]


# ---------------------------------------------------------------------------
# Production REST path with auth: resume delete, PKTX_USER_ID, webhook
# ---------------------------------------------------------------------------

_AUTH_ENV = {
    "PKTX_PUBLIC_URL": "https://pktx.test/",
    "CLERK_ISSUER": "https://clerk.test",
    "CLERK_JWKS_URL": "https://clerk.test/.well-known/jwks.json",
    "CLERK_OAUTH_CLIENT_ID": "test_client_id",
    "CLERK_OAUTH_CLIENT_SECRET": "test_client_secret_at_least_12_chars",
    "CLERK_WEBHOOK_SECRET": "whsec_" + base64.b64encode(b"0" * 32).decode(),
}


@pytest.fixture
def auth_client(
    pool: ConnectionPool[Any], monkeypatch: pytest.MonkeyPatch
) -> Generator[tuple[TestClient, Any], None, None]:
    import pktx.auth as auth_module
    from pktx.server import create_app

    for k, v in _AUTH_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("CLERK_AUTHORIZED_PARTIES", raising=False)  # derive
    private_key, public_key = gen_rsa_key_pair()
    monkeypatch.setattr(
        auth_module, "_JWKS_CACHE", {"ck1": public_key_to_jwk(public_key)}
    )
    monkeypatch.setattr(auth_module, "_JWKS_FETCHED_AT", time.monotonic())

    app = create_app(pool=pool, enable_auth=True)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c, private_key


def _bearer(private_key: Any, sub: str) -> dict[str, str]:
    token = make_token(private_key, sub=sub, azp="https://pktx.test")
    return {"Authorization": f"Bearer {token}"}


class TestProductionRestPath:
    def test_delete_one_of_two_resumes(self, auth_client: tuple) -> None:
        client, key = auth_client
        h = _bearer(key, "ac_alice")
        ids = []
        for label in ("one", "two"):
            resp = client.post("/api/resumes", json={"label": label}, headers=h)
            assert resp.status_code == 201, resp.text
            ids.append(resp.json()["id"])

        resp = client.delete(f"/api/resumes/{ids[0]}", headers=h)
        assert resp.status_code in (200, 204), resp.text
        listed = client.get("/api/resumes", headers=h).json()
        assert [r["id"] for r in listed] == [ids[1]]

    def test_default_authorized_party_from_public_url(self, auth_client: tuple) -> None:
        client, key = auth_client
        ok = client.get("/api/resumes", headers=_bearer(key, "ac_azp"))
        assert ok.status_code == 200
        bad = make_token(key, sub="ac_azp", azp="https://evil.example")
        resp = client.get("/api/resumes", headers={"Authorization": f"Bearer {bad}"})
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid token"

    def test_pkt_user_id_ignored_over_http(
        self, auth_client: tuple, monkeypatch: pytest.MonkeyPatch, pg_dsn: str
    ) -> None:
        client, _ = auth_client
        monkeypatch.setenv("PKTX_USER_ID", "ac_stdio_user")
        assert client.get("/api/resumes").status_code == 401
        garbage = {"Authorization": "Bearer not.a.jwt"}
        resp = client.get("/api/resumes", headers=garbage)
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid token"
        assert not _user_exists(pg_dsn, "ac_stdio_user")

    def test_rest_jwt_verified_once_per_request(
        self, auth_client: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import pktx.auth as auth_module

        client, key = auth_client
        real = auth_module.verify_clerk_jwt
        spy = MagicMock(side_effect=real)
        monkeypatch.setattr(auth_module, "verify_clerk_jwt", spy)
        assert (
            client.get("/api/resumes", headers=_bearer(key, "ac_once")).status_code
            == 200
        )
        assert spy.call_count == 1


def _signed_webhook(event: dict[str, Any], secret: str) -> tuple[bytes, dict[str, str]]:
    from svix.webhooks import Webhook

    payload = json.dumps(event)
    ts = datetime.now(tz=UTC)
    sig = Webhook(secret).sign("msg_1", ts, payload)
    headers = {
        "svix-id": "msg_1",
        "svix-timestamp": str(int(ts.timestamp())),
        "svix-signature": sig,
        "content-type": "application/json",
    }
    return payload.encode(), headers


class TestClerkWebhook:
    def test_bad_signature_400(self, auth_client: tuple) -> None:
        client, _ = auth_client
        body, headers = _signed_webhook(
            {"type": "user.deleted", "data": {"id": "ac_x"}},
            "whsec_" + base64.b64encode(b"1" * 32).decode(),
        )
        resp = client.post("/api/webhooks/clerk", content=body, headers=headers)
        assert resp.status_code == 400

    def test_user_deleted_cascades_only_that_user(
        self, auth_client: tuple, pg_dsn: str
    ) -> None:
        client, key = auth_client
        for uid in ("ac_gone", "ac_kept"):
            resp = client.post(
                "/api/resumes", json={"label": uid}, headers=_bearer(key, uid)
            )
            assert resp.status_code == 201
        body, headers = _signed_webhook(
            {"type": "user.deleted", "data": {"id": "ac_gone"}},
            _AUTH_ENV["CLERK_WEBHOOK_SECRET"],
        )
        resp = client.post("/api/webhooks/clerk", content=body, headers=headers)
        assert resp.status_code == 200, resp.text

        with _admin(pg_dsn) as c:
            gone = c.execute(
                "SELECT count(*) AS n FROM resume_version WHERE user_id = 'ac_gone'"
            ).fetchone()
            kept = c.execute(
                "SELECT count(*) AS n FROM resume_version WHERE user_id = 'ac_kept'"
            ).fetchone()
        assert gone is not None and gone["n"] == 0
        assert kept is not None and kept["n"] == 1
        assert not _user_exists(pg_dsn, "ac_gone")
        assert _user_exists(pg_dsn, "ac_kept")


# ---------------------------------------------------------------------------
# MCP tool calls: HTTP (ASGI scope) and stdio (tool middleware owns scope)
# ---------------------------------------------------------------------------


def _mcp_with_tools(pool: ConnectionPool[Any], user_id: str | None = None) -> Any:
    from fastmcp import FastMCP

    from pktx.auth import require_user_id
    from pktx.server import DBSessionToolMiddleware

    conn = RequestConnection(pool)
    m = FastMCP("t")
    m.add_middleware(DBSessionToolMiddleware(user_id=user_id))

    @m.tool()
    def write(uid: str) -> str:
        conn.execute("INSERT INTO users (id) VALUES (%s)", (uid,))
        return "ok"

    @m.tool()
    def write_then_fail(uid: str) -> str:
        conn.execute("INSERT INTO users (id) VALUES (%s)", (uid,))
        raise RuntimeError("tool failed after write")

    @m.tool()
    def whoami() -> str:
        return require_user_id()

    return m


class TestMcpHttpToolSession:
    def _call(self, client: TestClient, name: str, args: dict[str, Any]) -> Any:
        resp = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": args},
            },
            headers={"accept": "application/json, text/event-stream"},
        )
        assert resp.status_code == 200, resp.text
        return resp

    @pytest.fixture
    def mcp_client(
        self, pool: ConnectionPool[Any]
    ) -> Generator[TestClient, None, None]:
        from pktx.server import DBSessionMiddleware

        mcp_app = _mcp_with_tools(pool).http_app(path="/mcp", stateless_http=True)
        mcp_app.add_middleware(DBSessionMiddleware)
        with TestClient(mcp_app, raise_server_exceptions=False) as c:
            yield c

    def test_tool_success_commits(self, mcp_client: TestClient, pg_dsn: str) -> None:
        self._call(mcp_client, "write", {"uid": "ac_mcp_ok"})
        assert _user_exists(pg_dsn, "ac_mcp_ok")

    def test_tool_error_rolls_back_despite_200(
        self, mcp_client: TestClient, pg_dsn: str, pool: ConnectionPool[Any]
    ) -> None:
        resp = self._call(mcp_client, "write_then_fail", {"uid": "ac_mcp_fail"})
        assert "isError" in resp.text
        assert not _user_exists(pg_dsn, "ac_mcp_fail")
        stats = pool.get_stats()
        assert stats["pool_size"] == stats["pool_available"]


class TestStdioToolSession:
    async def test_stdio_tools_run_as_user_and_commit(
        self, pool: ConnectionPool[Any], pg_dsn: str
    ) -> None:
        from fastmcp import Client

        mcp = _mcp_with_tools(pool, user_id="ac_stdio")
        async with Client(mcp) as c:
            who = await c.call_tool("whoami", {})
            assert who.content[0].text == "ac_stdio"  # type: ignore[union-attr]
            await c.call_tool("write", {"uid": "ac_stdio_ok"})
            failed = await c.call_tool(
                "write_then_fail", {"uid": "ac_stdio_fail"}, raise_on_error=False
            )
            assert failed.is_error
        assert _user_exists(pg_dsn, "ac_stdio_ok")
        assert not _user_exists(pg_dsn, "ac_stdio_fail")
        stats = pool.get_stats()
        assert stats["pool_size"] == stats["pool_available"]

    def test_stdio_requires_user_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pktx.server import resolve_stdio_user_id

        monkeypatch.delenv("PKTX_USER_ID", raising=False)
        with pytest.raises(SystemExit, match="PKTX_USER_ID"):
            contextvars.copy_context().run(resolve_stdio_user_id)

    def test_stdio_sets_user_contextvar(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pktx.auth import current_user_id_var
        from pktx.server import resolve_stdio_user_id

        monkeypatch.setenv("PKTX_USER_ID", " ac_me ")

        def _run() -> tuple[str, str | None]:
            return resolve_stdio_user_id(), current_user_id_var.get()

        assert contextvars.copy_context().run(_run) == ("ac_me", "ac_me")
        assert current_user_id_var.get() is None


# ---------------------------------------------------------------------------
# Request body cap (8b)
# ---------------------------------------------------------------------------


class TestBodySizeLimit:
    def test_content_length_over_limit_413(self, client: TestClient) -> None:
        resp = client.post(
            "/api/resumes",
            content=b"x" * (1_048_576 + 1),
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 413
        assert resp.json() == {"detail": "Request body too large"}

    def test_under_limit_passes_through(self, client: TestClient) -> None:
        resp = client.post("/t/ok/ac_small", content=b"x" * 1000)
        assert resp.status_code == 200

    async def test_streamed_body_without_content_length_413(self) -> None:
        from pktx.server import BodySizeLimitMiddleware

        reached: list[bool] = []

        async def app(scope: Any, receive: Any, send: Any) -> None:
            while True:
                msg = await receive()
                if not msg.get("more_body"):
                    break
            reached.append(True)
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        chunk = b"x" * 300_000
        chunks = [chunk] * 4  # 1.2 MB, no Content-Length

        async def receive() -> dict[str, Any]:
            body = chunks.pop(0)
            return {"type": "http.request", "body": body, "more_body": bool(chunks)}

        sent: list[dict[str, Any]] = []

        async def send(msg: dict[str, Any]) -> None:
            sent.append(msg)

        scope = {"type": "http", "method": "POST", "path": "/x", "headers": []}
        mw: Any = BodySizeLimitMiddleware(app)
        await mw(scope, receive, send)
        assert not reached
        assert sent[0]["status"] == 413

    def test_streamed_body_through_fastapi_413(self, client: TestClient) -> None:
        def gen() -> Any:
            for _ in range(5):
                yield b"x" * 300_000

        resp = client.post(
            "/api/resumes", content=gen(), headers={"content-type": "application/json"}
        )
        assert resp.status_code == 413
