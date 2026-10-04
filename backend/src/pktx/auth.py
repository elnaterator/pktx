"""Clerk JWT validation and FastAPI dependency for authenticated user context."""

import asyncio
import logging
import os
import threading
import time
from collections.abc import Collection
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastmcp.server.auth import AccessToken
from fastmcp.server.auth.oauth_proxy import OAuthProxy
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.auth.redirect_validation import DEFAULT_LOCALHOST_PATTERNS
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.middleware import Middleware
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from pktx.database import upsert_user
from pktx.db import DBConnection

if TYPE_CHECKING:
    from psycopg_pool import ConnectionPool

logger = logging.getLogger("pktx")

# ContextVar for passing user identity into MCP tool handlers
# Set to the Clerk user_id string when a request is authenticated;
# None when running in stdio mode without a user context.
current_user_id_var: ContextVar[str | None] = ContextVar(
    "current_user_id", default=None
)


def require_user_id() -> str:
    """Return the current user ID from the context var, or raise.

    MCP tool handlers MUST call this to enforce user scoping.
    Raises RuntimeError when no authenticated user context is set.
    """
    user_id = current_user_id_var.get()
    if user_id is None:
        raise RuntimeError("No user context set — cannot access user data")
    return user_id


# ---------------------------------------------------------------------------
# JWKS in-memory cache (used by REST API JWT path)
# ---------------------------------------------------------------------------

_JWKS_CACHE: dict[str, Any] = {}  # kid -> key dict
_JWKS_FETCHED_AT: float = 0.0  # last *successful* fetch
_JWKS_TTL: float = 3600.0  # 1 hour
# Refetch throttle: an unknown kid triggers at most one JWKS fetch per window,
# so a storm of forged kids cannot amplify into a storm of upstream requests.
_JWKS_MIN_REFETCH_INTERVAL: float = 60.0
_JWKS_LAST_ATTEMPT: float = float("-inf")  # last fetch attempt (success or not)
_JWKS_LOCK = threading.Lock()

_INVALID_TOKEN = "Invalid token"  # noqa: S105 — error message, not a credential


def _unauthorized(detail: str = _INVALID_TOKEN) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def _jwks_url() -> str:
    return os.environ.get("CLERK_JWKS_URL", "")


def _issuer() -> str:
    return os.environ.get("CLERK_ISSUER", "")


def _fetch_jwks() -> dict[str, Any]:
    """Fetch JWKS from Clerk and update the in-memory cache."""
    global _JWKS_CACHE, _JWKS_FETCHED_AT
    url = _jwks_url()
    if not url:
        raise ValueError("CLERK_JWKS_URL is not configured")
    response = httpx.get(url, timeout=10.0)
    response.raise_for_status()
    data = response.json()
    keys: dict[str, Any] = {}
    for key in data.get("keys", []):
        kid = key.get("kid")
        if kid:
            keys[kid] = key
    _JWKS_CACHE = keys
    _JWKS_FETCHED_AT = time.monotonic()
    logger.debug("JWKS refreshed, %d keys cached", len(keys))
    return keys


def _get_jwks_key(kid: str) -> dict[str, Any]:
    """Return the JWK for ``kid``, refreshing the cache when allowed.

    Blocking (sync HTTP): runs only inside the threadpool-executed REST auth
    dependency, never on the event loop. A refetch (TTL expiry or unknown kid)
    happens at most once per ``_JWKS_MIN_REFETCH_INTERVAL`` seconds, serialized
    by a lock; otherwise an unknown kid is rejected with 401 straight away. A
    failed fetch falls back to the (stale) cache.
    """
    global _JWKS_LAST_ATTEMPT

    if time.monotonic() - _JWKS_FETCHED_AT < _JWKS_TTL and kid in _JWKS_CACHE:
        return _JWKS_CACHE[kid]

    with _JWKS_LOCK:
        now = time.monotonic()
        # Another thread may have refreshed while we waited for the lock.
        if now - _JWKS_FETCHED_AT < _JWKS_TTL and kid in _JWKS_CACHE:
            return _JWKS_CACHE[kid]
        if now - _JWKS_LAST_ATTEMPT >= _JWKS_MIN_REFETCH_INTERVAL:
            _JWKS_LAST_ATTEMPT = now
            try:
                _fetch_jwks()
            except Exception as exc:
                logger.warning("JWKS fetch failed: %s", exc)
        else:
            logger.debug("JWKS refetch throttled (kid=%s)", kid)
        key = _JWKS_CACHE.get(kid)

    if key is None:
        logger.debug("JWT rejected: unknown signing key kid=%s", kid)
        raise _unauthorized()
    return key


