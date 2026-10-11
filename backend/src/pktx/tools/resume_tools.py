"""MCP tool handlers for resume version management."""

from typing import Any

from fastmcp import FastMCP

from pktx.auth import require_user_id
from pktx.models import Resume
from pktx.resume_sections import ALL_SECTIONS
from pktx.resume_service import ResumeService


def register_resume_tools(mcp: FastMCP, get_service: Any) -> None:
    """Register resume version MCP tools on the given FastMCP instance."""

    @mcp.tool()
    def list_resumes() -> list[dict[str, Any]]:
        """List all resume versions with metadata.

        Returns a list of resume version summaries (id, label, is_default,
        app_count, timestamps). Does not include resume content.
        """
        user_id = require_user_id()
        service: ResumeService = get_service()
        return service.list_resumes(user_id=user_id)

    @mcp.tool()
    def get_resume(id: int | None = None) -> dict[str, Any]:
        """Get a resume version with full resume data.

        Args:
            id: Resume version ID. If omitted, returns the default version.

        Returns the full resume version: contact, summary, every list section
        (each entry has a stable `id`) and `enabled_sections` (the optional
        sections shown for this version).
        """
        user_id = require_user_id()
        service: ResumeService = get_service()
        version = service.get_resume(id, user_id=user_id)
        # Normalize through Resume model
        resume = Resume(**version["resume_data"])
        result = {
            "id": version["id"],
            "label": version["label"],
            "is_default": version["is_default"],
            "resume_data": resume.model_dump(),
            "created_at": version["created_at"],
            "updated_at": version["updated_at"],
        }
        return result

    @mcp.tool()
    def get_resume_section(section: str, id: int | None = None) -> Any:
        """Get a specific section from a resume version.

        Args:
            section: One of: contact, summary, experience, education, skills,
                projects, certifications, awards, publications, volunteer,
                languages.
            id: Resume version ID. If omitted, uses default.
        """
        user_id = require_user_id()
        service: ResumeService = get_service()
        version = service.get_resume(id, user_id=user_id)
        resume = Resume(**version["resume_data"])
        data = resume.model_dump()
        if section not in ALL_SECTIONS:
            raise ValueError(
                f"Invalid section: '{section}'. "
                f"Must be one of: {', '.join(ALL_SECTIONS)}"
            )
        return data[section]

    @mcp.tool()
    def update_resume_section(id: int, section: str, data: dict[str, Any]) -> str:
        """Update a non-list section (contact or summary) on a resume version.

        Args:
            id: Resume version ID.
            section: One of: contact, summary.
            data: Fields to update. For contact: name, phone, location and
                  `fields`, the full list of {"key", "value"} details. Common
                  keys: Email, Website, LinkedIn, GitHub, GitLab, Portfolio, X,
                  Bluesky; any other key is allowed. Shortcut: email, website,
                  linkedin and github are upserted into `fields`.
                  For summary: {"text": "new summary"}.
        """
        user_id = require_user_id()
        service: ResumeService = get_service()
        return service.update_section(section, data, id, user_id=user_id)

    @mcp.tool()
    def add_resume_entry(id: int, section: str, data: dict[str, Any]) -> str:
        """Add an entry to a list section of a resume version.

        Args:
            id: Resume version ID.
            section: One of: experience, education, skills, projects,
                certifications, awards, publications, volunteer, languages.
            data: Entry fields. Required fields vary by section
                  (see the `fields` of `GET /api/resume-sections`).
        """
        user_id = require_user_id()
        service: ResumeService = get_service()
        return service.add_entry(section, data, id, user_id=user_id)

    @mcp.tool()
    def update_resume_entry(
        id: int, section: str, entry_id: str, data: dict[str, Any]
    ) -> str:
        """Update an entry in a list section of a resume version.

        Args:
            id: Resume version ID.
            section: One of: experience, education, skills, projects,
                certifications, awards, publications, volunteer, languages.
            entry_id: Stable `id` of the entry (a 0-based index is also accepted).
            data: Fields to update (partial update).
        """
        user_id = require_user_id()
        service: ResumeService = get_service()
        return service.update_entry(section, entry_id, data, id, user_id=user_id)

    @mcp.tool()
    def remove_resume_entry(id: int, section: str, entry_id: str) -> str:
        """Remove an entry from a list section of a resume version.

        Args:
            id: Resume version ID.
            section: One of: experience, education, skills, projects,
                certifications, awards, publications, volunteer, languages.
            entry_id: Stable `id` of the entry (a 0-based index is also accepted).
        """
        user_id = require_user_id()
        service: ResumeService = get_service()
        return service.remove_entry(section, entry_id, id, user_id=user_id)

    @mcp.tool()
    def set_resume_section_enabled(id: int, section: str, enabled: bool = True) -> str:
        """Add or remove an optional section on a resume version.

        Sections are shown in a fixed order. experience, education and skills
        are always shown; the optional ones are projects, certifications,
        awards, publications, volunteer and languages. Adding an entry to an
        optional section shows it automatically.

        Args:
            id: Resume version ID.
            section: An optional section key.
            enabled: True to add the section, False to remove it (only
                allowed while it has no entries).
        """
        user_id = require_user_id()
        service: ResumeService = get_service()
        return service.set_section_enabled(section, enabled, id, user_id=user_id)

    @mcp.tool()
    def create_resume(label: str, tags: list[str] | None = None) -> str:
        """Create a new resume version, initialized as a copy of the default.

        Args:
            label: Label for the new version.
            tags: Tags for categorizing the version (e.g. "backend", "leadership").
        """
        user_id = require_user_id()
        service: ResumeService = get_service()
        version = service.create_resume(label, user_id=user_id, tags=tags)
        return f"Created resume version '{label}' (id={version['id']})"

    @mcp.tool()
    def update_resume_metadata(
        id: int, label: str | None = None, tags: list[str] | None = None
    ) -> str:
        """Update label and/or tags for a resume version.

        Args:
            id: Resume version ID.
            label: New label for the version.
            tags: Tags for categorizing the resume version.
        """
        user_id = require_user_id()
        service: ResumeService = get_service()
        version = service.get_resume(id, user_id=user_id)
        new_label = label or version["label"]
        service.update_metadata(id, new_label, user_id=user_id, tags=tags)
        return f"Updated resume version {id}"

    @mcp.tool()
    def set_default_resume(id: int) -> str:
        """Set a resume version as the default.

        Args:
            id: Resume version ID.
        """
        user_id = require_user_id()
        service: ResumeService = get_service()
        return service.set_default(id, user_id=user_id)

    @mcp.tool()
    def delete_resume(id: int) -> str:
        """Delete a resume version.

        Args:
            id: Resume version ID. Cannot delete the last remaining version.
        """
        user_id = require_user_id()
        service: ResumeService = get_service()
        return service.delete_resume(id, user_id=user_id)
