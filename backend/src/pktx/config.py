"""Configuration for pktx MCP server — database, server, and logging."""

import logging
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_PORT = 8000

logger = logging.getLogger("pktx")


def resolve_port() -> int:
    """Resolve the HTTP server port from PKTX_PORT env var (default 8000)."""
    raw = os.environ.get("PKTX_PORT", str(DEFAULT_PORT))
    return int(raw)


def resolve_cors_origins() -> list[str]:
    """Resolve CORS allowed origins from PKTX_CORS_ORIGINS env var.

    Comma-separated list. Empty/unset = no CORS origins allowed.
    """
    raw = os.environ.get("PKTX_CORS_ORIGINS", "")
    if not raw.strip():
        return []
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def resolve_frontend_dir() -> Path | None:
    """Resolve the frontend build directory path.

    Uses PKTX_FRONTEND_DIR env var if set, otherwise tries to find
    frontend/dist relative to the repository root.

    Returns None if the directory doesn't exist (backend runs without frontend).
    """
    raw = os.environ.get("PKTX_FRONTEND_DIR")

    if raw:
        # Use explicit env var if provided
        path = Path(raw).expanduser().resolve()
    else:
        # Try to find frontend/dist relative to repo root
        # The backend package is at <repo>/backend/src/pktx/
        # So we go up 3 levels to get to repo root, then to frontend/dist
        try:
            repo_root = Path(__file__).parent.parent.parent.parent
            path = repo_root / "frontend" / "dist"
        except Exception:
            logger.warning("Could not determine repository root for frontend directory")
            return None

    if not path.exists():
        logger.warning(
            "Frontend directory not found: %s (backend will run without frontend)",
            path,
        )
        return None

    if not path.is_dir():
        logger.warning("Frontend path is not a directory: %s", path)
        return None

    logger.info("Frontend directory resolved to: %s", path)
    return path


def resolve_public_url() -> str:
    """Resolve PKTX_PUBLIC_URL env var. Raises on missing."""
    value = os.environ.get("PKTX_PUBLIC_URL", "")
    if not value.strip():
        raise ValueError("PKTX_PUBLIC_URL environment variable is required")
    return value.strip().rstrip("/")


def resolve_public_url_optional() -> str | None:
    """PKTX_PUBLIC_URL if set (no trailing slash), else None — for cosmetic uses."""
    value = os.environ.get("PKTX_PUBLIC_URL", "").strip().rstrip("/")
    return value or None


def resolve_extra_client_redirect_uris() -> list[str]:
    """Resolve extra client redirect-URI patterns from PKTX_EXTRA_CLIENT_REDIRECT_URIS.

    Comma-separated list of patterns (wildcards allowed, e.g.
    ``https://claude.ai/api/mcp/auth_callback``). Loopback patterns are always
    allowed on top of these; this env var exists for hosted MCP clients, which
    identify themselves with a Client ID Metadata Document and redirect to their
    own HTTPS callback instead of a local port. Empty/unset = loopback only.
    """
    raw = os.environ.get("PKTX_EXTRA_CLIENT_REDIRECT_URIS", "")
    if not raw.strip():
        return []
    return [pattern.strip() for pattern in raw.split(",") if pattern.strip()]


def resolve_authorized_parties() -> list[str]:
    """Resolve the allowed ``azp`` values for REST session JWTs.

    ``CLERK_AUTHORIZED_PARTIES`` is a comma-separated list of origins (trimmed,
    trailing ``/`` stripped). When unset, defaults to the origin of
    ``PKTX_PUBLIC_URL``. Raises ``ValueError`` when neither is set, so a
    production deploy fails closed instead of accepting any ``azp``.
    """
    raw = os.environ.get("CLERK_AUTHORIZED_PARTIES", "")
    parties = [p.strip().rstrip("/") for p in raw.split(",") if p.strip()]
    if parties:
        return parties
    public = os.environ.get("PKTX_PUBLIC_URL", "").strip()
    if public:
        parsed = urlparse(public)
        if parsed.scheme and parsed.netloc:
            return [f"{parsed.scheme}://{parsed.netloc}"]
    raise ValueError(
        "CLERK_AUTHORIZED_PARTIES (or PKTX_PUBLIC_URL to derive it) must be set"
    )


def resolve_clerk_jwks_url() -> str:
    """Resolve CLERK_JWKS_URL env var. Raises on missing."""
    value = os.environ.get("CLERK_JWKS_URL", "")
    if not value.strip():
        raise ValueError("CLERK_JWKS_URL environment variable is required")
    return value.strip()


def resolve_clerk_issuer() -> str:
    """Resolve CLERK_ISSUER env var. Raises on missing."""
    value = os.environ.get("CLERK_ISSUER", "")
    if not value.strip():
        raise ValueError("CLERK_ISSUER environment variable is required")
    return value.strip()


def resolve_clerk_oauth_client_id() -> str:
    """Resolve CLERK_OAUTH_CLIENT_ID env var. Raises on missing.

    Client id of the static Clerk OAuth application the MCP proxy uses upstream.
    """
    value = os.environ.get("CLERK_OAUTH_CLIENT_ID", "")
    if not value.strip():
        raise ValueError("CLERK_OAUTH_CLIENT_ID environment variable is required")
    return value.strip()


def resolve_clerk_oauth_client_secret() -> str:
    """Resolve CLERK_OAUTH_CLIENT_SECRET env var. Raises on missing.

    Secret of the static Clerk OAuth application the MCP proxy uses upstream.
    """
    value = os.environ.get("CLERK_OAUTH_CLIENT_SECRET", "")
    if not value.strip():
        raise ValueError("CLERK_OAUTH_CLIENT_SECRET environment variable is required")
    return value.strip()


def resolve_clerk_secret_key() -> str:
    """Resolve CLERK_SECRET_KEY env var. Raises on missing."""
    value = os.environ.get("CLERK_SECRET_KEY", "")
    if not value.strip():
        raise RuntimeError(
            "CLERK_SECRET_KEY environment variable is required for MCP dual-auth "
            "(session JWTs + API keys). Set it to your Clerk secret key "
            "(starts with sk_test_ or sk_live_)."
        )
    return value.strip()


def resolve_clerk_webhook_secret() -> str:
    """Resolve CLERK_WEBHOOK_SECRET env var. Raises on missing."""
    value = os.environ.get("CLERK_WEBHOOK_SECRET", "")
    if not value.strip():
        raise ValueError("CLERK_WEBHOOK_SECRET environment variable is required")
    return value.strip()


def resolve_db_url() -> str:
    """Resolve PKTX_DB_URL env var (required for PostgreSQL).

    Raises ValueError if not set.
    """
    value = os.environ.get("PKTX_DB_URL", "")
    if not value.strip():
        raise ValueError("PKTX_DB_URL environment variable is required")
    return value.strip()


def resolve_pool_min() -> int:
    """Resolve PKTX_DB_POOL_MIN env var (default 1)."""
    return int(os.environ.get("PKTX_DB_POOL_MIN", "1"))


MAX_REQUEST_BODY_BYTES = 1_048_576  # 1 MB


def resolve_pool_max() -> int:
    """Resolve PKTX_DB_POOL_MAX env var (default 10)."""
    return int(os.environ.get("PKTX_DB_POOL_MAX", "10"))


def configure_logging() -> logging.Logger:
    """Configure logging to stderr with level from LOG_LEVEL env var."""
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    root_logger = logging.getLogger("pktx")
    root_logger.setLevel(level)
    # Avoid duplicate handlers on repeated calls
    if not root_logger.handlers:
        root_logger.addHandler(handler)

    return root_logger
