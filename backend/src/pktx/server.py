"""pktx server — FastAPI REST API + MCP tools, with --stdio backward compat."""

import argparse
import json
import logging
import os
from collections.abc import AsyncIterator, Awaitable, Callable, MutableMapping
from contextlib import asynccontextmanager
from typing import Any, TypeVar

import anyio
import anyio.to_thread
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware
from mcp.types import Icon
from psycopg_pool import ConnectionPool
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Route as StarletteRoute

from pktx.accomplishment_service import AccomplishmentService
from pktx.api.routes import create_router
from pktx.application_service import ApplicationService
from pktx.auth import (
    UserContextToolMiddleware,
    build_get_current_user,
    build_mcp_auth,
    current_user_id_var,
)
from pktx.communication_service import ContactCommunicationService
from pktx.config import (
    MAX_REQUEST_BODY_BYTES,
    configure_logging,
    resolve_authorized_parties,
    resolve_cors_origins,
    resolve_db_url,
    resolve_frontend_dir,
    resolve_pool_max,
    resolve_pool_min,
    resolve_port,
    resolve_public_url_optional,
)
from pktx.contact_service import ContactService
from pktx.database import init_pool
from pktx.db import (
    ConnHolder,
    DBConnection,
    RequestConnection,
    begin_scope,
    current_holder,
    end_scope,
)
from pktx.link_service import LinkService
from pktx.note_service import NoteService
from pktx.oauth_theme import ICON_DATA_URI, ThemedAuthPagesMiddleware
from pktx.resume_service import ResumeService
from pktx.tools.accomplishment_tools import register_accomplishment_tools
from pktx.tools.application_tools import register_application_tools
from pktx.tools.contact_tools import register_contact_tools
from pktx.tools.link_tools import register_link_tools
from pktx.tools.note_tools import register_note_tools
from pktx.tools.resume_tools import register_resume_tools

logger = logging.getLogger("pktx")

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


class SPAStaticFiles(StaticFiles):
    """StaticFiles subclass that falls back to index.html for unknown paths.

    Enables client-side routing (React Router) to handle routes like
    /resumes/3 when accessed directly or on page refresh, instead of
    returning a 404 from the server.

    API routes and MCP routes are registered before this mount and take
    priority, so /api/*, /health, and /mcp/* are never intercepted.
    """

    async def get_response(self, path: str, scope):  # type: ignore[override]
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


# Resolved at startup, used by MCP tool handlers.
_pool: ConnectionPool[Any] | None = None
_service: ResumeService | None = None
_app_service: ApplicationService | None = None
_acc_service: AccomplishmentService | None = None
_note_service: NoteService | None = None
_contact_service: ContactService | None = None
_comm_service: ContactCommunicationService | None = None
_link_service: LinkService | None = None


T = TypeVar("T")


def _require(value: T | None, name: str) -> T:
    """Return an initialized module global; raises (not asserts) so ``-O`` keeps it."""
    if value is None:
        raise RuntimeError(f"{name} is not initialized")
    return value


def _get_resume_service() -> ResumeService:
    return _require(_service, "_service")


def _get_app_service() -> ApplicationService:
    return _require(_app_service, "_app_service")


def _get_acc_service() -> AccomplishmentService:
    return _require(_acc_service, "_acc_service")


def _get_note_service() -> NoteService:
    return _require(_note_service, "_note_service")


def _get_contact_service() -> ContactService:
    return _require(_contact_service, "_contact_service")


def _get_comm_service() -> ContactCommunicationService:
    return _require(_comm_service, "_comm_service")


def _get_link_service() -> LinkService:
    return _require(_link_service, "_link_service")


def _init_services(service: ResumeService, conn: DBConnection | None) -> None:
    """Set the module-level services shared by REST routes and MCP tools."""
    global _service, _app_service, _acc_service, _note_service
    global _contact_service, _comm_service, _link_service
    _service = service
    _app_service = ApplicationService(conn) if conn else None
    _acc_service = AccomplishmentService(conn) if conn else None
    _note_service = NoteService(conn) if conn else None
    _contact_service = ContactService(conn) if conn else None
    _comm_service = ContactCommunicationService(conn) if conn else None
    _link_service = LinkService(conn) if conn else None


# ---------------------------------------------------------------------------
# Per-request DB session (027 / H6)
# ---------------------------------------------------------------------------


