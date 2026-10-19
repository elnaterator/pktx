"""MCP tool handlers for resume versions and their JSON Resume documents."""

from typing import Annotated, Any, Literal, get_args

from fastmcp import FastMCP
from pydantic import Field

from pktx.auth import require_user_id
from pktx.json_resume import Basics, Resume, dump
from pktx.resume_sections import LIST_SECTIONS, SECTIONS, entry_fields, section_data
from pktx.resume_service import ResumeService
from pktx.tools.errors import raises_tool_error

ListSection = Literal[
    "work",
    "education",
    "skills",
    "projects",
    "certificates",
    "awards",
    "publications",
    "volunteer",
    "languages",
    "interests",
    "references",
]
if get_args(ListSection) != LIST_SECTIONS:
    raise RuntimeError("ListSection is out of sync with the section registry")

_ENTRY_HELP = (
    "A JSON Resume entry (camelCase keys, partial for updates). Fields by section: "
    + "; ".join(f"{k}: {entry_fields(d.model)}" for k, d in SECTIONS.items())
    + ". Dates are YYYY, YYYY-MM or YYYY-MM-DD; omit endDate for a current role. "
    "A blank value clears a field on update."
)
EntryArg = Annotated[dict[str, Any], Field(description=_ENTRY_HELP)]


def register_resume_tools(mcp: FastMCP, get_service: Any) -> None:
    """Register resume version MCP tools on the given FastMCP instance."""

    @mcp.tool()
    @raises_tool_error
    def list_resumes() -> list[dict[str, Any]]:
        """List all resume versions with metadata.

        Returns summaries (id, label, is_default, tags, app_count, link_count,
        timestamps) without resume content.
        """
        service: ResumeService = get_service()
        return service.list_resumes(user_id=require_user_id())

    @mcp.tool()
    @raises_tool_error
    def get_resume(
        id: int | None = None,
        section: Annotated[
            Literal["basics", "meta", *get_args(ListSection)] | None,  # type: ignore[valid-type]
            Field(description="Return only this part of the document."),
        ] = None,
    ) -> dict[str, Any]:
        """Get a resume version, or one section of its document.

        The resume is `{id, label, tags, is_default, timestamps, links, data}`
        where `data` is a JSON Resume document (basics, work, education, ...).
        Every entry and profile has a stable `id`. Empty sections are omitted.

        Args:
            id: Resume version ID. If omitted, uses the default version.
            section: With a section, returns `{id, section, data}` holding just
                that part: `basics` and `meta` are objects, the rest are lists
                of entries (empty if the resume has none).
        """
        service: ResumeService = get_service()
        version = service.get_resume(id, user_id=require_user_id())
        if section is None:
            return version
        return {
            "id": version["id"],
            "section": section,
            "data": section_data(version["data"], section),
        }

    @mcp.tool()
    @raises_tool_error
    def create_resume(
        label: str,
        tags: list[str] | None = None,
        data: Resume | None = None,
    ) -> dict[str, Any]:
        """Create a resume version.

        Args:
            label: Label for the new version.
            tags: Tags for categorizing the version (e.g. "backend", "leadership").
            data: A whole JSON Resume document to start from. If omitted, the
                new version is a copy of the default.
        """
        service: ResumeService = get_service()
        return service.create_resume(
            label,
            user_id=require_user_id(),
            tags=tags,
            data=dump(data) if data is not None else None,
        )

    @mcp.tool()
    @raises_tool_error
    def update_resume(
        id: int,
        label: str | None = None,
        tags: list[str] | None = None,
        is_default: bool | None = None,
        data: Resume | None = None,
    ) -> dict[str, Any]:
        """Update a resume version. Omitted arguments are left unchanged.

        Args:
            id: Resume version ID.
            label: New label.
            tags: New tag list (replaces the existing tags).
            is_default: True makes this the default resume. The default cannot
                be unset; make another resume the default instead.
            data: A whole JSON Resume document. REPLACES the entire document;
                use the entry tools for small edits.
        """
        service: ResumeService = get_service()
        return service.update_resume(
            id,
            user_id=require_user_id(),
            label=label,
            tags=tags,
            is_default=is_default,
            data=dump(data) if data is not None else None,
        )

    @mcp.tool()
    @raises_tool_error
    def delete_resume(id: int) -> dict[str, Any]:
        """Delete a resume version.

        Args:
            id: Resume version ID. Cannot delete the last remaining version.

        Returns the deleted `{id, label}`.
        """
        service: ResumeService = get_service()
        return service.delete_resume(id, user_id=require_user_id())

    @mcp.tool()
    @raises_tool_error
    def update_resume_basics(id: int, basics: Basics) -> dict[str, Any]:
        """Update the `basics` of a resume (name, label, email, summary, ...).

        Only the fields you pass change; a blank value clears one. `location`
        and `profiles` are replaced as a whole when passed.

        Args:
            id: Resume version ID.
            basics: Fields to change.

        Returns the updated basics.
        """
        service: ResumeService = get_service()
        patch = basics.model_dump(mode="json", by_alias=True, exclude_unset=True)
        return service.update_basics(id, patch, user_id=require_user_id())

    @mcp.tool()
    @raises_tool_error
    def add_resume_entry(
        id: int,
        section: ListSection,
        entry: EntryArg,
        position: Annotated[
            int | None,
            Field(ge=0, description="0-based index; omit to append."),
        ] = None,
    ) -> dict[str, Any]:
        """Add an entry to a list section of a resume.

        Args:
            id: Resume version ID.
            section: The JSON Resume section, e.g. `work` or `skills`.
            entry: The new entry.
            position: Where to insert it, e.g. 0 to put a new job first.

        Returns the new entry, including its generated `id`.
        """
        service: ResumeService = get_service()
        return service.add_entry(
            id, section, entry, user_id=require_user_id(), position=position
        )

    @mcp.tool()
    @raises_tool_error
    def update_resume_entry(
        id: int, section: ListSection, entry_id: str, entry: EntryArg
    ) -> dict[str, Any]:
        """Update an entry of a resume. Only the fields you pass change.

        Args:
            id: Resume version ID.
            section: The JSON Resume section.
            entry_id: The entry's `id`.
            entry: Fields to change.

        Returns the updated entry.
        """
        service: ResumeService = get_service()
        return service.update_entry(
            id, section, entry_id, entry, user_id=require_user_id()
        )

    @mcp.tool()
    @raises_tool_error
    def remove_resume_entry(
        id: int, section: ListSection, entry_id: str
    ) -> dict[str, Any]:
        """Remove an entry from a resume.

        Args:
            id: Resume version ID.
            section: The JSON Resume section.
            entry_id: The entry's `id`.

        Returns the removed entry.
        """
        service: ResumeService = get_service()
        return service.remove_entry(id, section, entry_id, user_id=require_user_id())

    @mcp.tool()
    @raises_tool_error
    def reorder_resume_entries(
        id: int, section: ListSection, entry_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Reorder the entries of a section; the list order is the display order.

        Args:
            id: Resume version ID.
            section: The JSON Resume section.
            entry_ids: Every entry `id` of the section, exactly once, in the
                new order.

        Returns the reordered entries.
        """
        service: ResumeService = get_service()
        return service.reorder_entries(
            id, section, entry_ids, user_id=require_user_id()
        )
