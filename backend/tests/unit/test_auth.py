"""Unit tests for pktx.auth — JWKS caching and JWT validation."""

import time
from typing import Any
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from jwt.algorithms import RSAAlgorithm


@pytest.fixture(autouse=True)
def _authorized_parties(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tokens minted below carry azp=http://testserver (027 / M12)."""
    monkeypatch.setenv("CLERK_AUTHORIZED_PARTIES", "http://testserver")


# ---------------------------------------------------------------------------
# Helpers: generate an RSA key pair and build a minimal JWKS entry
# ---------------------------------------------------------------------------


def _gen_rsa_key_pair() -> tuple[Any, Any]:
    """Return (private_key, public_key) for test use."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    return private_key, private_key.public_key()


def _public_key_to_jwk(public_key: Any, kid: str = "test-kid") -> dict[str, Any]:
    """Convert an RSA public key to a minimal JWK dict usable by PyJWT."""
    jwk_dict = RSAAlgorithm.to_jwk(public_key, as_dict=True)
    jwk_dict["kid"] = kid
    jwk_dict["kty"] = "RSA"
    jwk_dict["alg"] = "RS256"
    return jwk_dict


def _make_token(
    private_key: Any,
    kid: str = "test-kid",
    sub: str = "user_test_123",
    issuer: str = "https://clerk.test",
    exp_offset: int = 3600,
) -> str:
    """Create a signed RS256 JWT for testing."""
    now = int(time.time())
    claims = {
        "sub": sub,
        "iss": issuer,
        "iat": now,
        "exp": now + exp_offset,
        "email": "test@example.com",
        "azp": "http://testserver",
    }
    headers = {"kid": kid}
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return jwt.encode(claims, pem, algorithm="RS256", headers=headers)


# ---------------------------------------------------------------------------
# Tests for JWKS cache helpers
# ---------------------------------------------------------------------------


class TestJWKSCache:
    """Tests for the in-memory JWKS cache behaviour."""

    def setup_method(self) -> None:
        """Reset the module-level cache state before each test."""
        import pktx.auth as auth_module

        auth_module._JWKS_CACHE = {}
        auth_module._JWKS_FETCHED_AT = 0.0
        auth_module._JWKS_LAST_ATTEMPT = float("-inf")

    def test_cache_hit_returns_key_without_fetch(self) -> None:
        """A known kid within TTL is returned without an HTTP call."""
        import pktx.auth as auth_module

        key_data = {"kid": "k1", "kty": "RSA"}
        auth_module._JWKS_CACHE = {"k1": key_data}
        auth_module._JWKS_FETCHED_AT = time.monotonic()  # fresh

        with patch("pktx.auth._fetch_jwks") as mock_fetch:
            result = auth_module._get_jwks_key("k1")

        mock_fetch.assert_not_called()
        assert result == key_data

    def test_cache_miss_triggers_fetch(self) -> None:
        """An unknown kid in a fresh cache triggers a JWKS refresh."""
        import pktx.auth as auth_module

        auth_module._JWKS_CACHE = {}
        auth_module._JWKS_FETCHED_AT = time.monotonic()  # fresh but empty

        key_data = {"kid": "k2", "kty": "RSA"}

        def _fake_fetch() -> dict[str, Any]:
            auth_module._JWKS_CACHE = {"k2": key_data}
            auth_module._JWKS_FETCHED_AT = time.monotonic()
            return auth_module._JWKS_CACHE

        with patch("pktx.auth._fetch_jwks", side_effect=_fake_fetch):
            result = auth_module._get_jwks_key("k2")

        assert result == key_data

    def test_expired_ttl_triggers_refresh(self) -> None:
        """An expired cache forces a fresh JWKS fetch even for a known kid."""
        import pktx.auth as auth_module

        key_data = {"kid": "k3", "kty": "RSA"}
        auth_module._JWKS_CACHE = {"k3": key_data}
        auth_module._JWKS_FETCHED_AT = time.monotonic() - 7200.0  # 2h ago — expired

        refreshed = {"kid": "k3", "kty": "RSA", "refreshed": True}

        def _fake_fetch() -> dict[str, Any]:
            auth_module._JWKS_CACHE = {"k3": refreshed}
            auth_module._JWKS_FETCHED_AT = time.monotonic()
            return auth_module._JWKS_CACHE

        with patch("pktx.auth._fetch_jwks", side_effect=_fake_fetch) as mock_fetch:
            result = auth_module._get_jwks_key("k3")

        mock_fetch.assert_called_once()
        assert result["refreshed"] is True

    def test_unknown_kid_after_refresh_raises_401(self) -> None:
        """If kid is still absent after a fresh JWKS fetch, a 401 is raised."""
        import pktx.auth as auth_module

        auth_module._JWKS_CACHE = {}
        auth_module._JWKS_FETCHED_AT = 0.0

        def _fake_fetch() -> dict[str, Any]:
            auth_module._JWKS_CACHE = {}
            auth_module._JWKS_FETCHED_AT = time.monotonic()
            return auth_module._JWKS_CACHE

        with patch("pktx.auth._fetch_jwks", side_effect=_fake_fetch):
            with pytest.raises(HTTPException) as exc_info:
                auth_module._get_jwks_key("unknown-kid")

        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Tests for verify_clerk_jwt
# ---------------------------------------------------------------------------


class TestVerifyClerkJwt:
    """Tests for the verify_clerk_jwt function."""

    def setup_method(self) -> None:
        import pktx.auth as auth_module

        auth_module._JWKS_CACHE = {}
        auth_module._JWKS_FETCHED_AT = 0.0
        auth_module._JWKS_LAST_ATTEMPT = float("-inf")

    def _setup_valid_key(
        self, kid: str = "test-kid", issuer: str = "https://clerk.test"
    ) -> tuple[Any, str]:
        """Set up JWKS cache with a test key and return (private_key, issuer)."""
        import pktx.auth as auth_module

        private_key, public_key = _gen_rsa_key_pair()
        jwk_entry = _public_key_to_jwk(public_key, kid=kid)
        auth_module._JWKS_CACHE = {kid: jwk_entry}
        auth_module._JWKS_FETCHED_AT = time.monotonic()
        return private_key, issuer

    def test_valid_token_returns_claims(self) -> None:
        """A valid JWT with matching issuer and sub returns claims dict."""
        private_key, issuer = self._setup_valid_key()
        token = _make_token(private_key, issuer=issuer)

        with patch.dict("os.environ", {"CLERK_ISSUER": issuer}):
            claims = __import__(
                "pktx.auth", fromlist=["verify_clerk_jwt"]
            ).verify_clerk_jwt(token)

        assert claims["sub"] == "user_test_123"
        assert claims["email"] == "test@example.com"

    def test_expired_token_raises_401(self) -> None:
        """An expired JWT raises HTTP 401."""
        private_key, issuer = self._setup_valid_key()
        token = _make_token(private_key, issuer=issuer, exp_offset=-3600)

        with patch.dict("os.environ", {"CLERK_ISSUER": issuer}):
            with pytest.raises(HTTPException) as exc_info:
                __import__("pktx.auth", fromlist=["verify_clerk_jwt"]).verify_clerk_jwt(
                    token
                )

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_wrong_issuer_raises_401(self) -> None:
        """A JWT signed with a different issuer fails validation."""
        private_key, _ = self._setup_valid_key()
        token = _make_token(private_key, issuer="https://evil.example.com")

        with patch.dict("os.environ", {"CLERK_ISSUER": "https://clerk.test"}):
            with pytest.raises(HTTPException) as exc_info:
                __import__("pktx.auth", fromlist=["verify_clerk_jwt"]).verify_clerk_jwt(
                    token
                )

        assert exc_info.value.status_code == 401

    def test_missing_sub_raises_401(self) -> None:
        """A JWT without a 'sub' claim raises HTTP 401."""
        private_key, issuer = self._setup_valid_key()
        # Craft a token without sub
        now = int(time.time())
        claims_no_sub = {
            "iss": issuer,
            "iat": now,
            "exp": now + 3600,
        }
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
        token = jwt.encode(
            claims_no_sub, pem, algorithm="RS256", headers={"kid": "test-kid"}
        )

        with patch.dict("os.environ", {"CLERK_ISSUER": issuer}):
            with pytest.raises(HTTPException) as exc_info:
                __import__("pktx.auth", fromlist=["verify_clerk_jwt"]).verify_clerk_jwt(
                    token
                )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid token"

    def test_malformed_token_raises_401(self) -> None:
        """A garbage string raises HTTP 401."""
        with patch.dict("os.environ", {"CLERK_ISSUER": "https://clerk.test"}):
            with pytest.raises(HTTPException) as exc_info:
                __import__("pktx.auth", fromlist=["verify_clerk_jwt"]).verify_clerk_jwt(
                    "not.a.jwt"
                )

        assert exc_info.value.status_code == 401

    def test_iat_slightly_in_future_accepted(self) -> None:
        """Clock skew: a just-minted token whose iat is ahead of us still verifies."""
        private_key, issuer = self._setup_valid_key()
        now = int(time.time())
        claims = {
            "sub": "user_test_123",
            "iss": issuer,
            "iat": now + 5,
            "exp": now + 3600,
            "azp": "http://testserver",
        }
        token = jwt.encode(
            claims, private_key, algorithm="RS256", headers={"kid": "test-kid"}
        )

        with patch.dict("os.environ", {"CLERK_ISSUER": issuer}):
            claims_out = __import__(
                "pktx.auth", fromlist=["verify_clerk_jwt"]
            ).verify_clerk_jwt(token)

        assert claims_out["sub"] == "user_test_123"

    @pytest.mark.parametrize(
        ("algorithm", "key"), [("none", None), ("HS256", "s" * 32)]
    )
    def test_non_rs256_token_rejected(self, algorithm: str, key: Any) -> None:
        """Only RS256 is accepted: alg=none and HMAC tokens get 401."""
        _, issuer = self._setup_valid_key()
        now = int(time.time())
        claims = {
            "sub": "user_test_123",
            "iss": issuer,
            "iat": now,
            "exp": now + 3600,
            "azp": "http://testserver",
        }
        token = jwt.encode(
            claims, key, algorithm=algorithm, headers={"kid": "test-kid"}
        )

        with patch.dict("os.environ", {"CLERK_ISSUER": issuer}):
            with pytest.raises(HTTPException) as exc_info:
                __import__("pktx.auth", fromlist=["verify_clerk_jwt"]).verify_clerk_jwt(
                    token
                )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid token"

    @pytest.mark.parametrize(
        "bad_jwk",
        [
            {"kid": "test-kid", "kty": "RSA"},
            {"kid": "test-kid", "kty": "oct", "k": "c2VjcmV0"},
            {"kid": "test-kid"},
        ],
    )
    def test_unusable_jwk_is_401_not_500(self, bad_jwk: dict[str, Any]) -> None:
        """A malformed or non-RSA JWKS entry rejects the token instead of crashing."""
        import pktx.auth as auth_module

        private_key, issuer = self._setup_valid_key()
        auth_module._JWKS_CACHE = {"test-kid": bad_jwk}
        token = _make_token(private_key, issuer=issuer)

        with patch.dict("os.environ", {"CLERK_ISSUER": issuer}):
            with pytest.raises(HTTPException) as exc_info:
                auth_module.verify_clerk_jwt(token)

        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Plan 025: build_mcp_auth wiring (CIMD + redirect allowlist)
# ---------------------------------------------------------------------------


_MCP_AUTH_ENV = {
    "PKTX_PUBLIC_URL": "https://pktx.test",
    "CLERK_ISSUER": "https://clerk.test",
    "CLERK_JWKS_URL": "https://clerk.test/.well-known/jwks.json",
    "CLERK_OAUTH_CLIENT_ID": "test_client_id",
    "CLERK_OAUTH_CLIENT_SECRET": "test_client_secret_at_least_12_chars",
}


def _build_auth(extra_redirects: str | None = None) -> Any:
    """Build the production MCP auth provider against a stand-in pool."""
    from unittest.mock import MagicMock

    from pktx.auth import build_mcp_auth

    env = dict(_MCP_AUTH_ENV)
    if extra_redirects is not None:
        env["PKTX_EXTRA_CLIENT_REDIRECT_URIS"] = extra_redirects
    with patch.dict("os.environ", env, clear=False):
        return build_mcp_auth(MagicMock())


class TestBuildMcpAuthWiring:
    """The proxy we ship must support CIMD and gate redirects to loopback."""

    def test_cimd_is_enabled(self) -> None:
        proxy = _build_auth()
        assert proxy._cimd_manager is not None

    def test_loopback_patterns_are_allowed(self) -> None:
        proxy = _build_auth()
        assert "http://localhost:*" in proxy._allowed_client_redirect_uris
        assert "http://127.0.0.1:*" in proxy._allowed_client_redirect_uris

    def test_extra_redirect_uris_are_appended(self) -> None:
        proxy = _build_auth("https://client.example.com/callback")
        allowed = proxy._allowed_client_redirect_uris
        assert "https://client.example.com/callback" in allowed
        assert "http://localhost:*" in allowed

    def test_cimd_manager_shares_the_redirect_allowlist(self) -> None:
        """A CIMD document cannot smuggle in a redirect the allowlist rejects."""
        proxy = _build_auth("https://client.example.com/callback")
        assert proxy._cimd_manager is not None
        assert (
            "https://client.example.com/callback"
            in proxy._cimd_manager.allowed_redirect_uri_patterns
        )


class TestChatGptConnectorRedirects:
    """ChatGPT derives a per-connector callback, so it needs a wildcard entry.

    Observed shape: https://chatgpt.com/connector/oauth/<connector-id>. Without
    an allowlist entry the proxy answers the authorize call with
    "Redirect URI ... does not match allowed patterns".
    """

    _PATTERNS = (
        "https://chatgpt.com/connector/oauth/*,"
        "https://chatgpt.com/connector_platform_oauth_redirect"
    )

    def _validate(self, redirect_uri: str) -> bool:
        from fastmcp.server.auth.redirect_validation import validate_redirect_uri

        proxy = _build_auth(self._PATTERNS)
        return validate_redirect_uri(redirect_uri, proxy._allowed_client_redirect_uris)

    def test_per_connector_callback_is_allowed(self) -> None:
        assert self._validate("https://chatgpt.com/connector/oauth/u9m_SO-e_jDr")

    def test_platform_callback_is_allowed(self) -> None:
        assert self._validate("https://chatgpt.com/connector_platform_oauth_redirect")

    def test_lookalike_host_is_rejected(self) -> None:
        assert not self._validate("https://chatgpt.com.evil.test/connector/oauth/x")

    def test_other_path_on_same_host_is_rejected(self) -> None:
        assert not self._validate("https://chatgpt.com/somewhere/else")

    def test_loopback_still_allowed_alongside(self) -> None:
        assert self._validate("http://127.0.0.1:33418/callback")


# ---------------------------------------------------------------------------
# 027 / M10: JWKS refetch throttle
# ---------------------------------------------------------------------------


def _reset_jwks() -> None:
    import pktx.auth as auth_module

    auth_module._JWKS_CACHE = {}
    auth_module._JWKS_FETCHED_AT = 0.0
    auth_module._JWKS_LAST_ATTEMPT = float("-inf")


class _FakeJwksResponse:
    def __init__(self, keys: list[dict[str, Any]]) -> None:
        self._keys = keys

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {"keys": self._keys}


class TestJwksRefetchThrottle:
    """An unknown-kid storm costs at most one JWKS fetch per 60s window."""

    def setup_method(self) -> None:
        _reset_jwks()

    def teardown_method(self) -> None:
        _reset_jwks()

    def _fetch_mock(self) -> Any:
        from unittest.mock import MagicMock

        return MagicMock(return_value=_FakeJwksResponse([{"kid": "real", "n": "x"}]))

    def test_unknown_kid_storm_fetches_once(self) -> None:
        import pktx.auth as auth_module

        get = self._fetch_mock()
        with (
            patch.dict("os.environ", {"CLERK_JWKS_URL": "https://clerk.test/jwks"}),
            patch("pktx.auth.httpx.get", get),
        ):
            for i in range(50):
                with pytest.raises(HTTPException) as exc_info:
                    auth_module._get_jwks_key(f"forged-{i}")
                assert exc_info.value.status_code == 401
                assert exc_info.value.detail == "Invalid token"
            # The real kid is still served from the one fetch's cache.
            assert auth_module._get_jwks_key("real")["kid"] == "real"

        assert get.call_count == 1

    def test_concurrent_storm_fetches_once(self) -> None:
        import threading

        import pktx.auth as auth_module

        get = self._fetch_mock()
        errors: list[int] = []

        def _hit(i: int) -> None:
            try:
                auth_module._get_jwks_key(f"forged-{i}")
            except HTTPException as exc:
                errors.append(exc.status_code)

        with (
            patch.dict("os.environ", {"CLERK_JWKS_URL": "https://clerk.test/jwks"}),
            patch("pktx.auth.httpx.get", get),
        ):
            threads = [threading.Thread(target=_hit, args=(i,)) for i in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert get.call_count == 1
        assert errors == [401] * 20

    def test_refetch_allowed_after_window(self) -> None:
        import pktx.auth as auth_module

        get = self._fetch_mock()
        with (
            patch.dict("os.environ", {"CLERK_JWKS_URL": "https://clerk.test/jwks"}),
            patch("pktx.auth.httpx.get", get),
        ):
            with pytest.raises(HTTPException):
                auth_module._get_jwks_key("rotated")
            auth_module._JWKS_LAST_ATTEMPT -= 61.0
            with pytest.raises(HTTPException):
                auth_module._get_jwks_key("rotated")

        assert get.call_count == 2

    def test_fetch_failure_is_401_not_500(self) -> None:
        import pktx.auth as auth_module

        with (
            patch.dict("os.environ", {"CLERK_JWKS_URL": "https://clerk.test/jwks"}),
            patch("pktx.auth.httpx.get", side_effect=RuntimeError("boom")),
        ):
            with pytest.raises(HTTPException) as exc_info:
                auth_module._get_jwks_key("any")
        assert exc_info.value.status_code == 401
        assert "boom" not in exc_info.value.detail


# ---------------------------------------------------------------------------
# 027 / M12 + M14: azp check, generic 401 details
# ---------------------------------------------------------------------------


class TestAzpAndGenericDetails:
    def setup_method(self) -> None:
        import pktx.auth as auth_module

        _reset_jwks()
        self.private_key, public_key = _gen_rsa_key_pair()
        auth_module._JWKS_CACHE = {"test-kid": _public_key_to_jwk(public_key)}
        auth_module._JWKS_FETCHED_AT = time.monotonic()

    def teardown_method(self) -> None:
        _reset_jwks()

    def _verify(self, token: str, parties: Any = None) -> dict[str, Any]:
        from pktx.auth import verify_clerk_jwt

        with patch.dict("os.environ", {"CLERK_ISSUER": "https://clerk.test"}):
            return verify_clerk_jwt(token, parties)

    def _token(self, azp: str | None) -> str:
        from tests.helpers import make_token

        return make_token(self.private_key, kid="test-kid", azp=azp)

    def test_matching_azp_accepted(self) -> None:
        assert self._verify(self._token("http://testserver"))["sub"] == "user_alice"

    def test_azp_trailing_slash_accepted(self) -> None:
        assert self._verify(self._token("http://testserver/"))["sub"] == "user_alice"

    def test_azp_mismatch_rejected(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            self._verify(self._token("https://evil.example"))
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid token"

    def test_azp_missing_rejected(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            self._verify(self._token(None))
        assert exc_info.value.status_code == 401

    def test_explicit_parties_override_env(self) -> None:
        token = self._token("https://app.example")
        assert self._verify(token, frozenset({"https://app.example"}))
        with pytest.raises(HTTPException):
            self._verify(token)  # env says http://testserver only

    def test_malformed_token_detail_is_generic(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            self._verify("not.a.jwt")
        assert exc_info.value.detail == "Invalid token"

    def test_bad_signature_detail_does_not_echo_exception(self) -> None:
        from tests.helpers import make_token

        other_key, _ = _gen_rsa_key_pair()
        token = make_token(other_key, kid="test-kid")
        with pytest.raises(HTTPException) as exc_info:
            self._verify(token)
        assert exc_info.value.detail == "Invalid token"

    def test_wrong_issuer_detail_is_generic(self) -> None:
        from tests.helpers import make_token

        token = make_token(self.private_key, kid="test-kid", issuer="https://evil")
        with pytest.raises(HTTPException) as exc_info:
            self._verify(token)
        assert exc_info.value.detail == "Invalid token"

    def test_build_dependency_fails_closed_without_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from unittest.mock import MagicMock

        from pktx.auth import build_get_current_user

        monkeypatch.delenv("CLERK_AUTHORIZED_PARTIES", raising=False)
        monkeypatch.delenv("PKTX_PUBLIC_URL", raising=False)
        with pytest.raises(ValueError):
            build_get_current_user(MagicMock())


# ---------------------------------------------------------------------------
# 027 / M13: MCP tool middleware upserts once per sub, off the event loop
# ---------------------------------------------------------------------------


class TestUserContextToolMiddleware:
    async def test_upsert_once_per_sub_off_event_loop(self) -> None:
        import threading
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        from pktx.auth import UserContextToolMiddleware, current_user_id_var

        conn = MagicMock()
        calls: list[tuple[str, str]] = []
        main_thread = threading.current_thread()

        def _fake_upsert(c: Any, sub: str, email: Any, name: Any) -> None:
            assert threading.current_thread() is not main_thread
            calls.append((sub, threading.current_thread().name))

        mw: Any = UserContextToolMiddleware(conn)
        seen: list[str | None] = []

        async def _call_next(ctx: Any) -> str:
            seen.append(current_user_id_var.get())
            return "ok"

        for sub in ("user_a", "user_a", "user_b", "user_a", "user_b"):
            tok = SimpleNamespace(claims={"sub": sub})
            with (
                patch("pktx.auth.get_access_token", return_value=tok),
                patch("pktx.auth.upsert_user", side_effect=_fake_upsert),
            ):
                assert await mw.on_call_tool(MagicMock(), _call_next) == "ok"

        assert [c[0] for c in calls] == ["user_a", "user_b"]
        assert seen == ["user_a", "user_a", "user_b", "user_a", "user_b"]
        assert conn.commit.call_count == 2
        assert current_user_id_var.get() is None

    async def test_failed_upsert_is_retried_next_call(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        from pktx.auth import UserContextToolMiddleware

        conn = MagicMock()
        mw: Any = UserContextToolMiddleware(conn)
        upsert = MagicMock(side_effect=[RuntimeError("db down"), None])

        async def _call_next(ctx: Any) -> str:
            return "ok"

        tok = SimpleNamespace(claims={"sub": "user_a"})
        with (
            patch("pktx.auth.get_access_token", return_value=tok),
            patch("pktx.auth.upsert_user", upsert),
        ):
            await mw.on_call_tool(MagicMock(), _call_next)
            await mw.on_call_tool(MagicMock(), _call_next)
            await mw.on_call_tool(MagicMock(), _call_next)

        assert upsert.call_count == 2
        conn.rollback.assert_called_once()
