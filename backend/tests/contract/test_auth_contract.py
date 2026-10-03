"""Contract tests for authentication and authorisation on all API routes.

Phase 3 tests (T009): 401 on missing token, 200 on valid mock JWT.
Phase 4 tests (T016, T035, T036): 403 on cross-user access.
Plan 016 (T15-T19): MCP OAuth2 resource server contract tests.
"""

import time
from typing import Any
from unittest.mock import patch

import psycopg
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from jose import jwt
from psycopg import Connection
from starlette.testclient import TestClient

from pktx.accomplishment_service import AccomplishmentService
from pktx.api.routes import create_router
from pktx.application_service import ApplicationService
from pktx.auth import build_get_current_user
from pktx.resume_service import ResumeService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _gen_rsa_key_pair() -> tuple[Any, Any]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _public_key_to_jwk(public_key: Any, kid: str = "ck1") -> dict[str, Any]:
    from jose.backends import RSAKey

    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    rsa_key = RSAKey(pem, "RS256")  # pyright: ignore [reportOptionalCall]
    jwk_dict = rsa_key.public_key().to_dict()  # type: ignore[union-attr]
    jwk_dict["kid"] = kid
    jwk_dict["kty"] = "RSA"
    jwk_dict["alg"] = "RS256"
    return jwk_dict


