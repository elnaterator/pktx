"""ResumeService — shared business logic for resume version CRUD operations."""

import json
import uuid
from typing import Any

from pktx.database import (
    create_resume_version,
    delete_resume_version,
    link_counts_by_type,
    load_default_resume_version,
    load_resume_version,
    load_resume_version_tags,
    load_resume_versions,
    set_default_resume_version,
    unlink_all_for,
    update_resume_version_data,
    update_resume_version_metadata,
)
from pktx.db import DBConnection
from pktx.link_service import LinkService
from pktx.models import ContactInfo, CustomSection
from pktx.resume_layout import CUSTOM_PREFIX, custom_key, normalize_layout
from pktx.resume_sections import (
    ALL_SECTIONS,
    LIST_SECTIONS,
    SECTION_UPDATE,
    is_custom,
    section_def,
)
from pktx.validation import (
    MAX_LONG,
    MAX_NAME,
    MAX_SHORT,
    check_len,
    check_lengths,
    normalize_tags,
)

_CONTACT_LIMITS = {
    "name": MAX_NAME,
    "email": MAX_SHORT,
    "phone": MAX_SHORT,
    "location": MAX_SHORT,
}
# Entry fields that are names/titles get the tighter limit; every other
# scalar string gets MAX_SHORT; each highlight bullet gets _MAX_HIGHLIGHT.
_ENTRY_NAME_FIELDS = {
    "title",
    "company",
    "institution",
    "degree",
    "name",
    "category",
    "issuer",
    "venue",
    "role",
    "organization",
    "language",
    "proficiency",
    "heading",
    "label",
}
# Free-text bodies get the long limit.
_ENTRY_LONG_FIELDS = {"description", "body"}
_MAX_HIGHLIGHT = 2000


def _check_entry_lengths(entry: dict[str, Any]) -> None:
    for key, value in entry.items():
        if isinstance(value, str):
            if key in _ENTRY_LONG_FIELDS:
                limit = MAX_LONG
            elif key in _ENTRY_NAME_FIELDS:
                limit = MAX_NAME
            else:
                limit = MAX_SHORT
            check_len(key, value, limit)
        elif isinstance(value, list):
            for item in value:
                check_len(key, item, _MAX_HIGHLIGHT)


def _clean_label(label: Any) -> str:
    if not isinstance(label, str) or not label.strip():
        raise ValueError("Label must not be empty")
    label = label.strip()
    check_len("label", label, MAX_NAME)
    return label


def _entries(resume_data: dict[str, Any], section: str) -> list[dict[str, Any]]:
    """The mutable entry list for a built-in or ``custom:<id>`` list section."""
    section_def(section)  # validates the key
    if is_custom(section):
        custom = (resume_data.get("custom_sections") or {}).get(
            section[len(CUSTOM_PREFIX) :]
        )
        if custom is None:
            raise ValueError(f"Unknown custom section: '{section}'")
        return custom.setdefault("entries", [])
    return resume_data.setdefault(section, [])


def _resolve(entries: list[dict[str, Any]], section: str, ref: str | int) -> int:
    """Index of the entry addressed by stable id, or by legacy 0-based index."""
    if isinstance(ref, str):
        for i, e in enumerate(entries):
            if e.get("id") == ref:
                return i
        if not ref.lstrip("-").isdigit():
            raise ValueError(f"No {section} entry with id '{ref}'")
    index = int(ref)
    if index < 0 or index >= len(entries):
        raise ValueError(
            f"{section.title()} index {index} out of range. "
            f"Resume has {len(entries)} {section} entries."
        )
    return index