# ---------------------------------------------------------------------------
# JWT verification (REST API path)
# ---------------------------------------------------------------------------


def verify_clerk_jwt(
    token: str, authorized_parties: Collection[str] | None = None
) -> dict[str, Any]:
    """Validate a Clerk session JWT and return its claims.

    Checks signature (JWKS), issuer, expiry, ``sub``, and that ``azp`` is
    present and one of ``authorized_parties`` (resolved from config when not
    given). 401 details are fixed strings; the cause is logged at DEBUG.

    Raises:
        HTTPException 401: If the token is invalid for any reason.
    """
    if authorized_parties is None:
        from pktx.config import resolve_authorized_parties

        authorized_parties = resolve_authorized_parties()

    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        logger.debug("JWT rejected: bad header (%s)", exc)
        raise _unauthorized() from exc

    kid = unverified_header.get("kid", "")
    key = _get_jwks_key(kid)

    issuer = _issuer()
    if not issuer:
        logger.error("CLERK_ISSUER is not configured; rejecting REST JWT")
        raise _unauthorized()

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"verify_aud": False},
        )
    except ExpiredSignatureError as exc:
        raise _unauthorized("Token has expired") from exc
    except JWTError as exc:
        logger.debug("JWT rejected: %s", exc)
        raise _unauthorized() from exc

    if not claims.get("sub"):
        logger.debug("JWT rejected: missing sub")
        raise _unauthorized()

    # Authorized parties: Clerk session tokens always carry azp (the origin of
    # the frontend that minted them). Reject tokens from other origins and
    # tokens without azp (e.g. OAuth access tokens from the same instance).
    azp = claims.get("azp")
    if not isinstance(azp, str) or azp.rstrip("/") not in authorized_parties:
        logger.debug("JWT rejected: azp %r not in authorized parties", azp)
        raise _unauthorized()

    return claims


# ---------------------------------------------------------------------------
# UserContext and FastAPI dependency (REST API)
# ---------------------------------------------------------------------------


@dataclass
class UserContext:
    """Authenticated user identity extracted from a valid Clerk JWT."""

    id: str
    email: str | None
    display_name: str | None


_bearer = HTTPBearer(auto_error=False)


def build_get_current_user(  # type: ignore[no-untyped-def]
    conn: DBConnection, authorized_parties: Collection[str] | None = None
):
    """Return a FastAPI dependency that validates JWTs and upserts users.

    ``authorized_parties`` defaults to ``config.resolve_authorized_parties()``,
    read once here (dependency-build time) so a misconfigured deploy fails at
    startup instead of per request. The dependency is sync, so FastAPI runs it
    in the threadpool: the JWKS fetch and the upsert never block the event loop.
    """
    if authorized_parties is None:
        from pktx.config import resolve_authorized_parties

        authorized_parties = resolve_authorized_parties()
    parties = frozenset(authorized_parties)

    def _dep(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ) -> UserContext:
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header missing",
            )
        claims = verify_clerk_jwt(credentials.credentials, parties)

        user_id: str = claims["sub"]
        email: str | None = claims.get("email") or claims.get("primary_email_address")
        display_name: str | None = (
            claims.get("name") or claims.get("display_name") or claims.get("username")
        )

        upsert_user(conn, user_id, email, display_name)
        return UserContext(id=user_id, email=email, display_name=display_name)

    return _dep