def _make_token(
    private_key: Any,
    kid: str = "ck1",
    sub: str = "user_alice",
    issuer: str = "https://clerk.test",
    email: str = "alice@example.com",
) -> str:
    now = int(time.time())
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return jwt.encode(
        {
            "sub": sub,
            "iss": issuer,
            "iat": now,
            "exp": now + 3600,
            "email": email,
            "azp": "http://testserver",
        },
        pem,
        algorithm="RS256",
        headers={"kid": kid},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _authorized_parties(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tokens above carry azp=http://testserver (027 / M12)."""
    monkeypatch.setenv("CLERK_AUTHORIZED_PARTIES", "http://testserver")


@pytest.fixture
def auth_db(db_conn: Connection[Any]) -> psycopg.Connection:
    """PostgreSQL connection with schema already applied (via db_conn fixture).

    The 'legacy' user is seeded by migrate_v3_to_v4, so no manual insert needed.
    """
    return db_conn


@pytest.fixture
def auth_app(auth_db: psycopg.Connection) -> tuple:  # type: ignore[override]
    """Full app with auth middleware enabled."""
    import pktx.auth as auth_module

    private_key, public_key = _gen_rsa_key_pair()
    jwk_entry = _public_key_to_jwk(public_key, kid="ck1")
    auth_module._JWKS_CACHE = {"ck1": jwk_entry}
    auth_module._JWKS_FETCHED_AT = time.monotonic()

    app = FastAPI()
    get_user = build_get_current_user(auth_db)  # type: ignore[arg-type]
    app.include_router(
        create_router(
            ResumeService(auth_db),  # type: ignore[arg-type]
            app_service=ApplicationService(auth_db),  # type: ignore[arg-type]
            acc_service=AccomplishmentService(auth_db),  # type: ignore[arg-type]
            get_current_user=get_user,
        )
    )
    return TestClient(app, raise_server_exceptions=False), private_key


# ---------------------------------------------------------------------------
# Phase 3 — T009: Basic 401 / 200 contract
# ---------------------------------------------------------------------------


class TestBasicAuthContract:
    """GET /api/resumes without token → 401; with valid token → 200."""

    def test_list_resumes_without_token_returns_401(self, auth_app: tuple) -> None:
        client, _ = auth_app
        response = client.get("/api/resumes")
        assert response.status_code == 401

    def test_list_resumes_with_valid_token_returns_200(self, auth_app: tuple) -> None:
        client, private_key = auth_app
        token = _make_token(private_key, sub="user_alice")
        with patch.dict("os.environ", {"CLERK_ISSUER": "https://clerk.test"}):
            response = client.get(
                "/api/resumes", headers={"Authorization": f"Bearer {token}"}
            )
        assert response.status_code == 200

    def test_health_endpoint_does_not_require_auth(self, auth_app: tuple) -> None:
        client, _ = auth_app
        response = client.get("/health")
        assert response.status_code == 200

    def test_list_applications_without_token_returns_401(self, auth_app: tuple) -> None:
        client, _ = auth_app
        response = client.get("/api/applications")
        assert response.status_code == 401

    def test_list_accomplishments_without_token_returns_401(
        self, auth_app: tuple
    ) -> None:
        client, _ = auth_app
        response = client.get("/api/accomplishments")
        assert response.status_code == 401

    def test_create_resume_without_token_returns_401(self, auth_app: tuple) -> None:
        client, _ = auth_app
        response = client.post("/api/resumes", json={"label": "Test"})
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Phase 4 — T016: 403 on cross-user access for resume/application routes
# ---------------------------------------------------------------------------


class TestCrossUserOwnershipContract:
    """Valid JWT for wrong user → 403 on detail/mutation endpoints."""

    def _make_user_client(
        self,
        auth_db: psycopg.Connection,
        private_key: Any,
        user_id: str,
        email: str,
    ) -> TestClient:

        app = FastAPI()
        get_user = build_get_current_user(auth_db)  # type: ignore[arg-type]
        app.include_router(
            create_router(
                ResumeService(auth_db),  # type: ignore[arg-type]
                app_service=ApplicationService(auth_db),  # type: ignore[arg-type]
                acc_service=AccomplishmentService(auth_db),  # type: ignore[arg-type]
                get_current_user=get_user,
            )
        )

        def _make_client_with_token() -> TestClient:
            token = _make_token(private_key, sub=user_id, email=email)
            client = TestClient(app, raise_server_exceptions=False)
            # Store token for use in tests
            client._auth_token = token  # type: ignore[attr-defined]
            return client

        return _make_client_with_token()

    @pytest.fixture
    def two_user_setup(self, auth_db: psycopg.Connection) -> dict:
        import pktx.auth as auth_module

        private_key, public_key = _gen_rsa_key_pair()
        jwk_entry = _public_key_to_jwk(public_key, kid="ck1")
        auth_module._JWKS_CACHE = {"ck1": jwk_entry}
        auth_module._JWKS_FETCHED_AT = time.monotonic()

        # Create user A
        auth_db.execute(
            "INSERT INTO users (id, email) VALUES ('user_alice', 'alice@test.com')"
        )
        # Create user B
        auth_db.execute(
            "INSERT INTO users (id, email) VALUES ('user_bob', 'bob@test.com')"
        )

        app = FastAPI()
        get_user = build_get_current_user(auth_db)  # type: ignore[arg-type]
        app.include_router(
            create_router(
                ResumeService(auth_db),  # type: ignore[arg-type]
                app_service=ApplicationService(auth_db),  # type: ignore[arg-type]
                acc_service=AccomplishmentService(auth_db),  # type: ignore[arg-type]
                get_current_user=get_user,
            )
        )
        client = TestClient(app, raise_server_exceptions=False)

        alice_token = _make_token(private_key, sub="user_alice", email="alice@test.com")
        bob_token = _make_token(private_key, sub="user_bob", email="bob@test.com")

        return {
            "client": client,
            "alice_token": alice_token,
            "bob_token": bob_token,
            "db": auth_db,
            "private_key": private_key,
        }

    def test_get_resume_by_id_wrong_user_returns_403(
        self, two_user_setup: dict
    ) -> None:
        client = two_user_setup["client"]
        alice_token = two_user_setup["alice_token"]
        bob_token = two_user_setup["bob_token"]

        # Alice creates a resume
        with patch.dict("os.environ", {"CLERK_ISSUER": "https://clerk.test"}):
            resp = client.post(
                "/api/resumes",
                json={"label": "Alice's Resume"},
                headers={"Authorization": f"Bearer {alice_token}"},
            )
        assert resp.status_code == 201
        alice_resume_id = resp.json()["id"]

        # Bob tries to access Alice's resume → 403
        with patch.dict("os.environ", {"CLERK_ISSUER": "https://clerk.test"}):
            resp = client.get(
                f"/api/resumes/{alice_resume_id}",
                headers={"Authorization": f"Bearer {bob_token}"},
            )
        assert resp.status_code == 403

    def test_patch_resume_wrong_user_returns_403(self, two_user_setup: dict) -> None:
        client = two_user_setup["client"]
        alice_token = two_user_setup["alice_token"]
        bob_token = two_user_setup["bob_token"]

        with patch.dict("os.environ", {"CLERK_ISSUER": "https://clerk.test"}):
            resp = client.post(
                "/api/resumes",
                json={"label": "Alice Resume"},
                headers={"Authorization": f"Bearer {alice_token}"},
            )
        alice_resume_id = resp.json()["id"]

        with patch.dict("os.environ", {"CLERK_ISSUER": "https://clerk.test"}):
            resp = client.patch(
                f"/api/resumes/{alice_resume_id}",
                json={"label": "Hacked"},
                headers={"Authorization": f"Bearer {bob_token}"},
            )
        assert resp.status_code == 403

    def test_delete_resume_wrong_user_returns_403(self, two_user_setup: dict) -> None:
        client = two_user_setup["client"]
        alice_token = two_user_setup["alice_token"]
        bob_token = two_user_setup["bob_token"]

        with patch.dict("os.environ", {"CLERK_ISSUER": "https://clerk.test"}):
            resp = client.post(
                "/api/resumes",
                json={"label": "Alice Resume"},
                headers={"Authorization": f"Bearer {alice_token}"},
            )
        alice_resume_id = resp.json()["id"]

        with patch.dict("os.environ", {"CLERK_ISSUER": "https://clerk.test"}):
            resp = client.delete(
                f"/api/resumes/{alice_resume_id}",
                headers={"Authorization": f"Bearer {bob_token}"},
            )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Plan 017 — MCP OAuth DCR proxy contract tests (FastMCP OAuthProxy)
# ---------------------------------------------------------------------------

_TEST_PUBLIC_URL = "https://pktx.test"
_TEST_ISSUER = "https://clerk.test"
_TEST_RESOURCE = f"{_TEST_PUBLIC_URL}/mcp"


def _build_mcp_proxy(private_key: Any) -> Any:
    """Build a production-mirroring OAuthProxy provider for testing.

    Uses an in-memory client store so no proxy state hits disk. Signature +
    issuer are enforced by the token verifier; audience is not (Clerk mints
    tokens with aud=client_id).
    """
    from fastmcp.server.auth.oauth_proxy import OAuthProxy
    from fastmcp.server.auth.providers.jwt import JWTVerifier
    from fastmcp.server.auth.redirect_validation import DEFAULT_LOCALHOST_PATTERNS
    from key_value.aio.stores.memory import MemoryStore

    pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    verifier = JWTVerifier(
        public_key=pem,
        issuer=_TEST_ISSUER,
        audience=None,
        base_url=_TEST_PUBLIC_URL,
    )
    return OAuthProxy(
        upstream_authorization_endpoint=f"{_TEST_ISSUER}/oauth/authorize",
        upstream_token_endpoint=f"{_TEST_ISSUER}/oauth/token",
        upstream_client_id="test_client_id",
        upstream_client_secret="test_client_secret_at_least_12_chars",
        token_verifier=verifier,
        base_url=_TEST_PUBLIC_URL,
        redirect_path="/auth/callback",
        allowed_client_redirect_uris=list(DEFAULT_LOCALHOST_PATTERNS),
        client_storage=MemoryStore(),
    )


def _build_mcp_oauth_app(private_key: Any) -> Any:
    """Build a FastMCP ASGI app fronted by the OAuth DCR proxy for testing."""
    from fastmcp import FastMCP

    m = FastMCP("pktx", auth=_build_mcp_proxy(private_key))

    @m.tool()
    def ping() -> str:
        return "pong"

    return m.http_app(path="/mcp", stateless_http=True)


def _make_mcp_token(
    private_key: Any,
    kid: str = "ck1",
    sub: str = "user_alice",
    issuer: str = _TEST_ISSUER,
    audience: str = _TEST_RESOURCE,
    exp_offset: int = 3600,
) -> str:
    now = int(time.time())
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    claims: dict[str, Any] = {
        "sub": sub,
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + exp_offset,
    }
    return jwt.encode(claims, pem, algorithm="RS256", headers={"kid": kid})


@pytest.fixture(scope="module")
def mcp_oauth_key_pair() -> tuple[Any, Any]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


class TestMCPProxyProtectedResourceMetadata:
    """T07: /.well-known/oauth-protected-resource/mcp advertises our own domain.

    With the DCR proxy the authorization server is *us*, not Clerk — clients
    register and authorize against our base_url, which then proxies to Clerk.
    """

    def test_metadata_route_returns_200(self, mcp_oauth_key_pair: tuple) -> None:
        private_key, _ = mcp_oauth_key_pair
        app = _build_mcp_oauth_app(private_key)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/.well-known/oauth-protected-resource/mcp")
        assert resp.status_code == 200

    def test_metadata_body_has_resource(self, mcp_oauth_key_pair: tuple) -> None:
        private_key, _ = mcp_oauth_key_pair
        app = _build_mcp_oauth_app(private_key)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/.well-known/oauth-protected-resource/mcp")
        body = resp.json()
        assert "resource" in body

    def test_authorization_server_is_our_base_url(
        self, mcp_oauth_key_pair: tuple
    ) -> None:
        private_key, _ = mcp_oauth_key_pair
        app = _build_mcp_oauth_app(private_key)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/.well-known/oauth-protected-resource/mcp")
        body = resp.json()
        assert "authorization_servers" in body
        servers = [s.rstrip("/") for s in body["authorization_servers"]]
        # Proxy advertises itself as the AS; Clerk stays upstream and hidden.
        assert _TEST_PUBLIC_URL.rstrip("/") in servers
        assert _TEST_ISSUER.rstrip("/") not in servers


class TestMCPProxyAuthorizationServerMetadata:
    """T07: AS metadata endpoint exposes register/authorize/token on our domain."""

    def test_as_metadata_returns_200(self, mcp_oauth_key_pair: tuple) -> None:
        private_key, _ = mcp_oauth_key_pair
        app = _build_mcp_oauth_app(private_key)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/.well-known/oauth-authorization-server")
        assert resp.status_code == 200

    def test_as_metadata_advertises_dcr_and_flow_endpoints(
        self, mcp_oauth_key_pair: tuple
    ) -> None:
        private_key, _ = mcp_oauth_key_pair
        app = _build_mcp_oauth_app(private_key)
        client = TestClient(app, raise_server_exceptions=False)
        body = client.get("/.well-known/oauth-authorization-server").json()
        for endpoint in (
            "registration_endpoint",
            "authorization_endpoint",
            "token_endpoint",
        ):
            assert endpoint in body, f"missing {endpoint}"
            assert body[endpoint].startswith(_TEST_PUBLIC_URL), body[endpoint]


def _pkce_challenge() -> str:
    import base64
    import hashlib
    import secrets

    verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


class TestMCPProxyLoopbackRegistration:
    """T08: loopback host mismatch is tolerated at /authorize — the core 017 fix.

    Native clients register one loopback host (e.g. http://127.0.0.1:PORT) but
    send the other (http://localhost:PORT). Per OAuth these are distinct strings;
    Clerk's exact-match validation 400s. Our proxy configures localhost patterns
    so either host on any port is accepted, while a non-loopback redirect the
    client never registered is still rejected.
    """

    def _register(self, app: Any, redirect_uri: str) -> Any:
        client = TestClient(app, raise_server_exceptions=False)
        return client.post(
            "/register",
            json={
                "redirect_uris": [redirect_uri],
                "token_endpoint_auth_method": "none",
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
            },
        )

    def _authorize(self, client: Any, client_id: str, redirect_uri: str) -> Any:
        return client.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "code_challenge": _pkce_challenge(),
                "code_challenge_method": "S256",
                "state": "xyz",
            },
            follow_redirects=False,
        )

    def test_register_accepts_both_loopback_variants(
        self, mcp_oauth_key_pair: tuple
    ) -> None:
        private_key, _ = mcp_oauth_key_pair
        app = _build_mcp_oauth_app(private_key)
        for uri in (
            "http://127.0.0.1:33418/callback",
            "http://localhost:51000/callback",
        ):
            resp = self._register(app, uri)
            assert resp.status_code == 201, resp.text
            assert "client_id" in resp.json()

    def test_authorize_tolerates_loopback_host_mismatch(
        self, mcp_oauth_key_pair: tuple
    ) -> None:
        # Register 127.0.0.1, then authorize with localhost on the same port.
        private_key, _ = mcp_oauth_key_pair
        app = _build_mcp_oauth_app(private_key)
        client = TestClient(app, raise_server_exceptions=False)
        client_id = self._register(app, "http://127.0.0.1:33418/callback").json()[
            "client_id"
        ]
        resp = self._authorize(client, client_id, "http://localhost:33418/callback")
        # 302 → proceeds into the flow (consent / upstream). A redirect_uri
        # rejection would be 400; that must NOT happen for a loopback variant.
        assert resp.status_code != 400, resp.text
        assert resp.status_code in (302, 303, 307)

    def test_authorize_rejects_unregistered_non_loopback(
        self, mcp_oauth_key_pair: tuple
    ) -> None:
        private_key, _ = mcp_oauth_key_pair
        app = _build_mcp_oauth_app(private_key)
        client = TestClient(app, raise_server_exceptions=False)
        client_id = self._register(app, "http://127.0.0.1:33418/callback").json()[
            "client_id"
        ]
        resp = self._authorize(client, client_id, "https://evil.example.com/callback")
        assert resp.status_code == 400, resp.text


