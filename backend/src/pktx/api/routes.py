"""FastAPI route handlers for the pktx REST API."""

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from pktx.accomplishment_service import AccomplishmentService
from pktx.application_service import ApplicationService
from pktx.auth import UserContext
from pktx.communication_service import ContactCommunicationService
from pktx.contact_service import ContactService
from pktx.export_service import ExportService
from pktx.link_service import RESOURCE_TYPES, LinkService
from pktx.models import Resume
from pktx.note_service import NoteService
from pktx.resume_service import ALL_SECTIONS, SECTION_LIST, ResumeService
from pktx.search_service import SearchService

_NO_AUTH_USER = UserContext(id="legacy", email=None, display_name=None)


def _make_user_dep(get_current_user: Callable | None) -> Callable:
    """Return a FastAPI dependency that always yields a ``UserContext``.

    When auth is disabled (``get_current_user`` is ``None``, local/test mode),
    every request runs as the seeded ``"legacy"`` user, so handlers can use
    ``current_user.id`` unconditionally and every query stays user-scoped.
    """
    if get_current_user is not None:
        return get_current_user

    async def _no_auth() -> UserContext:
        return _NO_AUTH_USER

    return _no_auth


def _client_error(e: Exception) -> HTTPException:
    """Map a service ValueError/TypeError to 404 (missing) or 422 (bad input)."""
    detail = str(e)
    if "not found" in detail or "out of range" in detail:
        return HTTPException(status_code=404, detail=detail)
    return HTTPException(status_code=422, detail=detail)