# ---------------------------------------------------------------------------
# MCP OAuth2 resource server auth (FastMCP RemoteAuthProvider + JWTVerifier)
# ---------------------------------------------------------------------------


class _DiagnosticJWTVerifier(JWTVerifier):
    """JWTVerifier that records why a token was rejected, for diagnosis.

    FastMCP's JWTVerifier swallows validation failures, returns ``None``, and
    logs the reason only on its own logger — so our logs show a bare 401
    invalid_token with no cause. This subclass re-logs the rejection on the
    ``pktx`` logger at DEBUG, including the token's unverified header/claims
    next to the expected issuer, making a mismatch (alg, kid, issuer, or an
    opaque non-JWT token) diagnosable. Verification behaviour is unchanged.
    """

    async def verify_token(self, token: str) -> AccessToken | None:
        result = await super().verify_token(token)
        if result is None and logger.isEnabledFor(logging.DEBUG):
            self._log_rejection(token)
        return result

    def _log_rejection(self, token: str) -> None:
        try:
            header = jwt.get_unverified_header(token)
        except JWTError as exc:
            logger.debug("MCP token rejected: not a parseable JWT (%s)", exc)
            return
        try:
            claims = jwt.get_unverified_claims(token)
        except JWTError:
            claims = {}
        logger.debug(
            "MCP token rejected: alg=%s kid=%s token_iss=%s token_aud=%s exp=%s "
            "(expected_iss=%s jwks=%s)",
            header.get("alg"),
            header.get("kid"),
            claims.get("iss"),
            claims.get("aud"),
            claims.get("exp"),
            self.issuer,
            self.jwks_uri,
        )