class TestMCPProxyUnauthenticated:
    """T10: Unauthenticated POST /mcp → 401 with WWW-Authenticate header."""

    def test_unauth_post_returns_401(self, mcp_oauth_key_pair: tuple) -> None:
        private_key, _ = mcp_oauth_key_pair
        app = _build_mcp_oauth_app(private_key)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/mcp", json={"jsonrpc": "2.0", "method": "tools/list", "id": 1}
        )
        assert resp.status_code == 401

    def test_unauth_post_has_www_authenticate_header(
        self, mcp_oauth_key_pair: tuple
    ) -> None:
        private_key, _ = mcp_oauth_key_pair
        app = _build_mcp_oauth_app(private_key)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/mcp", json={"jsonrpc": "2.0", "method": "tools/list", "id": 1}
        )
        assert "www-authenticate" in {k.lower(): v for k, v in resp.headers.items()}

    def test_www_authenticate_references_metadata_url(
        self, mcp_oauth_key_pair: tuple
    ) -> None:
        private_key, _ = mcp_oauth_key_pair
        app = _build_mcp_oauth_app(private_key)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/mcp", json={"jsonrpc": "2.0", "method": "tools/list", "id": 1}
        )
        www_auth = resp.headers.get("www-authenticate", "")
        assert "/.well-known/oauth-protected-resource/mcp" in www_auth


