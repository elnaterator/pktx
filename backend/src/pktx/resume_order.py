"""Fixed resume section order and which optional sections a version shows.

Kept free of model imports so ``models.Resume`` can normalize on construction.
``resume_sections`` asserts its registry matches ``LIST_ORDER``.
"""

from typing import Any

# Every list section, in the one order they are shown.
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
# Always shown. The rest are optional: the user adds them from a fixed list.
CORE: tuple[str, ...] = ("experience", "education", "skills")
OPTIONAL: tuple[str, ...] = tuple(k for k in LIST_ORDER if k not in CORE)


def normalize_enabled(enabled: list[str], data: dict[str, Any]) -> list[str]:
    """Optional sections to show, in fixed order.

    A section is shown when it was added or already has entries, so adding an
    entry (e.g. through MCP) never leaves content hidden. Unknown keys drop out.
    """
    return [k for k in OPTIONAL if k in enabled or data.get(k)]
