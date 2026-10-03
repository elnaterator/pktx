"""SearchService — cross-resource global search."""

from typing import Any

from pktx.models import SearchResult

_SNIPPET_MAX = 160


def _trunc(text: str | None) -> str | None:
    if not text:
        return None
    text = text.strip()
    if len(text) <= _SNIPPET_MAX:
        return text
    return text[:_SNIPPET_MAX].rstrip() + "…"


def _map_resume(row: dict[str, Any]) -> SearchResult:
    return SearchResult(
        type="resume",
        id=row["id"],
        title=row["label"],
        subtitle="Resume",
        tags=row.get("tags", []),
        url=f"/resumes/{row['id']}",
    )


def _map_application(row: dict[str, Any]) -> SearchResult:
    title = f"{row['position']} @ {row['company']}"
    return SearchResult(
        type="application",
        id=row["id"],
        title=title,
        subtitle=row.get("status"),
        tags=row.get("tags", []),
        url=f"/applications/{row['id']}",
    )


def _map_accomplishment(row: dict[str, Any]) -> SearchResult:
    return SearchResult(
        type="accomplishment",
        id=row["id"],
        title=row["title"],
        snippet=_trunc(row.get("result")),
        tags=row.get("tags", []),
        url=f"/accomplishments/{row['id']}",
    )


def _map_note(row: dict[str, Any]) -> SearchResult:
    return SearchResult(
        type="note",
        id=row["id"],
        title=row["title"],
        snippet=_trunc(row.get("content")),
        tags=row.get("tags", []),
        url=f"/notes/{row['id']}",
    )


def _map_contact(row: dict[str, Any]) -> SearchResult:
    parts = [p for p in [row.get("title"), row.get("company")] if p]
    subtitle = " · ".join(parts) if parts else None
    return SearchResult(
        type="contact",
        id=row["id"],
        title=row["name"],
        subtitle=subtitle,
        tags=row.get("tags", []),
        url=f"/contacts/{row['id']}",
    )


def _map_communication(row: dict[str, Any]) -> SearchResult:
    return SearchResult(
        type="communication",
        id=row["id"],
        title=row.get("subject") or "(no subject)",
        subtitle=row.get("parent_name"),
        snippet=_trunc(row.get("body")),
        tags=row.get("tags", []),
        url=f"/contacts/{row['contact_ref_id']}",
    )


_PER_TYPE_CAP = 50


class SearchService:
    """Fan-out cross-resource search over existing service methods."""

    def __init__(
        self,
        resume_service: Any,
        app_service: Any | None = None,
        acc_service: Any | None = None,
        note_service: Any | None = None,
        contact_service: Any | None = None,
        comm_service: Any | None = None,
    ) -> None:
        self._resume_svc = resume_service
        self._app_svc = app_service
        self._acc_svc = acc_service
        self._note_svc = note_service
        self._contact_svc = contact_service
        self._comm_svc = comm_service

    def search(
        self,
        q: str | None,
        tags: list[str] | None,
        types: list[str] | None,
        user_id: str,
    ) -> list[SearchResult]:
        if not q and not tags:
            return []

        wanted = set(types) if types else None
        results: list[SearchResult] = []

        def _want(t: str) -> bool:
            return wanted is None or t in wanted

        if _want("resume"):
            for row in self._resume_svc.list_resumes(user_id=user_id, tags=tags, q=q)[
                :_PER_TYPE_CAP
            ]:
                results.append(_map_resume(row))

        if _want("application") and self._app_svc is not None:
            for row in self._app_svc.list_applications(tags=tags, q=q, user_id=user_id)[
                :_PER_TYPE_CAP
            ]:
                results.append(_map_application(row))

        if _want("accomplishment") and self._acc_svc is not None:
            for row in self._acc_svc.list_accomplishments(
                tags=tags, q=q, user_id=user_id
            )[:_PER_TYPE_CAP]:
                results.append(_map_accomplishment(row))

        if _want("note") and self._note_svc is not None:
            for row in self._note_svc.list_notes(tags=tags, q=q, user_id=user_id)[
                :_PER_TYPE_CAP
            ]:
                results.append(_map_note(row))

        if _want("contact") and self._contact_svc is not None:
            for row in self._contact_svc.list_contacts(tags=tags, q=q, user_id=user_id)[
                :_PER_TYPE_CAP
            ]:
                results.append(_map_contact(row))

        if _want("communication") and self._comm_svc is not None:
            for row in self._comm_svc.search(q=q, tags=tags, user_id=user_id)[
                :_PER_TYPE_CAP
            ]:
                results.append(_map_communication(row))

        return results