class TestMCPProxyTokenRejection:
    """T10: raw tokens are rejected — clients must use proxy-issued reference JWTs.

    A directly-minted Clerk-style JWT is NOT a proxy token: it carries no JTI
    mapping to a stored upstream token, so the swap in load_access_token fails.
    """

    def test_raw_clerk_token_rejected(self, mcp_oauth_key_pair: tuple) -> None:
        private_key, _ = mcp_oauth_key_pair
        app = _build_mcp_oauth_app(private_key)
        token = _make_mcp_token(private_key)
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json, text/event-stream",
                },
            )
        assert resp.status_code == 401

    def test_garbage_token_returns_401(self, mcp_oauth_key_pair: tuple) -> None:
        private_key, _ = mcp_oauth_key_pair
        app = _build_mcp_oauth_app(private_key)
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
                headers={
                    "Authorization": "Bearer not-a-real-token",
                    "Accept": "application/json, text/event-stream",
                },
            )
        assert resp.status_code == 401


class TestMCPWellKnownRouteOrdering:
    """T10: Well-known route not shadowed by SPA static catch-all."""

    def test_well_known_route_in_mcp_app_routes(
        self, mcp_oauth_key_pair: tuple
    ) -> None:
        """The /.well-known/... route is present in mcp_app.routes before any mount."""
        private_key, _ = mcp_oauth_key_pair
        app = _build_mcp_oauth_app(private_key)
        paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert any("/.well-known/oauth-protected-resource/mcp" in p for p in paths)

    def test_well_known_route_precedes_mcp_route(
        self, mcp_oauth_key_pair: tuple
    ) -> None:
        """Well-known route index < /mcp route index in mcp_app.routes."""
        private_key, _ = mcp_oauth_key_pair
        app = _build_mcp_oauth_app(private_key)
        paths = [r.path for r in app.routes if hasattr(r, "path")]
        wk_idx = next(i for i, p in enumerate(paths) if "/.well-known" in p)
        mcp_idx = next(i for i, p in enumerate(paths) if p == "/mcp")
        assert wk_idx < mcp_idx


