"""Per-version resume layout: section order, visibility and title overrides.

Kept free of model imports so ``models.Resume`` can normalize its layout on
construction. ``resume_sections`` asserts its registry matches ``LIST_ORDER``.
"""

from typing import Any

CUSTOM_PREFIX = "custom:"

# Sections shown on the resume, in default order. ``contact`` is the header and
# is always first, so it is not part of the layout.
LIST_ORDER: tuple[str, ...] = (
    "experience",
    "education",
    "skills",
    "projects",
    "certifications",
    "awards",
    "publications",
    "volunteer",
    "languages",
)
# Sections that existed before the layout was introduced: visible by default.
LEGACY_VISIBLE = {"summary", "experience", "education", "skills"}


def custom_key(custom_id: str) -> str:
    return f"{CUSTOM_PREFIX}{custom_id}"


def normalize_layout(layout: list[dict[str, Any]], data: dict[str, Any]) -> list[dict]:
    """Return ``layout`` cleaned against ``data``.

    Unknown or duplicate sections are dropped; sections missing from the layout
    are appended in default order. A missing section is visible when it is a
    pre-layout section or already has content, so existing resumes look the same
    and new, empty sections stay out of the way until used.
    """
    customs = data.get("custom_sections") or {}
    valid = {"summary", *LIST_ORDER, *(custom_key(c) for c in customs)}
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in layout:
        key = item.get("section")
        if key in valid and key not in seen:
            seen.add(key)
            result.append(
                {
                    "section": key,
                    "visible": bool(item.get("visible", True)),
                    "title": item.get("title") or None,
                }
            )

    def has_content(key: str) -> bool:
        if key == "summary":
            return bool(data.get("summary"))
        if key.startswith(CUSTOM_PREFIX):
            return bool(customs.get(key[len(CUSTOM_PREFIX) :], {}).get("entries"))
        return bool(data.get(key))

    default_order = ["summary", *LIST_ORDER, *(custom_key(c) for c in customs)]
    for key in default_order:
        if key not in seen:
            result.append(
                {
                    "section": key,
                    "visible": key in LEGACY_VISIBLE or has_content(key),
                    "title": None,
                }
            )
    return result
