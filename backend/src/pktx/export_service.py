"""User-facing data export: everything one user owns, as one JSON document.

The portability story — a single user's records, in the same shape the API
already returns them, readable without any pktx code. Database backups are not
this app's job: Neon's own point-in-time restore covers that.
"""

from datetime import datetime, timezone
from typing import Any

from pktx.accomplishment_service import AccomplishmentService
from pktx.application_service import ApplicationService
from pktx.communication_service import ContactCommunicationService
from pktx.contact_service import ContactService
from pktx.link_service import LinkService
from pktx.migrations import SCHEMA_VERSION
from pktx.note_service import NoteService
from pktx.resume_service import ResumeService


class ExportService:
    """Compose a full per-user export from the existing resource services."""

    def __init__(
        self,
        resume_service: ResumeService,
        app_service: ApplicationService | None = None,
        acc_service: AccomplishmentService | None = None,
        note_service: NoteService | None = None,
        contact_service: ContactService | None = None,
        comm_service: ContactCommunicationService | None = None,
        link_service: LinkService | None = None,
    ) -> None:
        self._resumes = resume_service
        self._apps = app_service
        self._accs = acc_service
        self._notes = note_service
        self._contacts = contact_service
        self._comms = comm_service
        self._links = link_service

    def export_user_data(self, user_id: str | None = None) -> dict[str, Any]:
        """Return every resource owned by ``user_id``.

        List endpoints return summaries, so each item is re-fetched by id to get
        full bodies (resume sections, note content, STAR fields, links).
        """
        uid = user_id or "legacy"

        resumes = [
            self._resumes.get_resume(r["id"], user_id=user_id)
            for r in self._resumes.list_resumes(user_id=user_id)
        ]

        applications: list[dict[str, Any]] = []
        if self._apps is not None:
            applications = [
                self._apps.get_application(a["id"], user_id=user_id)
                for a in self._apps.list_applications(user_id=user_id)
            ]

        accomplishments: list[dict[str, Any]] = []
        if self._accs is not None:
            accomplishments = [
                self._accs.get_accomplishment(a["id"], user_id=user_id)
                for a in self._accs.list_accomplishments(user_id=user_id)
            ]

        notes: list[dict[str, Any]] = []
        if self._notes is not None:
            notes = [
                self._notes.get_note(n["id"], user_id=user_id)
                for n in self._notes.list_notes(user_id=user_id)
            ]

        contacts: list[dict[str, Any]] = []
        communications: list[dict[str, Any]] = []
        if self._contacts is not None:
            contacts = [
                self._contacts.get_contact(c["id"], user_id=user_id)
                for c in self._contacts.list_contacts(user_id=user_id)
            ]
            if self._comms is not None:
                for contact in contacts:
                    for comm in self._comms.list_for_contact(
                        contact["id"], user_id=user_id
                    ):
                        communications.append({**comm, "contact_id": contact["id"]})

        links: list[dict[str, Any]] = []
        if self._links is not None:
            links = self._links.list_all(uid)

        return {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": SCHEMA_VERSION,
            "user_id": user_id,
            "resumes": resumes,
            "applications": applications,
            "accomplishments": accomplishments,
            "notes": notes,
            "contacts": contacts,
            "communications": communications,
            "links": links,
        }