class ResumeService:
    """Resume version CRUD operations with constructor-injected DB connection."""

    def __init__(self, conn: DBConnection) -> None:
        self._conn = conn
        self._links = LinkService(conn)

    # --- Version management ---

    def list_resumes(
        self,
        user_id: str,
        tags: list[str] | None = None,
        q: str | None = None,
    ) -> list[dict[str, Any]]:
        """List the user's resume versions with metadata."""
        resumes = load_resume_versions(self._conn, user_id=user_id, tags=tags, q=q)
        if resumes:
            ids = [r["id"] for r in resumes]
            counts = self._links.count_links("resume", ids, user_id)
            for r in resumes:
                r["link_count"] = counts.get(r["id"], 0)
            app_counts = link_counts_by_type(
                self._conn, "resume", ids, "application", user_id
            )
            for r in resumes:
                r["app_count"] = app_counts.get(r["id"], 0)
        return resumes

    def get_resume(
        self, version_id: int | None = None, *, user_id: str
    ) -> dict[str, Any]:
        """Get a resume version. If id is None, returns the default."""
        if version_id is None:
            rv = load_default_resume_version(self._conn, user_id=user_id)
        else:
            rv = load_resume_version(self._conn, version_id, user_id=user_id)
        rv["links"] = self._links.list_links("resume", rv["id"], user_id)
        return rv

    def list_tags(self, user_id: str) -> list[str]:
        """Return sorted unique tag list for autocomplete."""
        return load_resume_version_tags(self._conn, user_id=user_id)

    def create_resume(
        self,
        label: str,
        *,
        user_id: str,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new resume version copied from the default.

        If the user has no existing default resume, creates one with empty data.
        """
        label = _clean_label(label)
        normalized_tags = normalize_tags(tags)
        try:
            default = load_default_resume_version(self._conn, user_id=user_id)
            resume_data = default["resume_data"]
        except ValueError:
            resume_data = {}
        return create_resume_version(
            self._conn,
            label,
            resume_data,
            user_id=user_id,
            tags=normalized_tags,
        )

    def set_default(self, version_id: int, *, user_id: str) -> str:
        """Set a resume version as default."""
        label = set_default_resume_version(self._conn, version_id, user_id=user_id)
        return f"Set '{label}' as default resume"

    def delete_resume(self, version_id: int, *, user_id: str) -> str:
        """Delete a resume version and its links atomically.

        Ownership is checked first so nothing is touched for a foreign id.
        """
        load_resume_version(self._conn, version_id, user_id=user_id)
        with self._conn.transaction():
            unlink_all_for(self._conn, "resume", version_id, user_id)
            label = delete_resume_version(self._conn, version_id, user_id=user_id)
        return f"Deleted resume version '{label}'"

    def update_metadata(
        self,
        version_id: int,
        label: str,
        *,
        user_id: str,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update resume version label (and optionally tags)."""
        label = _clean_label(label)
        normalized_tags = normalize_tags(tags) if tags is not None else None
        return update_resume_version_metadata(
            self._conn,
            version_id,
            label,
            user_id=user_id,
            tags=normalized_tags,
        )

    # --- Section operations (version-scoped) ---

    def get_section(
        self, section: str, version_id: int | None = None, *, user_id: str
    ) -> Any:
        """Get a section from a resume version."""
        version = self.get_resume(version_id, user_id=user_id)
        resume_data = version["resume_data"]
        if is_custom(section):
            return _entries(resume_data, section)
        if section not in ALL_SECTIONS:
            raise ValueError(
                f"Invalid section: '{section}'. "
                f"Must be one of: {', '.join(ALL_SECTIONS)}"
            )
        return resume_data.get(section)

    def update_section(
        self,
        section: str,
        data: dict[str, Any],
        version_id: int | None = None,
        *,
        user_id: str,
    ) -> str:
        """Update a singleton section (contact or summary) on a version."""
        if section not in SECTION_UPDATE:
            raise ValueError(
                f"Invalid section for update_section: '{section}'. "
                f"Must be one of: {', '.join(SECTION_UPDATE)}"
            )

        version = self.get_resume(version_id, user_id=user_id)
        vid = version["id"]
        resume_data = version["resume_data"]

        if section == "contact":
            known_fields = set(ContactInfo.model_fields.keys())
            filtered = {k: v for k, v in data.items() if k in known_fields}
            if not filtered:
                raise ValueError("At least one contact field must be provided")
            check_lengths(filtered, _CONTACT_LIMITS)
            for profile in filtered.get("profiles") or []:
                if isinstance(profile, dict):
                    _check_entry_lengths(
                        {k: v for k, v in profile.items() if k != "url"}
                    )
            merged = {**(resume_data.get("contact") or {}), **filtered}
            # Validates types and http(s)-only linkedin/website/github/profiles.
            contact = ContactInfo.model_validate(merged)
            resume_data["contact"] = contact.model_dump(exclude_unset=True)
            update_resume_version_data(self._conn, vid, resume_data, user_id=user_id)
            return f"Updated contact fields: {', '.join(filtered.keys())}"

        # summary
        text = data.get("text", "")
        if not text or not isinstance(text, str):
            raise ValueError("Summary text must not be empty")
        check_len("summary", text, MAX_LONG)
        resume_data["summary"] = text
        update_resume_version_data(self._conn, vid, resume_data, user_id=user_id)
        return "Updated summary"

    def add_entry(
        self,
        section: str,
        data: dict[str, Any],
        version_id: int | None = None,
        *,
        user_id: str,
    ) -> str:
        """Add an entry to a list section of a resume version."""
        sdef = section_def(section)

        # Validate entry data by constructing the model
        entry = sdef.model.model_validate({**data, "id": None})
        _check_entry_lengths(entry.model_dump())

        version = self.get_resume(version_id, user_id=user_id)
        vid = version["id"]
        resume_data = version["resume_data"]
        entries = _entries(resume_data, section)

        if sdef.unique_field:
            value = getattr(entry, sdef.unique_field)
            for existing in entries:
                if str(existing.get(sdef.unique_field, "")).lower() == value.lower():
                    raise ValueError(
                        f"{sdef.label} entry '{value}' already exists"
                        + (
                            f" under category '{existing.get('category')}'"
                            if section == "skills"
                            else ""
                        )
                    )

        entry_dict = json.loads(entry.model_dump_json())
        entry_dict["id"] = uuid.uuid4().hex
        if sdef.insert == "prepend":
            entries.insert(0, entry_dict)
        else:
            entries.append(entry_dict)

        if len(entries) == 1:
            # First entry in a section that started out empty (and hidden by
            # default): show it, otherwise the new content would be invisible.
            for item in resume_data.get("layout") or []:
                if item.get("section") == section:
                    item["visible"] = True
        update_resume_version_data(self._conn, vid, resume_data, user_id=user_id)
        return f"Added {section} entry: {sdef.summary(entry)} (id={entry_dict['id']})"

    def update_entry(
        self,
        section: str,
        ref: str | int,
        data: dict[str, Any],
        version_id: int | None = None,
        *,
        user_id: str,
    ) -> str:
        """Update an entry in a list section by stable id (or legacy index)."""
        sdef = section_def(section)

        version = self.get_resume(version_id, user_id=user_id)
        vid = version["id"]
        resume_data = version["resume_data"]
        entries = _entries(resume_data, section)
        index = _resolve(entries, section, ref)

        # Re-validate the merged entry so bad types never reach storage.
        entry_id = entries[index].get("id")
        patch = {k: v for k, v in data.items() if k != "id"}
        updated = sdef.model.model_validate({**entries[index], **patch})
        _check_entry_lengths(updated.model_dump())
        entries[index] = {**json.loads(updated.model_dump_json()), "id": entry_id}

        update_resume_version_data(self._conn, vid, resume_data, user_id=user_id)
        return f"Updated {section} entry at index {index}: {sdef.summary(updated)}"

    def remove_entry(
        self,
        section: str,
        ref: str | int,
        version_id: int | None = None,
        *,
        user_id: str,
    ) -> str:
        """Remove an entry from a list section by stable id (or legacy index)."""
        sdef = section_def(section)

        version = self.get_resume(version_id, user_id=user_id)
        vid = version["id"]
        resume_data = version["resume_data"]
        entries = _entries(resume_data, section)
        index = _resolve(entries, section, ref)

        removed = sdef.model.model_validate(entries.pop(index))

        update_resume_version_data(self._conn, vid, resume_data, user_id=user_id)
        return f"Removed {section} entry: {sdef.summary(removed)}"

    # --- Layout and custom sections ---

    def update_layout(
        self,
        layout: list[dict[str, Any]],
        version_id: int | None = None,
        *,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """Replace the section order / visibility / titles of a version.

        Sections omitted from ``layout`` are appended in default order.
        """
        if not isinstance(layout, list):
            raise ValueError("Layout must be a list")
        version = self.get_resume(version_id, user_id=user_id)
        resume_data = version["resume_data"]
        valid = {
            "summary",
            *LIST_SECTIONS,
            *(custom_key(c) for c in resume_data.get("custom_sections") or {}),
        }
        seen: set[str] = set()
        items: list[dict[str, Any]] = []
        for raw in layout:
            if not isinstance(raw, dict):
                raise ValueError("Each layout item must be an object")
            key = raw.get("section")
            if key not in valid:
                raise ValueError(f"Unknown layout section: '{key}'")
            if key in seen:
                raise ValueError(f"Duplicate layout section: '{key}'")
            seen.add(key)
            title = raw.get("title")
            if title is not None and not isinstance(title, str):
                raise ValueError("Layout title must be a string")
            check_len("title", title, MAX_NAME)
            items.append(
                {
                    "section": key,
                    "visible": bool(raw.get("visible", True)),
                    "title": (title or "").strip() or None,
                }
            )
        resume_data["layout"] = normalize_layout(items, resume_data)
        update_resume_version_data(
            self._conn, version["id"], resume_data, user_id=user_id
        )
        return resume_data["layout"]

    def add_custom_section(
        self,
        title: str,
        version_id: int | None = None,
        *,
        user_id: str,
    ) -> str:
        """Add an empty user-defined section; returns its ``custom:<id>`` key."""
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Section title must not be empty")
        title = title.strip()
        check_len("title", title, MAX_NAME)
        version = self.get_resume(version_id, user_id=user_id)
        resume_data = version["resume_data"]
        cid = uuid.uuid4().hex[:8]
        customs = resume_data.setdefault("custom_sections", {})
        customs[cid] = CustomSection(title=title).model_dump()
        layout = normalize_layout(resume_data.get("layout") or [], resume_data)
        for item in layout:
            if item["section"] == custom_key(cid):
                item["visible"] = True
        resume_data["layout"] = layout
        update_resume_version_data(
            self._conn, version["id"], resume_data, user_id=user_id
        )
        return custom_key(cid)

    def remove_custom_section(
        self,
        section: str,
        version_id: int | None = None,
        *,
        user_id: str,
    ) -> str:
        """Delete a user-defined section and all of its entries."""
        if not is_custom(section):
            raise ValueError(f"Not a custom section: '{section}'")
        version = self.get_resume(version_id, user_id=user_id)
        resume_data = version["resume_data"]
        customs = resume_data.get("custom_sections") or {}
        removed = customs.pop(section[len(CUSTOM_PREFIX) :], None)
        if removed is None:
            raise ValueError(f"Unknown custom section: '{section}'")
        resume_data["custom_sections"] = customs
        resume_data["layout"] = normalize_layout(
            resume_data.get("layout") or [], resume_data
        )
        update_resume_version_data(
            self._conn, version["id"], resume_data, user_id=user_id
        )
        return f"Removed custom section '{removed.get('title')}'"