def create_router(
    service: ResumeService,
    app_service: ApplicationService | None = None,
    acc_service: AccomplishmentService | None = None,
    note_service: NoteService | None = None,
    contact_service: ContactService | None = None,
    comm_service: ContactCommunicationService | None = None,
    link_service: LinkService | None = None,
    get_current_user: Callable | None = None,
) -> APIRouter:
    """Create an APIRouter with all endpoints.

    Args:
        service: Resume service.
        app_service: Optional application service.
        acc_service: Optional accomplishment service.
        get_current_user: Optional FastAPI dependency that validates Bearer JWTs
            and returns a ``UserContext``. When provided, all routes except
            ``GET /health`` and ``POST /api/webhooks/clerk`` require a valid
            token.
    """
    # Top-level router — only truly public endpoints land here.
    router = APIRouter()

    # All API routes are protected. When auth is disabled the dependency list
    # is empty, so existing tests keep working without any token.
    _auth_deps = [Depends(get_current_user)] if get_current_user is not None else []
    api = APIRouter(dependencies=_auth_deps)

    # Optional-user dependency: always returns UserContext | None.
    _user_dep = _make_user_dep(get_current_user)

    # ------------------------------------------------------------------
    # Public: health check (no auth required)
    # ------------------------------------------------------------------

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # ------------------------------------------------------------------
    # Resume Version Routes
    # ------------------------------------------------------------------

    @api.get("/api/resumes")
    def list_resumes(
        tag: list[str] | None = Query(default=None),
        q: str | None = None,
        current_user: UserContext = Depends(_user_dep),
    ) -> list[dict[str, Any]]:
        return service.list_resumes(user_id=current_user.id, tags=tag, q=q)

    @api.post("/api/resumes", status_code=201)
    def create_resume(
        data: dict[str, Any],
        current_user: UserContext = Depends(_user_dep),
    ) -> dict[str, Any]:
        label = data.get("label", "")
        if not isinstance(label, str) or not label.strip():
            raise HTTPException(status_code=422, detail="Label is required")
        tags = data.get("tags") or []
        try:
            return service.create_resume(label, user_id=current_user.id, tags=tags)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    # NOTE: /tags MUST be registered BEFORE /{version_id} to prevent FastAPI
    # matching the literal string "tags" as an integer path parameter.
    @api.get("/api/resumes/tags")
    def list_resume_tags(
        current_user: UserContext = Depends(_user_dep),
    ) -> list[str]:
        return service.list_tags(user_id=current_user.id)

    @api.get("/api/resumes/default")
    def get_default_resume(
        current_user: UserContext = Depends(_user_dep),
    ) -> dict[str, Any]:
        try:
            version = service.get_resume(None, user_id=current_user.id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        resume = Resume(**version["resume_data"])
        version["resume_data"] = resume.model_dump()
        return version

    @api.get("/api/resumes/{version_id}")
    def get_resume_version(
        version_id: int,
        current_user: UserContext = Depends(_user_dep),
    ) -> dict[str, Any]:
        try:
            version = service.get_resume(version_id, user_id=current_user.id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        resume = Resume(**version["resume_data"])
        version["resume_data"] = resume.model_dump()
        return version

    @api.patch("/api/resumes/{version_id}")
    def update_resume_metadata(
        version_id: int,
        data: dict[str, Any],
        current_user: UserContext = Depends(_user_dep),
    ) -> dict[str, Any]:
        label = data.get("label", "")
        if not isinstance(label, str) or not label.strip():
            raise HTTPException(status_code=422, detail="Label is required")
        tags = data.get("tags")
        try:
            version = service.update_metadata(
                version_id, label, user_id=current_user.id, tags=tags
            )
        except ValueError as e:
            detail = str(e)
            if "not found" in detail:
                raise HTTPException(status_code=404, detail=detail)
            raise HTTPException(status_code=422, detail=detail)
        resume = Resume(**version["resume_data"])
        version["resume_data"] = resume.model_dump()
        return version

    @api.delete("/api/resumes/{version_id}")
    def delete_resume_version(
        version_id: int,
        current_user: UserContext = Depends(_user_dep),
    ) -> dict[str, str]:
        try:
            msg = service.delete_resume(version_id, user_id=current_user.id)
        except ValueError as e:
            detail = str(e)
            if "last remaining" in detail:
                raise HTTPException(status_code=409, detail=detail)
            raise HTTPException(status_code=404, detail=detail)
        return {"message": msg}

    @api.post("/api/resumes/{version_id}/default")
    def set_resume_default(
        version_id: int,
        current_user: UserContext = Depends(_user_dep),
    ) -> dict[str, str]:
        try:
            msg = service.set_default(version_id, user_id=current_user.id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return {"message": msg}

    @api.get("/api/resumes/{version_id}/{section}")
    def get_resume_section(
        version_id: int,
        section: str,
        current_user: UserContext = Depends(_user_dep),
    ) -> Any:
        if section not in ALL_SECTIONS:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Invalid section: '{section}'. "
                    f"Must be one of: {', '.join(ALL_SECTIONS)}"
                ),
            )
        try:
            version = service.get_resume(version_id, user_id=current_user.id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        resume = Resume(**version["resume_data"])
        return resume.model_dump()[section]

    @api.put("/api/resumes/{version_id}/contact")
    def update_resume_contact(
        version_id: int,
        data: dict[str, Any],
        current_user: UserContext = Depends(_user_dep),
    ) -> dict[str, str]:
        try:
            msg = service.update_section(
                "contact", data, version_id, user_id=current_user.id
            )
        except ValueError as e:
            raise _client_error(e)
        return {"message": msg}

    @api.put("/api/resumes/{version_id}/summary")
    def update_resume_summary(
        version_id: int,
        data: dict[str, Any],
        current_user: UserContext = Depends(_user_dep),
    ) -> dict[str, str]:
        text = data.get("text", "")
        if not text:
            raise HTTPException(
                status_code=422, detail="Summary text must not be empty"
            )
        try:
            msg = service.update_section(
                "summary", data, version_id, user_id=current_user.id
            )
        except ValueError as e:
            raise _client_error(e)
        return {"message": msg}

    @api.post("/api/resumes/{version_id}/{section}/entries", status_code=201)
    def add_resume_entry(
        version_id: int,
        section: str,
        data: dict[str, Any],
        current_user: UserContext = Depends(_user_dep),
    ) -> dict[str, str]:
        if section not in SECTION_LIST:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid section for entries: '{section}'. "
                    f"Must be one of: {', '.join(SECTION_LIST)}"
                ),
            )
        try:
            msg = service.add_entry(section, data, version_id, user_id=current_user.id)
        except (ValueError, TypeError) as e:
            raise _client_error(e)
        return {"message": msg}

    @api.put("/api/resumes/{version_id}/{section}/entries/{index}")
    def update_resume_entry(
        version_id: int,
        section: str,
        index: int,
        data: dict[str, Any],
        current_user: UserContext = Depends(_user_dep),
    ) -> dict[str, str]:
        if section not in SECTION_LIST:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid section for entries: '{section}'. "
                    f"Must be one of: {', '.join(SECTION_LIST)}"
                ),
            )
        try:
            msg = service.update_entry(
                section, index, data, version_id, user_id=current_user.id
            )
        except (ValueError, TypeError) as e:
            raise _client_error(e)
        return {"message": msg}

    @api.delete("/api/resumes/{version_id}/{section}/entries/{index}")
    def remove_resume_entry(
        version_id: int,
        section: str,
        index: int,
        current_user: UserContext = Depends(_user_dep),
    ) -> dict[str, str]:
        if section not in SECTION_LIST:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid section for entries: '{section}'. "
                    f"Must be one of: {', '.join(SECTION_LIST)}"
                ),
            )
        try:
            msg = service.remove_entry(
                section, index, version_id, user_id=current_user.id
            )
        except ValueError as e:
            raise _client_error(e)
        return {"message": msg}

    # ==========================================================
    # Application Routes
    # ==========================================================

    if app_service is not None:

        @api.get("/api/applications")
        def list_applications(
            status: list[str] | None = Query(default=None),
            tag: list[str] | None = Query(default=None),
            q: str | None = None,
            current_user: UserContext = Depends(_user_dep),
        ) -> list[dict[str, Any]]:
            return app_service.list_applications(
                status=status, tags=tag, q=q, user_id=current_user.id
            )

        @api.post("/api/applications", status_code=201)
        def create_application(
            data: dict[str, Any],
            current_user: UserContext = Depends(_user_dep),
        ) -> dict[str, Any]:
            try:
                return app_service.create_application(data, user_id=current_user.id)
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e))

        # NOTE: /tags MUST be registered BEFORE /{app_id} to prevent FastAPI
        # matching the literal string "tags" as an integer path parameter.
        @api.get("/api/applications/tags")
        def list_application_tags(
            current_user: UserContext = Depends(_user_dep),
        ) -> list[str]:
            return app_service.list_tags(user_id=current_user.id)

        @api.get("/api/applications/{app_id}")
        def get_application(
            app_id: int,
            current_user: UserContext = Depends(_user_dep),
        ) -> dict[str, Any]:
            try:
                return app_service.get_application(app_id, user_id=current_user.id)
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @api.patch("/api/applications/{app_id}")
        def update_application(
            app_id: int,
            data: dict[str, Any],
            current_user: UserContext = Depends(_user_dep),
        ) -> dict[str, Any]:
            try:
                return app_service.update_application(
                    app_id, data, user_id=current_user.id
                )
            except ValueError as e:
                detail = str(e)
                if "not found" in detail:
                    raise HTTPException(status_code=404, detail=detail)
                raise HTTPException(status_code=422, detail=detail)

        @api.delete("/api/applications/{app_id}")
        def delete_application(
            app_id: int,
            current_user: UserContext = Depends(_user_dep),
        ) -> dict[str, str]:
            try:
                app = app_service.delete_application(app_id, user_id=current_user.id)
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
            return {
                "message": (
                    f"Deleted application '{app['position']}' at "
                    f"'{app['company']}' and all associated data"
                )
            }

        # --- Application Context ---

        @api.get("/api/applications/{app_id}/context")
        def get_application_context(
            app_id: int,
            current_user: UserContext = Depends(_user_dep),
        ) -> dict[str, Any]:
            try:
                return app_service.get_application_context(
                    app_id, user_id=current_user.id
                )
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

    # ==========================================================
    # Accomplishment Routes
    # ==========================================================

    if acc_service is not None:

        @api.get("/api/accomplishments")
        def list_accomplishments(
            tag: list[str] | None = Query(default=None),
            q: str | None = None,
            current_user: UserContext = Depends(_user_dep),
        ) -> list[dict[str, Any]]:
            return acc_service.list_accomplishments(
                tags=tag, q=q, user_id=current_user.id
            )

        @api.post("/api/accomplishments", status_code=201)
        def create_accomplishment(
            data: dict[str, Any],
            current_user: UserContext = Depends(_user_dep),
        ) -> dict[str, Any]:
            try:
                return acc_service.create_accomplishment(data, user_id=current_user.id)
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e))

        # NOTE: /tags MUST be registered BEFORE /{acc_id} to prevent FastAPI
        # matching the literal string "tags" as an integer path parameter.
        @api.get("/api/accomplishments/tags")
        def list_accomplishment_tags(
            current_user: UserContext = Depends(_user_dep),
        ) -> list[str]:
            return acc_service.list_tags(user_id=current_user.id)

        @api.get("/api/accomplishments/{acc_id}")
        def get_accomplishment(
            acc_id: int,
            current_user: UserContext = Depends(_user_dep),
        ) -> dict[str, Any]:
            try:
                return acc_service.get_accomplishment(acc_id, user_id=current_user.id)
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @api.patch("/api/accomplishments/{acc_id}")
        def update_accomplishment(
            acc_id: int,
            data: dict[str, Any],
            current_user: UserContext = Depends(_user_dep),
        ) -> dict[str, Any]:
            try:
                return acc_service.update_accomplishment(
                    acc_id, data, user_id=current_user.id
                )
            except ValueError as e:
                detail = str(e)
                if "not found" in detail:
                    raise HTTPException(status_code=404, detail=detail)
                raise HTTPException(status_code=422, detail=detail)

        @api.delete("/api/accomplishments/{acc_id}")
        def delete_accomplishment(
            acc_id: int,
            current_user: UserContext = Depends(_user_dep),
        ) -> dict[str, str]:
            try:
                acc = acc_service.delete_accomplishment(acc_id, user_id=current_user.id)
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
            return {"message": f"Deleted accomplishment '{acc['title']}'"}

    # ==========================================================
    # Note Routes
    # ==========================================================

    if note_service is not None:

        @api.get("/api/notes")
        def list_notes(
            tag: list[str] | None = Query(default=None),
            q: str | None = None,
            current_user: UserContext = Depends(_user_dep),
        ) -> list[dict[str, Any]]:
            return note_service.list_notes(tags=tag, q=q, user_id=current_user.id)

        @api.post("/api/notes", status_code=201)
        def create_note(
            data: dict[str, Any],
            current_user: UserContext = Depends(_user_dep),
        ) -> dict[str, Any]:
            try:
                return note_service.create_note(data, user_id=current_user.id)
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e))

        # NOTE: /tags MUST be registered BEFORE /{note_id} to prevent FastAPI
        # matching the literal string "tags" as an integer path parameter.
        @api.get("/api/notes/tags")
        def list_note_tags(
            current_user: UserContext = Depends(_user_dep),
        ) -> list[str]:
            return note_service.list_tags(user_id=current_user.id)

        @api.get("/api/notes/{note_id}")
        def get_note(
            note_id: int,
            current_user: UserContext = Depends(_user_dep),
        ) -> dict[str, Any]:
            try:
                return note_service.get_note(note_id, user_id=current_user.id)
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @api.patch("/api/notes/{note_id}")
        def update_note(
            note_id: int,
            data: dict[str, Any],
            current_user: UserContext = Depends(_user_dep),
        ) -> dict[str, Any]:
            try:
                return note_service.update_note(note_id, data, user_id=current_user.id)
            except ValueError as e:
                detail = str(e)
                if "not found" in detail:
                    raise HTTPException(status_code=404, detail=detail)
                raise HTTPException(status_code=422, detail=detail)

        @api.delete("/api/notes/{note_id}")
        def delete_note(
            note_id: int,
            current_user: UserContext = Depends(_user_dep),
        ) -> dict[str, str]:
            try:
                note = note_service.delete_note(note_id, user_id=current_user.id)
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
            return {"message": f"Deleted note '{note['title']}'"}

    # ==========================================================
    # Contact Routes
    # ==========================================================

    if contact_service is not None:

        @api.get("/api/contacts")
        def list_contacts(
            tag: list[str] | None = Query(default=None),
            q: str | None = None,
            current_user: UserContext = Depends(_user_dep),
        ) -> list[dict[str, Any]]:
            return contact_service.list_contacts(tags=tag, q=q, user_id=current_user.id)

        @api.post("/api/contacts", status_code=201)
        def create_contact(
            data: dict[str, Any],
            current_user: UserContext = Depends(_user_dep),
        ) -> dict[str, Any]:
            try:
                return contact_service.create_contact(data, user_id=current_user.id)
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e))

        # NOTE: /tags MUST be registered BEFORE /{contact_id} to prevent FastAPI
        # matching the literal string "tags" as an integer path parameter.
        @api.get("/api/contacts/tags")
        def list_contact_tags(
            current_user: UserContext = Depends(_user_dep),
        ) -> list[str]:
            return contact_service.list_tags(user_id=current_user.id)

        @api.get("/api/contacts/{contact_id}")
        def get_contact(
            contact_id: int,
            current_user: UserContext = Depends(_user_dep),
        ) -> dict[str, Any]:
            try:
                return contact_service.get_contact(contact_id, user_id=current_user.id)
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @api.patch("/api/contacts/{contact_id}")
        def update_contact(
            contact_id: int,
            data: dict[str, Any],
            current_user: UserContext = Depends(_user_dep),
        ) -> dict[str, Any]:
            try:
                return contact_service.update_contact(
                    contact_id, data, user_id=current_user.id
                )
            except ValueError as e:
                detail = str(e)
                if "not found" in detail:
                    raise HTTPException(status_code=404, detail=detail)
                raise HTTPException(status_code=422, detail=detail)

        @api.delete("/api/contacts/{contact_id}")
        def delete_contact(
            contact_id: int,
            current_user: UserContext = Depends(_user_dep),
        ) -> dict[str, str]:
            try:
                contact = contact_service.delete_contact(
                    contact_id, user_id=current_user.id
                )
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
            return {"message": f"Deleted contact '{contact['name']}'"}

    # ==========================================================
    # Contact Communication Routes
    # ==========================================================

    if comm_service is not None:

        @api.get("/api/contacts/{cid}/communications")
        def list_contact_communications(
            cid: int,
            current_user: UserContext = Depends(_user_dep),
        ) -> list[dict[str, Any]]:
            try:
                return comm_service.list_for_contact(cid, user_id=current_user.id)
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @api.post("/api/contacts/{cid}/communications", status_code=201)
        def add_contact_communication(
            cid: int,
            data: dict[str, Any],
            current_user: UserContext = Depends(_user_dep),
        ) -> dict[str, Any]:
            try:
                return comm_service.add_for_contact(cid, data, user_id=current_user.id)
            except ValueError as e:
                detail = str(e)
                if "not found" in detail:
                    raise HTTPException(status_code=404, detail=detail)
                raise HTTPException(status_code=422, detail=detail)

        @api.patch("/api/contacts/{cid}/communications/{cmid}")
        def update_contact_communication(
            cid: int,
            cmid: int,
            data: dict[str, Any],
            current_user: UserContext = Depends(_user_dep),
        ) -> dict[str, Any]:
            try:
                return comm_service.update(
                    cmid, data, user_id=current_user.id, contact_id=cid
                )
            except ValueError as e:
                detail = str(e)
                if "not found" in detail:
                    raise HTTPException(status_code=404, detail=detail)
                raise HTTPException(status_code=422, detail=detail)

        @api.delete("/api/contacts/{cid}/communications/{cmid}")
        def delete_contact_communication(
            cid: int,
            cmid: int,
            current_user: UserContext = Depends(_user_dep),
        ) -> dict[str, str]:
            try:
                subject = comm_service.remove(
                    cmid, user_id=current_user.id, contact_id=cid
                )
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
            return {"message": f"Removed communication '{subject}'"}

        # NOTE: /search MUST be registered before /{cid} path params to avoid
        # FastAPI matching the literal string "search".
        @api.get("/api/communications")
        def search_communications(
            q: str | None = None,
            tag: list[str] | None = Query(default=None),
            current_user: UserContext = Depends(_user_dep),
        ) -> list[dict[str, Any]]:
            return comm_service.search(q=q, tags=tag, user_id=current_user.id)

    # ==========================================================
    # Resource Link Routes
    # ==========================================================

    if link_service is not None:

        @api.post("/api/links", status_code=201)
        def create_link(
            data: dict[str, Any],
            current_user: UserContext = Depends(_user_dep),
        ) -> dict[str, str]:
            a_type = data.get("a_type", "")
            b_type = data.get("b_type", "")
            a_id = data.get("a_id")
            b_id = data.get("b_id")
            if a_type not in RESOURCE_TYPES or b_type not in RESOURCE_TYPES:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Invalid resource type. Must be one of: "
                        f"{', '.join(RESOURCE_TYPES)}"
                    ),
                )
            if not isinstance(a_id, int) or not isinstance(b_id, int):
                raise HTTPException(
                    status_code=422, detail="a_id and b_id must be integers"
                )
            try:
                link_service.link(a_type, a_id, b_type, b_id, current_user.id)
            except ValueError as e:
                detail = str(e)
                if "not found" in detail or "not owned" in detail:
                    raise HTTPException(status_code=404, detail=detail)
                raise HTTPException(status_code=422, detail=detail)
            return {"message": f"Linked {a_type}/{a_id} ↔ {b_type}/{b_id}"}

        @api.delete("/api/links", status_code=204)
        def remove_link(
            data: dict[str, Any],
            current_user: UserContext = Depends(_user_dep),
        ) -> None:
            a_type = data.get("a_type", "")
            b_type = data.get("b_type", "")
            a_id = data.get("a_id")
            b_id = data.get("b_id")
            if a_type not in RESOURCE_TYPES or b_type not in RESOURCE_TYPES:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Invalid resource type. Must be one of: "
                        f"{', '.join(RESOURCE_TYPES)}"
                    ),
                )
            if not isinstance(a_id, int) or not isinstance(b_id, int):
                raise HTTPException(
                    status_code=422, detail="a_id and b_id must be integers"
                )
            try:
                link_service.unlink(a_type, a_id, b_type, b_id, current_user.id)
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e))

    # ==========================================================
    # Unified Tags Route
    # ==========================================================

    # Service registry: all non-None services that expose list_tags(user_id)
    _all_svcs = [
        service,
        app_service,
        acc_service,
        note_service,
        contact_service,
        comm_service,
    ]
    _tag_registry = [svc for svc in _all_svcs if svc is not None]

    @api.get("/api/tags")
    def list_all_tags(
        current_user: UserContext = Depends(_user_dep),
    ) -> list[str]:
        all_tags: set[str] = set()
        for svc in _tag_registry:
            all_tags.update(svc.list_tags(user_id=current_user.id))
        return sorted(all_tags)

    # ==========================================================
    # Global Search Route
    # ==========================================================

    _search_service = SearchService(
        resume_service=service,
        app_service=app_service,
        acc_service=acc_service,
        note_service=note_service,
        contact_service=contact_service,
        comm_service=comm_service,
    )

    @api.get("/api/search")
    def global_search(
        q: str | None = None,
        tag: list[str] | None = Query(default=None),
        type: list[str] | None = Query(default=None, alias="type"),
        current_user: UserContext = Depends(_user_dep),
    ) -> list[dict[str, Any]]:
        results = _search_service.search(
            q=q, tags=tag, types=type, user_id=current_user.id
        )
        return [r.model_dump() for r in results]

    # ==========================================================
    # Data Export Route
    # ==========================================================

    _export_service = ExportService(
        resume_service=service,
        app_service=app_service,
        acc_service=acc_service,
        note_service=note_service,
        contact_service=contact_service,
        comm_service=comm_service,
        link_service=link_service,
    )

    @api.get("/api/export")
    def export_my_data(
        current_user: UserContext = Depends(_user_dep),
    ) -> JSONResponse:
        """Return every resource owned by the caller as one JSON document."""
        data = _export_service.export_user_data(user_id=current_user.id)
        filename = f"pktx-export-{data['exported_at'][:10]}.json"
        return JSONResponse(
            content=jsonable_encoder(data),
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # ==========================================================
    # Unknown /api paths → JSON 404 (MUST be registered last on ``api``)
    # ==========================================================

    @api.api_route(
        "/api/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    def api_not_found(path: str) -> None:
        """Stop unknown API paths falling through to the SPA's index.html."""
        raise HTTPException(status_code=404, detail="Not found")

    # ==========================================================
    # Webhook Routes (no auth — verified via Svix signature)
    # ==========================================================

    @router.post("/api/webhooks/clerk")
    async def clerk_webhook(request: Request) -> dict[str, str]:
        """Handle Clerk lifecycle webhooks (user.deleted, etc.)."""
        # The service's connection: a RequestConnection in production (this
        # request's pooled connection + transaction), a raw one in tests.
        return await _handle_clerk_webhook(request, service._conn)

    # Include protected sub-router
    router.include_router(api)
    return router


async def _handle_clerk_webhook(request: Request, conn: Any) -> dict[str, str]:
    """Verify Svix signature and process Clerk webhook events."""
    import asyncio
    import json
    import os

    from svix.webhooks import Webhook, WebhookVerificationError

    from pktx.database import delete_user

    webhook_secret = os.environ.get("CLERK_WEBHOOK_SECRET", "")
    if not webhook_secret:
        raise HTTPException(
            status_code=500, detail="CLERK_WEBHOOK_SECRET is not configured"
        )

    payload = await request.body()
    headers = dict(request.headers)

    try:
        wh = Webhook(webhook_secret)
        event = wh.verify(payload, headers)
    except WebhookVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    if isinstance(event, (str, bytes)):
        event = json.loads(event)

    event_type = event.get("type", "")
    if event_type == "user.deleted":
        user_id = event.get("data", {}).get("id")
        if user_id:
            # Blocking DB call: run it off the event loop. to_thread copies the
            # context, so the request's connection scope is visible.
            await asyncio.to_thread(delete_user, conn, user_id)

    return {"status": "ok"}
