"""MCP tool handlers for networking contact management."""

from typing import Any

from fastmcp import FastMCP

from pktx.auth import require_user_id
from pktx.communication_service import ContactCommunicationService
from pktx.contact_service import ContactService


def register_contact_tools(
    mcp: FastMCP, get_service: Any, get_comm_service: Any = None
) -> None:
    """Register contact MCP tools on the given FastMCP instance."""

    @mcp.tool()
    def list_contacts(
        tag: str | None = None, q: str | None = None
    ) -> list[dict[str, Any]]:
        """List networking contacts as summaries (notes omitted).

        Args:
            tag: Filter by exact tag. Returns only contacts that include this tag.
            q: Case-insensitive substring search across name, company, title, notes.
                Multiple words are AND-matched.
        """
        user_id = require_user_id()
        service: ContactService = get_service()
        return service.list_contacts(tags=[tag] if tag else None, q=q, user_id=user_id)

    @mcp.tool()
    def get_contact(id: int) -> dict[str, Any] | str:
        """Get full detail for a specific contact including notes.

        Args:
            id: Contact ID.
        """
        user_id = require_user_id()
        service: ContactService = get_service()
        try:
            return service.get_contact(id, user_id=user_id)
        except ValueError as e:
            return f"Error: {e}"

    @mcp.tool()
    def create_contact(
        name: str,
        email: str | None = None,
        phone: str | None = None,
        company: str | None = None,
        title: str | None = None,
        relationship: str | None = None,
        linkedin_url: str | None = None,
        location: str | None = None,
        last_contacted_date: str | None = None,
        followup_date: str | None = None,
        notes: str = "",
        tags: list[str] | None = None,
    ) -> str:
        """Create a new networking contact.

        Args:
            name: Contact's full name (required).
            email: Email address.
            phone: Phone number.
            company: Company or organization.
            title: Job title or role.
            relationship: Relationship type (e.g. Colleague, Recruiter, Mentor).
            linkedin_url: LinkedIn profile URL.
            location: City, region, or country.
            last_contacted_date: Date last contacted (YYYY-MM-DD).
            followup_date: Date to follow up (YYYY-MM-DD).
            notes: Free-form markdown notes about this person.
            tags: Category tags.
        """
        user_id = require_user_id()
        service: ContactService = get_service()
        try:
            contact = service.create_contact(
                {
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "company": company,
                    "title": title,
                    "relationship": relationship,
                    "linkedin_url": linkedin_url,
                    "location": location,
                    "last_contacted_date": last_contacted_date,
                    "followup_date": followup_date,
                    "notes": notes,
                    "tags": tags or [],
                },
                user_id=user_id,
            )
            return f"Created contact '{contact['name']}' (id={contact['id']})"
        except ValueError as e:
            return f"Error: {e}"

    @mcp.tool()
    def update_contact(
        id: int,
        name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        company: str | None = None,
        title: str | None = None,
        relationship: str | None = None,
        linkedin_url: str | None = None,
        location: str | None = None,
        last_contacted_date: str | None = None,
        followup_date: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """Update fields of an existing contact (partial update).

        Only provided fields are changed; omitted fields retain their current values.

        Args:
            id: Contact ID.
            name: New name (must not be blank if provided).
            email: Updated email address.
            phone: Updated phone number.
            company: Updated company.
            title: Updated job title.
            relationship: Updated relationship type.
            linkedin_url: Updated LinkedIn URL.
            location: Updated location.
            last_contacted_date: Updated last-contacted date (YYYY-MM-DD).
            followup_date: Updated follow-up date (YYYY-MM-DD).
            notes: Updated free-form notes.
            tags: Updated tag list (replaces existing tags).
        """
        user_id = require_user_id()
        service: ContactService = get_service()
        data: dict[str, Any] = {}
        for field, value in [
            ("name", name),
            ("email", email),
            ("phone", phone),
            ("company", company),
            ("title", title),
            ("relationship", relationship),
            ("linkedin_url", linkedin_url),
            ("location", location),
            ("last_contacted_date", last_contacted_date),
            ("followup_date", followup_date),
            ("notes", notes),
            ("tags", tags),
        ]:
            if value is not None:
                data[field] = value
        try:
            service.update_contact(id, data, user_id=user_id)
            return f"Updated contact {id}"
        except ValueError as e:
            return f"Error: {e}"

    @mcp.tool()
    def delete_contact(id: int) -> str:
        """Delete a networking contact by ID.

        Args:
            id: Contact ID.
        """
        user_id = require_user_id()
        service: ContactService = get_service()
        try:
            contact = service.delete_contact(id, user_id=user_id)
            return f"Deleted contact '{contact['name']}' (id={id})"
        except ValueError as e:
            return f"Error: {e}"

    if get_comm_service is None:
        return

    @mcp.tool()
    def list_contact_communications(contact_id: int) -> list[dict[str, Any]] | str:
        """List communications for a networking contact.

        Args:
            contact_id: Contact ID.
        """
        user_id = require_user_id()
        svc: ContactCommunicationService = get_comm_service()
        try:
            return svc.list_for_contact(contact_id, user_id=user_id)
        except ValueError as e:
            return f"Error: {e}"

    @mcp.tool()
    def add_contact_communication(
        contact_id: int,
        type: str,
        direction: str,
        body: str,
        date: str,
        subject: str = "",
        status: str = "sent",
        tags: list[str] | None = None,
    ) -> str:
        """Add a communication to a networking contact.

        Args:
            contact_id: Contact ID.
            type: One of: email, phone, interview_note, other.
            direction: One of: sent, received.
            body: Communication body text.
            date: Date in YYYY-MM-DD format.
            subject: Optional subject line.
            status: One of: draft, ready, sent, archived.
            tags: Optional list of tags.
        """
        user_id = require_user_id()
        svc: ContactCommunicationService = get_comm_service()
        try:
            comm = svc.add_for_contact(
                contact_id,
                {
                    "type": type,
                    "direction": direction,
                    "body": body,
                    "date": date,
                    "subject": subject,
                    "status": status,
                    "tags": tags or [],
                },
                user_id=user_id,
            )
            return f"Added communication (id={comm['id']}) to contact {contact_id}"
        except ValueError as e:
            return f"Error: {e}"

    @mcp.tool()
    def update_contact_communication(
        comm_id: int,
        type: str | None = None,
        direction: str | None = None,
        body: str | None = None,
        date: str | None = None,
        subject: str | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """Update a contact communication (partial update).

        Args:
            comm_id: Communication ID.
            type: Updated type.
            direction: Updated direction.
            body: Updated body text.
            date: Updated date (YYYY-MM-DD).
            subject: Updated subject.
            status: Updated status.
            tags: Updated tag list (replaces existing).
        """
        user_id = require_user_id()
        svc: ContactCommunicationService = get_comm_service()
        data: dict[str, Any] = {}
        for field, value in [
            ("type", type),
            ("direction", direction),
            ("body", body),
            ("date", date),
            ("subject", subject),
            ("status", status),
            ("tags", tags),
        ]:
            if value is not None:
                data[field] = value
        try:
            svc.update(comm_id, data, user_id=user_id)
            return f"Updated communication {comm_id}"
        except ValueError as e:
            return f"Error: {e}"

    @mcp.tool()
    def remove_contact_communication(comm_id: int) -> str:
        """Remove a contact communication.

        Args:
            comm_id: Communication ID.
        """
        user_id = require_user_id()
        svc: ContactCommunicationService = get_comm_service()
        try:
            subject = svc.remove(comm_id, user_id=user_id)
            return f"Removed communication '{subject}' (id={comm_id})"
        except ValueError as e:
            return f"Error: {e}"

    @mcp.tool()
    def search_communications(
        q: str | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]] | str:
        """Search communications across all networking contacts.

        Args:
            q: Substring search on subject, body, contact name.
            tag: Filter by exact tag.
        """
        user_id = require_user_id()
        svc: ContactCommunicationService = get_comm_service()
        try:
            return svc.search(
                q=q,
                tags=[tag] if tag else None,
                user_id=user_id,
            )
        except ValueError as e:
            return f"Error: {e}"
