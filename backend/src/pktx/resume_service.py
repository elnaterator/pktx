"""ResumeService: resume version CRUD and edits to the JSON Resume document."""

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
    update_resume_version,
)
from pktx.db import DBConnection
from pktx.json_resume import Basics, Resume, alias_keys, dump, validate
from pktx.link_service import LinkService
from pktx.resume_sections import section_def
from pktx.validation import MAX_NAME, check_len, normalize_tags


def _clean_label(label: Any) -> str:
    if not isinstance(label, str) or not label.strip():
        raise ValueError("Label must not be empty")
    label = label.strip()
    check_len("label", label, MAX_NAME)
    return label


def _with_ids(doc: dict[str, Any]) -> dict[str, Any]:
    """Give every entry and profile a unique id (existing ones are kept)."""
    seen: set[str] = set()

    def stamp(items: list[dict[str, Any]]) -> None:
        for item in items:
            if not item.get("id") or item["id"] in seen:
                item["id"] = uuid.uuid4().hex
            seen.add(item["id"])

    for value in doc.values():
        if isinstance(value, list):
            stamp(value)
    stamp((doc.get("basics") or {}).get("profiles") or [])
    return doc


def _document(data: Any) -> dict[str, Any]:
    """Validate a whole JSON Resume (either key case) into its stored form."""
    if not isinstance(data, dict):
        raise ValueError("Resume data must be a JSON object")
    return _with_ids(dump(validate(Resume, data)))


