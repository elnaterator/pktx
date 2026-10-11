"""Well-known contact keys offered in the UI, most common first.

Contact details are key/value pairs. These presets get validation by kind;
any other key is a custom key with free-text value. Pure data (no model
imports) so ``models`` and ``resume_sections`` can both use it.
"""

import re
from dataclasses import dataclass
from typing import Literal

Kind = Literal["email", "url", "text"]


@dataclass(frozen=True)
class ContactKey:
    key: str
    kind: Kind


CONTACT_KEYS: tuple[ContactKey, ...] = (
    ContactKey("Email", "email"),
    ContactKey("Website", "url"),
    ContactKey("LinkedIn", "url"),
    ContactKey("GitHub", "url"),
    ContactKey("GitLab", "url"),
    ContactKey("Portfolio", "url"),
    ContactKey("X", "url"),
    ContactKey("Bluesky", "url"),
    ContactKey("Mastodon", "url"),
    ContactKey("Stack Overflow", "url"),
    ContactKey("Medium", "url"),
    ContactKey("YouTube", "url"),
    ContactKey("Dribbble", "url"),
    ContactKey("Behance", "url"),
    ContactKey("ORCID", "url"),
    ContactKey("Google Scholar", "url"),
)


def _fold(key: str) -> str:
    return re.sub(r"\s+", "", key).lower()


_BY_FOLDED = {_fold(c.key): c for c in CONTACT_KEYS}


def canonical_key(raw: str) -> str:
    """Trim/collapse spaces; map a preset spelled differently ("linked in") to it."""
    cleaned = re.sub(r"\s+", " ", raw).strip()
    preset = _BY_FOLDED.get(_fold(cleaned))
    return preset.key if preset else cleaned


def key_kind(key: str) -> Kind:
    preset = _BY_FOLDED.get(_fold(key))
    return preset.kind if preset else "text"