async def _release(holder: ConnHolder, commit: bool) -> None:
    """Commit/rollback + putconn off the event loop, shielded from cancellation.

    Shielded so a cancelled request (client disconnect) still returns its
    connection to the pool instead of leaking it.
    """
    if holder.conn is None:
        return
    with anyio.CancelScope(shield=True):
        await anyio.to_thread.run_sync(holder.release, commit)


async def _send_json(send: Send, status: int, body: dict[str, Any]) -> None:
    payload = json.dumps(body).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(payload)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": payload})


class DBSessionMiddleware:
    """One pooled connection + one transaction per HTTP request.

    Installs an empty ``ConnHolder`` before the app runs; ``RequestConnection``
    checks a connection out lazily on first use. When the response starts, a
    checked-out connection is committed (rolled back on a 5xx status or a
    holder marked failed) *before* the status line is forwarded, so a client
    never sees success for a write that failed to commit — a commit failure
    turns into a 500 instead. At the end of the request any remaining work is
    committed (rolled back if the app raised) and the connection goes back to
    the pool. Blocking pool/commit calls run in a worker thread.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        holder, token = begin_scope()
        swallow = False

        async def send_wrapper(message: Message) -> None:
            nonlocal swallow
            if swallow:
                return
            if message["type"] == "http.response.start" and holder.conn is not None:
                if message["status"] >= 500:
                    holder.failed = True
                try:
                    await anyio.to_thread.run_sync(holder.end_transaction, True)
                except Exception:
                    logger.exception("DB commit failed; answering 500")
                    holder.failed = True
                    swallow = True
                    await _send_json(send, 500, {"detail": "Internal Server Error"})
                    return
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except BaseException:
            holder.failed = True
            await _release(holder, commit=False)
            raise
        else:
            await _release(holder, commit=True)
        finally:
            end_scope(token)


class DBSessionToolMiddleware(Middleware):
    """DB session handling for MCP tool calls.

    Over HTTP the ASGI ``DBSessionMiddleware`` already owns the scope; MCP
    returns tool errors as HTTP 200, so here a raised tool error only marks the
    scope for rollback. With no scope active (stdio transport) this middleware
    owns one per tool call: install a holder, run the tool, commit or roll back,
    return the connection. ``user_id`` (stdio only) is set as the current user
    for every call.
    """

    def __init__(self, user_id: str | None = None) -> None:
        self._user_id = user_id

    async def on_call_tool(self, context, call_next):  # type: ignore[override]
        user_token = None
        if self._user_id is not None:
            user_token = current_user_id_var.set(self._user_id)
        try:
            outer = current_holder()
            if outer is not None:
                try:
                    return await call_next(context)
                except BaseException:
                    outer.failed = True
                    raise

            holder, token = begin_scope()
            try:
                result = await call_next(context)
            except BaseException:
                holder.failed = True
                await _release(holder, commit=False)
                raise
            else:
                await _release(holder, commit=True)
                return result
            finally:
                end_scope(token)
        finally:
            if user_token is not None:
                current_user_id_var.reset(user_token)


# ---------------------------------------------------------------------------
# Request body size cap (027 / 8b)
# ---------------------------------------------------------------------------


class _BodyTooLarge(StarletteHTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=413, detail="Request body too large")


class BodySizeLimitMiddleware:
    """Reject request bodies over ``max_bytes`` with 413.

    A declared ``Content-Length`` over the limit is rejected before the app
    runs. Bodies without one (chunked) are counted as they are received; the
    read that crosses the limit raises, and the 413 is sent if no response has
    started. The exception subclasses ``HTTPException`` so FastAPI's body
    parsing re-raises it untouched instead of turning it into a 400.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_REQUEST_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    await _send_json(send, 400, {"detail": "Invalid Content-Length"})
                    return
                if declared > self.max_bytes:
                    await _send_json(send, 413, {"detail": "Request body too large"})
                    return

        received = 0
        started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLarge()
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            if started:
                raise
            await _send_json(send, 413, {"detail": "Request body too large"})


# ---------------------------------------------------------------------------
# MCP wiring
# ---------------------------------------------------------------------------


