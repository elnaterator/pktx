"""Integration tests for two-user data isolation.

Verifies that Alice and Bob each see only their own data and that
cross-user detail access returns 404. Also tests account deletion cascade.
"""

import time
from typing import Any
from unittest.mock import patch

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
# RSA / JWT helpers (same pattern as test_auth_contract.py)
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
        {"sub": sub, "iss": issuer, "iat": now, "exp": now + 3600, "email": email},
        pem,
        algorithm="RS256",
        headers={"kid": kid},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def multi_user_db(db_conn: Connection[Any]) -> Connection[Any]:
    """PostgreSQL connection with both users seeded (rolled back after test)."""
    db_conn.execute(
        "INSERT INTO users (id, email) VALUES ('user_alice', 'alice@test.com')"
    )
    db_conn.execute("INSERT INTO users (id, email) VALUES ('user_bob', 'bob@test.com')")
    return db_conn


@pytest.fixture
def two_user_setup(multi_user_db: Connection[Any]) -> dict[str, Any]:  # type: ignore[return]
    """Build a shared TestClient plus tokens for Alice and Bob."""
    import pktx.auth as auth_module

    private_key, public_key = _gen_rsa_key_pair()
    jwk_entry = _public_key_to_jwk(public_key, kid="ck1")
    auth_module._JWKS_CACHE = {"ck1": jwk_entry}
    auth_module._JWKS_FETCHED_AT = time.monotonic()

    app = FastAPI()
    get_user = build_get_current_user(multi_user_db)  # type: ignore[arg-type]
    app.include_router(
        create_router(
            ResumeService(multi_user_db),  # type: ignore[arg-type]
            app_service=ApplicationService(multi_user_db),  # type: ignore[arg-type]
            acc_service=AccomplishmentService(multi_user_db),  # type: ignore[arg-type]
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
        "db": multi_user_db,
        "private_key": private_key,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMultiUserDataIsolation:
    """Alice and Bob each create data; each sees only their own in list calls."""

    @pytest.fixture(autouse=True)
    def _setup(self, two_user_setup: dict[str, Any]) -> None:
        self.client = two_user_setup["client"]
        self.alice_token = two_user_setup["alice_token"]
        self.bob_token = two_user_setup["bob_token"]

    def _post(self, url: str, token: str, body: dict[str, Any]) -> Any:
        with patch.dict("os.environ", {"CLERK_ISSUER": "https://clerk.test"}):
            return self.client.post(url, json=body, headers=_auth(token))

    def _get(self, url: str, token: str) -> Any:
        with patch.dict("os.environ", {"CLERK_ISSUER": "https://clerk.test"}):
            return self.client.get(url, headers=_auth(token))

    # --- Resume isolation ---

    def test_alice_creates_resume_bob_list_is_empty(self) -> None:
        resp = self._post("/api/resumes", self.alice_token, {"label": "Alice CV"})
        assert resp.status_code == 201

        resp = self._get("/api/resumes", self.bob_token)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_alice_list_contains_only_her_resume(self) -> None:
        self._post("/api/resumes", self.alice_token, {"label": "Alice CV"})

        resp = self._get("/api/resumes", self.alice_token)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["label"] == "Alice CV"

    # --- Application isolation ---

    def test_alice_creates_application_bob_list_is_empty(self) -> None:
        resp = self._post(
            "/api/applications",
            self.alice_token,
            {"company": "Acme", "position": "Engineer"},
        )
        assert resp.status_code == 201

        resp = self._get("/api/applications", self.bob_token)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_alice_list_contains_only_her_application(self) -> None:
        self._post(
            "/api/applications",
            self.alice_token,
            {"company": "Acme", "position": "Engineer"},
        )

        resp = self._get("/api/applications", self.alice_token)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["company"] == "Acme"

    # --- Accomplishment isolation ---

    def test_alice_creates_accomplishment_bob_list_is_empty(self) -> None:
        resp = self._post(
            "/api/accomplishments",
            self.alice_token,
            {"title": "Alice's win"},
        )
        assert resp.status_code == 201

        resp = self._get("/api/accomplishments", self.bob_token)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_alice_list_contains_only_her_accomplishment(self) -> None:
        self._post(
            "/api/accomplishments",
            self.alice_token,
            {"title": "Alice's win"},
        )

        resp = self._get("/api/accomplishments", self.alice_token)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["title"] == "Alice's win"


class TestCrossUserDetailAccess:
    """Bob attempting detail access to Alice's resources receives 404."""

    @pytest.fixture(autouse=True)
    def _create_alice_data(self, two_user_setup: dict[str, Any]) -> None:
        self.client = two_user_setup["client"]
        self.alice_token = two_user_setup["alice_token"]
        self.bob_token = two_user_setup["bob_token"]

        with patch.dict("os.environ", {"CLERK_ISSUER": "https://clerk.test"}):
            # Alice creates one of each resource type.
            resp = self.client.post(
                "/api/resumes",
                json={"label": "Alice CV"},
                headers=_auth(self.alice_token),
            )
            assert resp.status_code == 201
            self.alice_resume_id = resp.json()["id"]

            resp = self.client.post(
                "/api/applications",
                json={"company": "Acme", "position": "Engineer"},
                headers=_auth(self.alice_token),
            )
            assert resp.status_code == 201
            self.alice_app_id = resp.json()["id"]

            resp = self.client.post(
                "/api/accomplishments",
                json={"title": "Alice's win"},
                headers=_auth(self.alice_token),
            )
            assert resp.status_code == 201
            self.alice_acc_id = resp.json()["id"]

    def _get(self, url: str, token: str) -> Any:
        with patch.dict("os.environ", {"CLERK_ISSUER": "https://clerk.test"}):
            return self.client.get(url, headers=_auth(token))

    def test_bob_cannot_get_alice_resume(self) -> None:
        resp = self._get(f"/api/resumes/{self.alice_resume_id}", self.bob_token)
        assert resp.status_code == 404

    def test_bob_cannot_get_alice_application(self) -> None:
        resp = self._get(f"/api/applications/{self.alice_app_id}", self.bob_token)
        assert resp.status_code == 404

    def test_bob_cannot_get_alice_accomplishment(self) -> None:
        resp = self._get(f"/api/accomplishments/{self.alice_acc_id}", self.bob_token)
        assert resp.status_code == 404

    def test_alice_can_get_her_own_resume(self) -> None:
        resp = self._get(f"/api/resumes/{self.alice_resume_id}", self.alice_token)
        assert resp.status_code == 200

    def test_alice_can_get_her_own_application(self) -> None:
        resp = self._get(f"/api/applications/{self.alice_app_id}", self.alice_token)
        assert resp.status_code == 200

    def test_alice_can_get_her_own_accomplishment(self) -> None:
        resp = self._get(f"/api/accomplishments/{self.alice_acc_id}", self.alice_token)
        assert resp.status_code == 200


class TestUserDeletionCascade:
    """Deleting Alice's user row cascades to remove all her owned data."""

    def test_deleting_alice_removes_her_resume(
        self, two_user_setup: dict[str, Any]
    ) -> None:
        client = two_user_setup["client"]
        alice_token = two_user_setup["alice_token"]
        db = two_user_setup["db"]

        with patch.dict("os.environ", {"CLERK_ISSUER": "https://clerk.test"}):
            resp = client.post(
                "/api/resumes",
                json={"label": "Alice CV"},
                headers=_auth(alice_token),
            )
            assert resp.status_code == 201
            alice_resume_id = resp.json()["id"]

        # Directly delete Alice's user row (simulates webhook cascade).
        from pktx.database import delete_user

        delete_user(db, "user_alice")

        # The resume row must be gone.
        row = db.execute(
            "SELECT id FROM resume_version WHERE id = %s", (alice_resume_id,)
        ).fetchone()
        assert row is None

    def test_deleting_alice_removes_her_application(
        self, two_user_setup: dict[str, Any]
    ) -> None:
        client = two_user_setup["client"]
        alice_token = two_user_setup["alice_token"]
        db = two_user_setup["db"]

        with patch.dict("os.environ", {"CLERK_ISSUER": "https://clerk.test"}):
            resp = client.post(
                "/api/applications",
                json={"company": "Acme", "position": "Engineer"},
                headers=_auth(alice_token),
            )
            assert resp.status_code == 201
            alice_app_id = resp.json()["id"]

        from pktx.database import delete_user

        delete_user(db, "user_alice")

        row = db.execute(
            "SELECT id FROM application WHERE id = %s", (alice_app_id,)
        ).fetchone()
        assert row is None

    def test_deleting_alice_removes_her_accomplishment(
        self, two_user_setup: dict[str, Any]
    ) -> None:
        client = two_user_setup["client"]
        alice_token = two_user_setup["alice_token"]
        db = two_user_setup["db"]

        with patch.dict("os.environ", {"CLERK_ISSUER": "https://clerk.test"}):
            resp = client.post(
                "/api/accomplishments",
                json={"title": "Alice's win"},
                headers=_auth(alice_token),
            )
            assert resp.status_code == 201
            alice_acc_id = resp.json()["id"]

        from pktx.database import delete_user

        delete_user(db, "user_alice")

        row = db.execute(
            "SELECT id FROM accomplishment WHERE id = %s", (alice_acc_id,)
        ).fetchone()
        assert row is None

    def test_deleting_alice_does_not_affect_bob_data(
        self, two_user_setup: dict[str, Any]
    ) -> None:
        client = two_user_setup["client"]
        alice_token = two_user_setup["alice_token"]
        bob_token = two_user_setup["bob_token"]
        db = two_user_setup["db"]

        with patch.dict("os.environ", {"CLERK_ISSUER": "https://clerk.test"}):
            # Both users create a resume.
            client.post(
                "/api/resumes",
                json={"label": "Alice CV"},
                headers=_auth(alice_token),
            )
            resp = client.post(
                "/api/resumes",
                json={"label": "Bob CV"},
                headers=_auth(bob_token),
            )
            assert resp.status_code == 201
            bob_resume_id = resp.json()["id"]

        from pktx.database import delete_user

        delete_user(db, "user_alice")

        # Bob's resume must still exist.
        row = db.execute(
            "SELECT id FROM resume_version WHERE id = %s", (bob_resume_id,)
        ).fetchone()
        assert row is not None