# ---------------------------------------------------------------------------
# Plan 025 — MCP 2025-11-25 authorization spec gaps (CIMD, audience, root PRM)
# ---------------------------------------------------------------------------


def _build_mcp_proxy_and_app(
    private_key: Any, extra_redirect_uris: list[str] | None = None
) -> tuple[Any, Any]:
    """Build the OAuth proxy plus its ASGI app, mirroring build_mcp_auth wiring."""
    from fastmcp import FastMCP
    from fastmcp.server.auth.oauth_proxy import OAuthProxy
    from fastmcp.server.auth.providers.jwt import JWTVerifier
    from fastmcp.server.auth.redirect_validation import DEFAULT_LOCALHOST_PATTERNS
    from key_value.aio.stores.memory import MemoryStore

    pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    proxy = OAuthProxy(
        upstream_authorization_endpoint=f"{_TEST_ISSUER}/oauth/authorize",
        upstream_token_endpoint=f"{_TEST_ISSUER}/oauth/token",
        upstream_client_id="test_client_id",
        upstream_client_secret="test_client_secret_at_least_12_chars",
        token_verifier=JWTVerifier(
            public_key=pem,
            issuer=_TEST_ISSUER,
            audience=None,
            base_url=_TEST_PUBLIC_URL,
        ),
        base_url=_TEST_PUBLIC_URL,
        redirect_path="/auth/callback",
        allowed_client_redirect_uris=[
            *DEFAULT_LOCALHOST_PATTERNS,
            *(extra_redirect_uris or []),
        ],
        client_storage=MemoryStore(),
        enable_cimd=True,
    )
    m = FastMCP("pktx", auth=proxy)

    @m.tool()
    def ping() -> str:
        return "pong"

    return proxy, m.http_app(path="/mcp", stateless_http=True)


