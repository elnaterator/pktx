"""Shared input validation for service-layer writes (027).

Every create/update path in the services funnels user-supplied tags, URLs and
free text through these helpers, so REST and MCP enforce identical rules.
Each helper raises ``ValueError`` on bad input; routes map that to 422 and
MCP tools surface it as a tool error.
"""

from typing import Any
from urllib.parse import urlparse

MAX_TAG_LEN = 50
MAX_TAGS = 50

# Length limits (characters).
MAX_NAME = 200  # labels, titles, names, company, position
MAX_URL = 2048
MAX_SHORT = 500  # email, phone, location, subject, relationship, contact title
MAX_LONG = 100_000  # note content, notes, description, STAR fields, bodies

_HTTP_SCHEMES = ("http", "https")


def normalize_tags(value: Any) -> list[str]:
    """Return a clean tag list: trimmed, lowercased, non-empty, de-duplicated.

    ``None`` means "no tags". Anything other than a list of strings is
    rejected rather than coerced (a bare string would otherwise be split into
    characters).
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Tags must be a list of strings")
    seen: set[str] = set()
    result: list[str] = []
    for tag in value:
        if not isinstance(tag, str):
            raise ValueError("Tags must be a list of strings")
        normalized = tag.strip().lower()
        if not normalized or normalized in seen:
            continue
        if len(normalized) > MAX_TAG_LEN:
            raise ValueError(
                f"Tag must not exceed {MAX_TAG_LEN} characters: '{normalized[:60]}'"
            )
        seen.add(normalized)
        result.append(normalized)
    if len(result) > MAX_TAGS:
        raise ValueError(f"At most {MAX_TAGS} tags are allowed")
    return result


def validate_http_url(value: Any, field: str = "URL") -> str | None:
    """Return the URL if it is an absolute http(s) URL; empty → ``None``.

    Blocks ``javascript:``, ``data:`` and every other non-web scheme so stored
    values are always safe to render as a link.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    url = value.strip()
    if not url:
        return None
    if len(url) > MAX_URL:
        raise ValueError(f"{field} must not exceed {MAX_URL} characters")
    normalized = _with_default_scheme(url)
    if normalized is None:
        raise ValueError(f"{field} must be an http:// or https:// URL")
    return normalized


def _with_default_scheme(url: str) -> str | None:
    """Return ``url`` as an absolute http(s) URL, or ``None`` if it is not one.

    A bare host like ``linkedin.com/in/jane`` (common from MCP clients) gets
    ``https://`` prepended rather than being rejected. The prefixed form must
    still parse to a dotted hostname with no userinfo and a valid port, which
    is what keeps ``javascript:alert(1)`` → ``https://javascript:alert(1)``
    (host ``javascript``, bad port) and ``mailto:a@b.c`` (userinfo) out.
    """
    if "://" not in url and not url.startswith("//"):
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme.lower() not in _HTTP_SCHEMES or not parsed.hostname:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    try:
        parsed.port  # noqa: B018 — raises ValueError on a malformed port
    except ValueError:
        return None
    if "." not in parsed.hostname and parsed.hostname != "localhost":
        return None
    return url


def check_len(field: str, value: Any, max_len: int) -> None:
    """Raise ``ValueError`` if a string ``value`` is longer than ``max_len``.

    Non-string values pass through untouched; ``None`` is always allowed.
    """
    if isinstance(value, str) and len(value) > max_len:
        raise ValueError(f"{field} must not exceed {max_len} characters")


def check_lengths(data: dict[str, Any], limits: dict[str, int]) -> None:
    """Apply ``check_len`` to every field in ``limits`` that ``data`` contains."""
    for field, max_len in limits.items():
        if field in data:
            check_len(field, data[field], max_len)
