"""Shared test helpers: JWT minting, full-app builder, per-user test client."""

import time
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Header, HTTPException
from jose import jwt
from starlette.testclient import TestClient

from pktx.accomplishment_service import AccomplishmentService
from pktx.api.routes import create_router
from pktx.application_service import ApplicationService
from pktx.auth import UserContext
from pktx.communication_service import ContactCommunicationService
from pktx.contact_service import ContactService
from pktx.link_service import LinkService
from pktx.note_service import NoteService
from pktx.resume_service import ResumeService

TEST_ISSUER = "https://clerk.test"
TEST_AZP = "http://testserver"


def gen_rsa_key_pair() -> tuple[Any, Any]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def public_key_to_jwk(public_key: Any, kid: str = "ck1") -> dict[str, Any]:
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


def make_token(
    private_key: Any,
    kid: str = "ck1",
    sub: str = "user_alice",
    issuer: str = TEST_ISSUER,
    email: str = "alice@example.com",
    azp: str | None = TEST_AZP,
) -> str:
    """Mint an RS256 Clerk-style session JWT. ``azp=None`` omits the claim."""
    now = int(time.time())
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    claims: dict[str, Any] = {
        "sub": sub,
        "iss": issuer,
        "iat": now,
        "exp": now + 3600,
        "email": email,
    }
    if azp is not None:
        claims["azp"] = azp
    return jwt.encode(claims, pem, algorithm="RS256", headers={"kid": kid})


def header_user_dep(x_test_user: str | None = Header(default=None)) -> UserContext:
    """Test-only auth dependency: the caller is whoever ``X-Test-User`` names."""
    if not x_test_user:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    return UserContext(id=x_test_user, email=None, display_name=None)


def build_full_app(conn: Any, get_current_user: Any = header_user_dep) -> FastAPI:
    """App with every resource router wired to ``conn``."""
    app = FastAPI()
    app.include_router(
        create_router(
            ResumeService(conn),
            app_service=ApplicationService(conn),
            acc_service=AccomplishmentService(conn),
            note_service=NoteService(conn),
            contact_service=ContactService(conn),
            comm_service=ContactCommunicationService(conn),
            link_service=LinkService(conn),
            get_current_user=get_current_user,
        )
    )
    return app


def user_client(app: FastAPI, user_id: str) -> TestClient:
    """TestClient that acts as ``user_id`` via the ``X-Test-User`` header."""
    return TestClient(
        app, raise_server_exceptions=False, headers={"X-Test-User": user_id}
    )