class TestMCPProxyCIMD:
    """MCP 2025-11-25: authorization servers SHOULD support CIMD client ids."""

    def test_as_metadata_advertises_cimd_support(
        self, mcp_oauth_key_pair: tuple
    ) -> None:
        private_key, _ = mcp_oauth_key_pair
        _, app = _build_mcp_proxy_and_app(private_key)
        client = TestClient(app, raise_server_exceptions=False)
        body = client.get("/.well-known/oauth-authorization-server").json()
        assert body.get("client_id_metadata_document_supported") is True

    def test_as_metadata_offers_secretless_client_auth(
        self, mcp_oauth_key_pair: tuple
    ) -> None:
        """CIMD clients hold no shared secret: auth is none or private_key_jwt."""
        private_key, _ = mcp_oauth_key_pair
        _, app = _build_mcp_proxy_and_app(private_key)
        client = TestClient(app, raise_server_exceptions=False)
        body = client.get("/.well-known/oauth-authorization-server").json()
        methods = body["token_endpoint_auth_methods_supported"]
        assert "none" in methods
        assert "private_key_jwt" in methods

    def test_dcr_registration_endpoint_still_advertised(
        self, mcp_oauth_key_pair: tuple
    ) -> None:
        """DCR stays available: the spec keeps it for clients that predate CIMD."""
        private_key, _ = mcp_oauth_key_pair
        _, app = _build_mcp_proxy_and_app(private_key)
        client = TestClient(app, raise_server_exceptions=False)
        body = client.get("/.well-known/oauth-authorization-server").json()
        assert body["registration_endpoint"].startswith(_TEST_PUBLIC_URL)

    def test_https_url_client_id_is_treated_as_cimd(
        self, mcp_oauth_key_pair: tuple
    ) -> None:
        private_key, _ = mcp_oauth_key_pair
        proxy, _app = _build_mcp_proxy_and_app(private_key)
        manager = proxy._cimd_manager
        assert manager is not None
        assert manager.is_cimd_client_id("https://app.example.com/client.json")

    def test_opaque_client_id_is_not_treated_as_cimd(
        self, mcp_oauth_key_pair: tuple
    ) -> None:
        """DCR-issued ids stay on the registered-client path, not the fetch path."""
        private_key, _ = mcp_oauth_key_pair
        proxy, _app = _build_mcp_proxy_and_app(private_key)
        manager = proxy._cimd_manager
        assert manager is not None
        assert not manager.is_cimd_client_id("dcr_generated_client_id")