def _entry(
    section: str, data: Any, base: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Validated entry (without ``id``): ``base`` overlaid with ``data``."""
    if not isinstance(data, dict):
        raise ValueError("Entry must be a JSON object")
    model = section_def(section).model
    patch = alias_keys(model, {k: v for k, v in data.items() if k != "id"})
    entry = dump(validate(model, {**(base or {}), **patch}))
    entry.pop("id", None)
    if not entry:
        raise ValueError(f"A {section} entry needs at least one field")
    return entry


def _find(entries: list[dict[str, Any]], section: str, entry_id: str) -> int:
    for i, e in enumerate(entries):
        if e.get("id") == entry_id:
            return i
    raise ValueError(f"Resume {section} entry not found: '{entry_id}'")


class ResumeService:
    """Resume version operations with a constructor-injected DB connection."""

    def __init__(self, conn: DBConnection) -> None:
        self._conn = conn
        self._links = LinkService(conn)

    # --- Versions ---

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
            app_counts = link_counts_by_type(
                self._conn, "resume", ids, "application", user_id
            )
            for r in resumes:
                r["link_count"] = counts.get(r["id"], 0)
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
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a resume version from ``data``, else a copy of the default.

        With no ``data`` and no default resume the document starts empty.
        """
        label = _clean_label(label)
        normalized_tags = normalize_tags(tags)
        if data is not None:
            doc = _document(data)
        else:
            try:
                doc = load_default_resume_version(self._conn, user_id=user_id)["data"]
            except ValueError:
                doc = {}
        return create_resume_version(
            self._conn, label, doc, user_id=user_id, tags=normalized_tags
        )

    def update_resume(
        self,
        version_id: int,
        *,
        user_id: str,
        label: str | None = None,
        tags: list[str] | None = None,
        is_default: bool | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update label, tags, default flag and/or replace the whole document.

        ``None`` leaves a field unchanged. Everything is validated before any
        write, and the writes share one transaction.
        """
        if label is None and tags is None and is_default is None and data is None:
            raise ValueError("Nothing to update: provide label, tags, is_default, data")
        current = load_resume_version(self._conn, version_id, user_id=user_id)
        new_label = _clean_label(label) if label is not None else None
        new_tags = normalize_tags(tags) if tags is not None else None
        doc = _document(data) if data is not None else None
        if is_default is not None and not isinstance(is_default, bool):
            raise ValueError("is_default must be true or false")
        if is_default is False and current["is_default"]:
            raise ValueError(
                "Cannot unset the default resume; set another resume as the default"
            )
        with self._conn.transaction():
            update_resume_version(
                self._conn,
                version_id,
                user_id,
                label=new_label,
                tags=new_tags,
                data=doc,
            )
            if is_default:
                set_default_resume_version(self._conn, version_id, user_id=user_id)
        return self.get_resume(version_id, user_id=user_id)

    def delete_resume(self, version_id: int, *, user_id: str) -> dict[str, Any]:
        """Delete a resume version and its links atomically.

        Ownership is checked first so nothing is touched for a foreign id.
        """
        load_resume_version(self._conn, version_id, user_id=user_id)
        with self._conn.transaction():
            unlink_all_for(self._conn, "resume", version_id, user_id)
            label = delete_resume_version(self._conn, version_id, user_id=user_id)
        return {"id": version_id, "label": label}

    # --- Document edits ---

    def _doc(self, version_id: int, user_id: str) -> dict[str, Any]:
        """The version's document, fresh from the DB, to mutate and ``_save``."""
        return load_resume_version(self._conn, version_id, user_id=user_id)["data"]

    def _save(self, version_id: int, doc: dict[str, Any], user_id: str) -> None:
        update_resume_version(self._conn, version_id, user_id, data=doc)

    def update_basics(
        self, version_id: int, patch: dict[str, Any], *, user_id: str
    ) -> dict[str, Any]:
        """Merge ``patch`` into ``basics`` (``location`` and ``profiles`` replace)."""
        if not isinstance(patch, dict) or not patch:
            raise ValueError("At least one basics field must be provided")
        doc = self._doc(version_id, user_id)
        merged = {**doc.get("basics", {}), **alias_keys(Basics, patch)}
        basics = dump(validate(Basics, merged))
        if basics:
            doc["basics"] = basics
        else:
            doc.pop("basics", None)
        _with_ids(doc)
        self._save(version_id, doc, user_id)
        return doc.get("basics", {})

    def add_entry(
        self,
        version_id: int,
        section: str,
        entry: dict[str, Any],
        *,
        user_id: str,
        position: int | None = None,
    ) -> dict[str, Any]:
        """Add an entry (at the end, or at 0-based ``position``); returns it."""
        item = {"id": uuid.uuid4().hex, **_entry(section, entry)}
        doc = self._doc(version_id, user_id)
        entries = doc.setdefault(section, [])
        if position is None:
            position = len(entries)
        if not isinstance(position, int) or not 0 <= position <= len(entries):
            raise ValueError(f"Position must be between 0 and {len(entries)}")
        entries.insert(position, item)
        self._save(version_id, doc, user_id)
        return item

    def update_entry(
        self,
        version_id: int,
        section: str,
        entry_id: str,
        patch: dict[str, Any],
        *,
        user_id: str,
    ) -> dict[str, Any]:
        """Merge ``patch`` into an entry (a blank value clears the field)."""
        section_def(section)
        doc = self._doc(version_id, user_id)
        entries = doc.get(section, [])
        index = _find(entries, section, entry_id)
        entries[index] = {"id": entry_id, **_entry(section, patch, entries[index])}
        self._save(version_id, doc, user_id)
        return entries[index]

    def remove_entry(
        self, version_id: int, section: str, entry_id: str, *, user_id: str
    ) -> dict[str, Any]:
        """Remove an entry; returns it."""
        section_def(section)
        doc = self._doc(version_id, user_id)
        entries = doc.get(section, [])
        removed = entries.pop(_find(entries, section, entry_id))
        if not entries:
            doc.pop(section, None)
        self._save(version_id, doc, user_id)
        return removed

    def reorder_entries(
        self, version_id: int, section: str, entry_ids: list[str], *, user_id: str
    ) -> list[dict[str, Any]]:
        """Reorder a section; ``entry_ids`` must be its current ids, each once."""
        section_def(section)
        doc = self._doc(version_id, user_id)
        entries = doc.get(section, [])
        by_id = {e["id"]: e for e in entries}
        if (
            not isinstance(entry_ids, list)
            or len(entry_ids) != len(entries)
            or set(entry_ids) != set(by_id)
        ):
            raise ValueError(
                f"entry_ids must list every {section} entry id exactly once"
            )
        doc[section] = [by_id[i] for i in entry_ids]
        self._save(version_id, doc, user_id)
        return doc[section]