def _build_mcp(
    production: bool,
    conn: DBConnection | None = None,
    stdio_user_id: str | None = None,
) -> FastMCP:
    """Create FastMCP instance, register all tools, and wire auth/middleware."""
    if production:
        if _pool is None:
            raise RuntimeError("DB pool required for production MCP auth")
        mcp_auth = build_mcp_auth(_pool)
    else:
        mcp_auth = None
    m = FastMCP(
        "pktx",
        auth=mcp_auth,
        # Shown on the OAuth consent screen and to clients that render server icons.
        icons=[Icon(src=ICON_DATA_URI, mimeType="image/svg+xml")],
        website_url=resolve_public_url_optional(),
    )

    register_resume_tools(m, _get_resume_service)
    register_application_tools(m, _get_app_service)
    register_accomplishment_tools(m, _get_acc_service)
    register_note_tools(m, _get_note_service)
    register_contact_tools(m, _get_contact_service, _get_comm_service)
    register_link_tools(m, _get_link_service)

    # Outermost: owns (stdio) or watches (HTTP) the DB session for each call.
    m.add_middleware(DBSessionToolMiddleware(user_id=stdio_user_id))
    if production:
        m.add_middleware(UserContextToolMiddleware(conn))

    return m


_PRM_PATH = "/.well-known/oauth-protected-resource"


def _add_root_resource_metadata_alias(app: FastAPI, mcp_app: Any) -> None:
    """Serve protected-resource metadata at the root well-known path too.

    FastMCP registers RFC 9728 metadata only at the path-suffixed location
    (``/.well-known/oauth-protected-resource/mcp``). MCP clients probe that first
    and fall back to the root path, so a client that skips the WWW-Authenticate
    header and probes only the root would otherwise get the SPA's 404 page. Both
    paths serve the same document, produced by the same handler.
    """
    suffixed = f"{_PRM_PATH}/mcp"
    source = next(
        (r for r in mcp_app.routes if getattr(r, "path", None) == suffixed), None
    )
    if source is None:
        return
    app.router.routes.append(
        StarletteRoute(
            _PRM_PATH,
            endpoint=source.endpoint,
            methods=["GET", "HEAD", "OPTIONS"],
            name="oauth_protected_resource_root",
        )
    )


# --- FastAPI application factory ---