class TestMCPProxyTokenAudience:
    """MCP 2025-11-25: a resource server MUST only accept tokens minted for it."""

    def test_issued_tokens_are_bound_to_the_mcp_resource_url(
        self, mcp_oauth_key_pair: tuple
    ) -> None:
        private_key, _ = mcp_oauth_key_pair
        proxy, _app = _build_mcp_proxy_and_app(private_key)
        assert proxy.jwt_issuer.audience.rstrip("/") == _TEST_RESOURCE

    def test_token_for_another_audience_is_rejected(
        self, mcp_oauth_key_pair: tuple
    ) -> None:
        """Same signing key, foreign aud — must not validate (no token passthrough)."""
        from fastmcp.server.auth.jwt_issuer import JWTIssuer
        from joserfc.errors import JoseError

        private_key, _ = mcp_oauth_key_pair
        proxy, _app = _build_mcp_proxy_and_app(private_key)
        foreign = JWTIssuer(
            issuer=proxy.jwt_issuer.issuer,
            audience="https://other.example.com/mcp",
            signing_key=proxy._jwt_signing_key,
        )
        token = foreign.issue_access_token(
            client_id="c1", scopes=[], jti="jti-foreign", expires_in=3600
        )
        with pytest.raises(JoseError):
            proxy.jwt_issuer.verify_token(token)

    def test_token_for_this_resource_validates(self, mcp_oauth_key_pair: tuple) -> None:
        private_key, _ = mcp_oauth_key_pair
        proxy, _app = _build_mcp_proxy_and_app(private_key)
        token = proxy.jwt_issuer.issue_access_token(
            client_id="c1", scopes=[], jti="jti-ours", expires_in=3600
        )
        claims = proxy.jwt_issuer.verify_token(token)
        assert claims["aud"].rstrip("/") == _TEST_RESOURCE


class TestRootProtectedResourceMetadataAlias:
    """RFC 9728 root fallback: clients probe the suffixed path, then the root."""

    def _app_with_alias(self, private_key: Any) -> FastAPI:
        from pktx.server import _add_root_resource_metadata_alias

        _, mcp_app = _build_mcp_proxy_and_app(private_key)
        app = FastAPI()
        for route in mcp_app.routes:
            app.router.routes.append(route)
        _add_root_resource_metadata_alias(app, mcp_app)
        return app

    def test_root_path_returns_200(self, mcp_oauth_key_pair: tuple) -> None:
        private_key, _ = mcp_oauth_key_pair
        client = TestClient(self._app_with_alias(private_key))
        assert client.get("/.well-known/oauth-protected-resource").status_code == 200

    def test_root_and_suffixed_documents_match(self, mcp_oauth_key_pair: tuple) -> None:
        private_key, _ = mcp_oauth_key_pair
        client = TestClient(self._app_with_alias(private_key))
        root = client.get("/.well-known/oauth-protected-resource").json()
        suffixed = client.get("/.well-known/oauth-protected-resource/mcp").json()
        assert root == suffixed
        assert root["resource"].rstrip("/") == _TEST_RESOURCE


class TestHostedClientRedirectAllowlist:
    """Hosted (non-loopback) CIMD clients need their HTTPS callback allowlisted."""

    def _register(self, app: Any, redirect_uri: str) -> Any:
        client = TestClient(app, raise_server_exceptions=False)
        return client.post(
            "/register",
            json={
                "redirect_uris": [redirect_uri],
                "token_endpoint_auth_method": "none",
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
            },
        )

    def test_hosted_redirect_rejected_by_default(
        self, mcp_oauth_key_pair: tuple
    ) -> None:
        private_key, _ = mcp_oauth_key_pair
        _, app = _build_mcp_proxy_and_app(private_key)
        client = TestClient(app, raise_server_exceptions=False)
        client_id = self._register(app, "http://127.0.0.1:33418/callback").json()[
            "client_id"
        ]
        resp = client.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": "https://client.example.com/callback",
                "code_challenge": _pkce_challenge(),
                "code_challenge_method": "S256",
                "state": "xyz",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 400, resp.text

    def test_hosted_redirect_allowed_when_configured(
        self, mcp_oauth_key_pair: tuple
    ) -> None:
        private_key, _ = mcp_oauth_key_pair
        _, app = _build_mcp_proxy_and_app(
            private_key, extra_redirect_uris=["https://client.example.com/callback"]
        )
        client = TestClient(app, raise_server_exceptions=False)
        client_id = self._register(app, "https://client.example.com/callback").json()[
            "client_id"
        ]
        resp = client.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": "https://client.example.com/callback",
                "code_challenge": _pkce_challenge(),
                "code_challenge_method": "S256",
                "state": "xyz",
            },
            follow_redirects=False,
        )
        assert resp.status_code != 400, resp.text
        assert resp.status_code in (302, 303, 307)