def build_mcp_auth(pool: "ConnectionPool[Any]") -> OAuthProxy:
    """Build the FastMCP OAuth proxy for the /mcp endpoint.

    Requires PKTX_PUBLIC_URL, CLERK_JWKS_URL, CLERK_ISSUER,
    CLERK_OAUTH_CLIENT_ID, CLERK_OAUTH_CLIENT_SECRET env vars.

    The proxy handles Dynamic Client Registration locally so native MCP clients
    (Claude Desktop, Cursor, VS Code) register with *us*, not Clerk — fixing the
    loopback redirect mismatch where a client registers http://localhost:PORT but
    sends http://127.0.0.1:PORT (distinct strings per OAuth, both allowed here by
    FastMCP's default localhost patterns). Authorize/token are proxied upstream to
    Clerk via one fixed pre-registered redirect URI; the proxy issues its own
    reference JWTs to clients and validates the stored Clerk token on every call.

    Proxy state (registrations, encrypted upstream tokens, JTI mappings, transient
    authorize state) is stored in PostgreSQL via ``pool`` so it is shared across
    serverless instances rather than a per-instance local DiskStore.

    Client identification supports both MCP 2025-11-25 mechanisms: Client ID
    Metadata Documents (``enable_cimd``, the spec's preferred approach — the client
    hosts a JSON document at an HTTPS URL and that URL is its ``client_id``) and
    Dynamic Client Registration at ``/register`` (kept for older clients).

    Audience: the proxy issues its own JWTs to clients bound to ``aud=<public>/mcp``
    and rejects any token whose audience differs, satisfying the spec requirement
    that a resource server only accept tokens minted for it. The *upstream* Clerk
    token — where we are the OAuth client, not the resource — is verified for
    signature (JWKS) and issuer only; its audience is Clerk's own client id.
    """
    from pktx.config import (
        resolve_clerk_issuer,
        resolve_clerk_jwks_url,
        resolve_clerk_oauth_client_id,
        resolve_clerk_oauth_client_secret,
        resolve_extra_client_redirect_uris,
        resolve_public_url,
    )
    from pktx.oauth_store import build_oauth_client_storage

    public = resolve_public_url()
    issuer = resolve_clerk_issuer()
    jwks_uri = resolve_clerk_jwks_url()
    client_secret = resolve_clerk_oauth_client_secret()
    verifier = _DiagnosticJWTVerifier(
        jwks_uri=jwks_uri,
        issuer=issuer,
        audience=None,
        base_url=public,
    )
    logger.info(
        "MCP OAuth proxy configured: issuer=%s jwks_uri=%s resource=%s/mcp",
        issuer,
        jwks_uri,
        public,
    )
    return OAuthProxy(
        upstream_authorization_endpoint=f"{issuer}/oauth/authorize",
        upstream_token_endpoint=f"{issuer}/oauth/token",
        upstream_client_id=resolve_clerk_oauth_client_id(),
        upstream_client_secret=client_secret,
        token_verifier=verifier,
        base_url=public,
        redirect_path="/auth/callback",
        # Loopback tolerance: a client that registers http://127.0.0.1:PORT may
        # authorize with http://localhost:PORT (or vice versa) — distinct strings
        # per OAuth. These patterns accept either host on any port so the mismatch
        # no longer 400s, while still rejecting non-loopback redirects a client
        # never registered. Hosted clients (CIMD documents pointing at an HTTPS
        # callback) are opted in per deployment via PKTX_EXTRA_CLIENT_REDIRECT_URIS;
        # the same allowlist gates DCR and CIMD clients alike.
        allowed_client_redirect_uris=[
            *DEFAULT_LOCALHOST_PATTERNS,
            *resolve_extra_client_redirect_uris(),
        ],
        # MCP 2025-11-25: authorization servers SHOULD support Client ID Metadata
        # Documents. On by default in FastMCP; set explicitly so a library default
        # flip cannot silently drop the capability (and its advertisement via
        # client_id_metadata_document_supported in the AS metadata).
        enable_cimd=True,
        # Shared, encrypted proxy state in PostgreSQL (not a local DiskStore) so
        # the OAuth flow survives across serverless instances and cold starts. The
        # Fernet key is derived from the Clerk OAuth client secret, stable per env.
        client_storage=build_oauth_client_storage(pool, client_secret),
    )


# ---------------------------------------------------------------------------
# MCP tool middleware: bridge access token sub → current_user_id_var
# ---------------------------------------------------------------------------


def _upsert_and_commit(conn: DBConnection, sub: str) -> None:
    """Ensure the users row exists, committed independently of the tool call.

    Committed right away (nothing else is in the scope's transaction yet) so a
    later tool error that rolls the scope back cannot undo it — the per-process
    cache below would otherwise skip the upsert for this sub from then on.
    """
    try:
        upsert_user(conn, sub, None, None)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


class UserContextToolMiddleware(Middleware):
    """Set current_user_id_var from the FastMCP access token for each tool call.

    The first call per ``sub`` in this process upserts the users row, off the
    event loop (``asyncio.to_thread``, which copies the context so the request
    connection scope is visible). Later calls for that sub skip the DB.
    """

    def __init__(self, conn: DBConnection | None = None) -> None:
        self._conn = conn
        self._upserted: set[str] = set()

    async def on_call_tool(self, context, call_next):  # type: ignore[override]
        tok = get_access_token()
        sub = (tok.claims or {}).get("sub") if tok else None
        reset = current_user_id_var.set(sub)
        try:
            if sub and self._conn is not None and sub not in self._upserted:
                try:
                    await asyncio.to_thread(_upsert_and_commit, self._conn, sub)
                    self._upserted.add(sub)
                except Exception as exc:
                    logger.warning("upsert_user failed in MCP tool middleware: %s", exc)
            return await call_next(context)
        finally:
            current_user_id_var.reset(reset)