def create_app(
    service: ResumeService | None = None,
    conn: DBConnection | None = None,
    *,
    pool: ConnectionPool[Any] | None = None,
    enable_auth: bool | None = None,
) -> FastAPI:
    """Create the FastAPI application with REST API routes and CORS middleware.

    Args:
        service: Optional pre-built ResumeService (for testing).
        conn: Optional pre-built DBConnection (for testing / MCP globals).
        pool: Optional pre-built pool (for testing the production connection
            path without auth). Services get a ``RequestConnection`` on it.
        enable_auth: Wire Clerk REST auth + the MCP OAuth proxy. Defaults to
            True only in full production mode (nothing injected).

    With nothing injected, initializes the pool from environment config; every
    request then runs on its own pooled connection and transaction.
    """
    global _pool

    production = service is None and conn is None and pool is None
    auth_enabled = production if enable_auth is None else enable_auth
    owns_pool = False

    if production:
        configure_logging()
        pool = init_pool(resolve_db_url(), resolve_pool_min(), resolve_pool_max())
        owns_pool = True
        logger.info("pktx server starting (PostgreSQL pool initialized)")
    if pool is not None:
        _pool = pool
        conn = RequestConnection(pool)
        if service is None:
            service = ResumeService(conn)
    if service is None:
        raise RuntimeError("create_app needs a service, conn or pool")

    _init_services(service, conn)

    mcp = _build_mcp(production=auth_enabled, conn=conn)

    # Get MCP HTTP app — use path="/mcp" so the Route is registered at /mcp.
    # We add this route directly to FastAPI's router (not via app.mount)
    # because Starlette's Mount("/mcp") regex requires a trailing slash,
    # causing POST /mcp to fall through to StaticFiles → 405.
    mcp_app = mcp.http_app(path="/mcp", stateless_http=True)

    # Create combined lifespan that wraps MCP lifespan and closes pool on shutdown
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with mcp_app.lifespan(app):
            yield
        if owns_pool and pool is not None:
            pool.close()

    app = FastAPI(title="pktx", lifespan=lifespan)

    # Middleware: last added is outermost. Resulting order, outer → inner:
    # CORS → body-size cap → MCP auth (if any) → auth-page theme → DB session → routes.
    app.add_middleware(DBSessionMiddleware)
    # FastMCP's consent/error pages get the SPA's look (HTML responses only).
    app.add_middleware(ThemedAuthPagesMiddleware)

    # Re-apply the MCP auth middleware that mcp.http_app() installs at the app
    # level. Below we graft only `mcp_app.routes` into this FastAPI app (to keep
    # POST /mcp working without a trailing slash); that drops the app-level
    # AuthenticationMiddleware (runs BearerAuthBackend → verify_token) and
    # AuthContextMiddleware (powers get_access_token() for tool user-scoping).
    # Without them every /mcp request is treated as unauthenticated and the
    # per-route RequireAuthMiddleware 401s as invalid_token before our verifier
    # ever runs. Add in reverse so AuthenticationMiddleware stays outermost and
    # populates request auth before AuthContextMiddleware reads it.
    if auth_enabled and mcp.auth is not None:
        for mw in reversed(mcp.auth.get_middleware()):
            app.add_middleware(mw.cls, *mw.args, **mw.kwargs)

    app.add_middleware(BodySizeLimitMiddleware)

    cors_origins = resolve_cors_origins()
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # REST auth. Authorized parties are resolved here, at build time, so a
    # deploy missing both CLERK_AUTHORIZED_PARTIES and PKTX_PUBLIC_URL fails to
    # start rather than accepting tokens from any origin.
    get_user = (
        build_get_current_user(conn, resolve_authorized_parties())
        if auth_enabled and conn is not None
        else None
    )
    app.include_router(
        create_router(
            service,
            app_service=_app_service,
            acc_service=_acc_service,
            note_service=_note_service,
            contact_service=_contact_service,
            comm_service=_comm_service,
            link_service=_link_service,
            get_current_user=get_user,
        )
    )

    # Add MCP routes directly to FastAPI's router (not via app.mount) so
    # the /mcp route is matched before the StaticFiles catch-all.
    for route in mcp_app.routes:
        app.router.routes.append(route)
    # Grafting routes drops mcp_app.state; FastMCP's consent and authorize
    # handlers read the server from it for its name, icon and website.
    app.state.fastmcp_server = mcp

    _add_root_resource_metadata_alias(app, mcp_app)

    # Mount static files for frontend (if directory exists)
    # This must come AFTER API routes and MCP mount so they take priority
    frontend_dir = resolve_frontend_dir()
    if frontend_dir is not None:
        app.mount(
            "/",
            SPAStaticFiles(directory=str(frontend_dir), html=True),
            name="frontend",
        )

    return app


def resolve_stdio_user_id() -> str:
    """Return ``PKTX_USER_ID`` for stdio mode, or exit with a clear error.

    Also sets ``current_user_id_var`` for the process (the stdio tool
    middleware sets it per call as well). Only the stdio transport uses
    ``PKTX_USER_ID``; HTTP mode ignores it.
    """
    user_id = os.environ.get("PKTX_USER_ID", "").strip()
    if not user_id:
        raise SystemExit(
            "pktx --stdio requires PKTX_USER_ID (the user id the MCP tools act as)"
        )
    current_user_id_var.set(user_id)
    return user_id


def main() -> None:
    """Start the pktx server (HTTP default, --stdio for backward compat)."""
    global _pool
    parser = argparse.ArgumentParser(description="pktx server")
    parser.add_argument(
        "--stdio",
        action="store_true",
        help="Run in stdio MCP mode (backward compat for local MCP clients)",
    )
    args = parser.parse_args()

    if args.stdio:
        configure_logging()
        user_id = resolve_stdio_user_id()
        pool = init_pool(resolve_db_url(), resolve_pool_min(), resolve_pool_max())
        _pool = pool
        conn = RequestConnection(pool)
        _init_services(ResumeService(conn), conn)
        logger.info("pktx MCP server starting (stdio, PostgreSQL pool initialized)")
        mcp = _build_mcp(production=False, stdio_user_id=user_id)
        try:
            mcp.run(transport="stdio")
        finally:
            pool.close()
    else:
        port = resolve_port()
        app = create_app()
        uvicorn.run(app, host="0.0.0.0", port=port)  # noqa: S104 — container/Lambda adapter must reach it


if __name__ == "__main__":
    main()
