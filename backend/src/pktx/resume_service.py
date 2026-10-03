"""ResumeService — shared business logic for resume version CRUD operations."""

import json
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
from pktx.models import (
    ContactInfo,
    Education,
    Skill,
    WorkExperience,
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
_ENTRY_NAME_FIELDS = {"title", "company", "institution", "degree", "name", "category"}
_MAX_HIGHLIGHT = 2000


def _check_entry_lengths(entry: dict[str, Any]) -> None:
    for key, value in entry.items():
        if isinstance(value, str):
            check_len(key, value, MAX_NAME if key in _ENTRY_NAME_FIELDS else MAX_SHORT)
        elif isinstance(value, list):
            for item in value:
                check_len(key, item, _MAX_HIGHLIGHT)


def _clean_label(label: Any) -> str:
    if not isinstance(label, str) or not label.strip():
        raise ValueError("Label must not be empty")
    label = label.strip()
    check_len("label", label, MAX_NAME)
    return label


SECTION_UPDATE = ("contact", "summary")
SECTION_LIST = ("experience", "education", "skills")
ALL_SECTIONS = ("contact", "summary", "experience", "education", "skills")


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
        if section not in ALL_SECTIONS:
            raise ValueError(
                f"Invalid section: '{section}'. "
                f"Must be one of: {', '.join(ALL_SECTIONS)}"
            )
        version = self.get_resume(version_id, user_id=user_id)
        resume_data = version["resume_data"]
        value = resume_data.get(section)
        return value

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
            merged = {**(resume_data.get("contact") or {}), **filtered}
            # Validates types and http(s)-only linkedin/website/github.
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
        if section not in SECTION_LIST:
            raise ValueError(
                f"Invalid section for add_entry: '{section}'. "
                f"Must be one of: {', '.join(SECTION_LIST)}"
            )

        # Validate entry data by constructing the model
        model_cls = _SECTION_MODELS[section]
        entry = model_cls.model_validate(data)
        _check_entry_lengths(entry.model_dump())

        version = self.get_resume(version_id, user_id=user_id)
        vid = version["id"]
        resume_data = version["resume_data"]

        entries = resume_data.get(section, [])

        # For skills, check for case-insensitive duplicates
        if section == "skills":
            for existing in entries:
                if existing.get("name", "").lower() == entry.name.lower():
                    raise ValueError(
                        f"Skill '{entry.name}' already exists "
                        f"under category '{existing.get('category')}'"
                    )

        # Prepend for experience/education, append for skills
        entry_dict = json.loads(entry.model_dump_json())
        if section in ("experience", "education"):
            entries.insert(0, entry_dict)
        else:
            entries.append(entry_dict)

        resume_data[section] = entries
        update_resume_version_data(self._conn, vid, resume_data, user_id=user_id)
        return f"Added {section} entry: {_entry_summary(section, entry)}"

    def update_entry(
        self,
        section: str,
        index: int,
        data: dict[str, Any],
        version_id: int | None = None,
        *,
        user_id: str,
    ) -> str:
        """Update an entry in a list section by index."""
        if section not in SECTION_LIST:
            raise ValueError(
                f"Invalid section for update_entry: '{section}'. "
                f"Must be one of: {', '.join(SECTION_LIST)}"
            )

        version = self.get_resume(version_id, user_id=user_id)
        vid = version["id"]
        resume_data = version["resume_data"]
        entries = resume_data.get(section, [])

        if index < 0 or index >= len(entries):
            raise ValueError(
                f"{section.title()} index {index} out of range. "
                f"Resume has {len(entries)} {section} entries."
            )

        model_cls = _SECTION_MODELS[section]
        # Re-validate the merged entry so bad types never reach storage.
        updated = model_cls.model_validate({**entries[index], **data})
        _check_entry_lengths(updated.model_dump())
        entries[index] = json.loads(updated.model_dump_json())

        resume_data[section] = entries
        update_resume_version_data(self._conn, vid, resume_data, user_id=user_id)
        return (
            f"Updated {section} entry at index {index}: "
            f"{_entry_summary(section, updated)}"
        )

    def remove_entry(
        self,
        section: str,
        index: int,
        version_id: int | None = None,
        *,
        user_id: str,
    ) -> str:
        """Remove an entry from a list section by index."""
        if section not in SECTION_LIST:
            raise ValueError(
                f"Invalid section for remove_entry: '{section}'. "
                f"Must be one of: {', '.join(SECTION_LIST)}"
            )

        version = self.get_resume(version_id, user_id=user_id)
        vid = version["id"]
        resume_data = version["resume_data"]
        entries = resume_data.get(section, [])

        if index < 0 or index >= len(entries):
            raise ValueError(
                f"{section.title()} index {index} out of range. "
                f"Resume has {len(entries)} {section} entries."
            )

        model_cls = _SECTION_MODELS[section]
        removed = model_cls(**entries[index])
        entries.pop(index)

        resume_data[section] = entries
        update_resume_version_data(self._conn, vid, resume_data, user_id=user_id)
        return f"Removed {section} entry: {_entry_summary(section, removed)}"


_SECTION_MODELS: dict[str, Any] = {
    "experience": WorkExperience,
    "education": Education,
    "skills": Skill,
}


def _entry_summary(section: str, entry: WorkExperience | Education | Skill) -> str:
    """Create a short human-readable summary of an entry."""
    if isinstance(entry, WorkExperience):
        return f"{entry.title} at {entry.company}"
    elif isinstance(entry, Education):
        return f"{entry.degree} from {entry.institution}"
    else:
        return f"{entry.name} ({entry.category})"
