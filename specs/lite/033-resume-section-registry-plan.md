---
roadmap_id: 033
issue: n/a
---

# Plan: 033 Complete the resume: projects, certifications, more sections, and a section registry

Branch: `feat/033-resume-section-registry`. Research: `research/resume-sections.md`.

## Overview

Resume had contact, summary, experience, education, skills. Section names were repeated in the service, MCP tools, routes and one hand-written frontend component each, and entries were index-addressed.

Two phases in one branch (refactor justified by real sections):

1. **Registry + stable ids** (behavior-preserving for existing data).
2. **New sections** as registry entries: projects, certifications, awards, publications/talks, volunteer, languages, plus contact `profiles`.

**Scope decision:** the UI stays simple. Fixed, opinionated section order; no reordering, hiding, renaming or free-form custom sections. Experience, education and skills are always shown; the six new sections are optional and added from a fixed list. (An earlier draft had a per-version layout and custom sections; dropped after review as too complex.)

## Acceptance criteria

- [x] Backend `resume_sections.py` registry: one definition per list section (key, label, model, summary formatter, insert rule, uniqueness rule, primary field). Service, MCP tools, REST routes, export and the `Resume` model derive from it; import-time checks fail if registry, `Resume` fields and `resume_order.LIST_ORDER` drift.
- [x] Every list entry has a stable `id` (uuid4 hex). Schema migration v14 → v15 backfills ids idempotently; no entry loses data. Entries without an id (unmigrated) still work by index.
- [x] Entries addressable by `entry_id` in service, REST (`/entries/{entry_ref}`) and MCP tools; legacy 0-based index still accepted; clients cannot overwrite an id.
- [x] Fixed section order (`resume_order.LIST_ORDER`). `CORE` sections (experience, education, skills) always shown; `OPTIONAL` sections shown when added or when they have entries (`Resume.enabled_sections`, normalized to fixed order).
- [x] `set_section_enabled`: add an optional section; remove only while empty; core and unknown sections rejected. Exposed as `PUT /api/resumes/{id}/sections/{section}` and MCP `set_resume_section_enabled`. New versions copy enabled sections from the default.
- [x] New sections work end to end (service, REST, MCP, UI, export): projects, certifications, awards, publications, volunteer, languages; contact gains a generic `profiles` list (label + http(s) URL). Existing linkedin/website/github untouched.
- [x] URLs in new entries pass `validate_http_url`; length limits enforced (long limit for `description`/`body`).
- [x] Frontend: registry-driven `GenericListSection` renders/edits any list section (experience/education migrated, skills keep bespoke grouped UI); `AddSectionBar` lists optional sections not yet added; empty optional sections have "Remove section".
- [x] Section metadata served by `GET /api/resume-sections` (includes `optional`) so the frontend duplicates no field definitions.
- [x] `tests/integration/test_route_scoping.py` covers every new route; `make check` passes.
- [x] Existing resume tests pass unchanged (index addressing, blobs without ids/enabled sections).

## Open questions

Resolved:

- MCP: generic `add_resume_entry(section=...)` stays, no per-section tools; one new `set_resume_section_enabled`.
- Ids: migrated in schema migration v15; read path tolerates missing ids via index fallback.
- Dates stay free-form strings.
- Reorder / hide / rename / custom sections: dropped (see scope decision).

Open:

- [ ] Hide a section that has entries without deleting them? — _proposed: no; delete entries first (keeps "has entries ⇒ shown" simple)_

## Design

**Registry (backend).** `SectionDef(key, label, model, summary, insert, unique_field, primary_field)` per list section. Field descriptors for the UI are derived from the pydantic model (`fields_for`): widget from field name (`highlights` → bullets, `tech` → tags, `url` → url, `description`/`body` → textarea), `required` from the model. `describe_sections()` adds `optional` (not in `CORE`).

**Order and enabled sections.** `resume_order.py` (no model imports, so `Resume` can use it): `LIST_ORDER`, `CORE`, `OPTIONAL`, `normalize_enabled(enabled, data)` = optional keys that are enabled or have entries, in fixed order. `Resume` normalizes `enabled_sections` in a validator.

**Entry ids.** `Entry` base model with `id: str | None`; the service assigns `uuid4().hex` on add. `_resolve(entries, section, ref)` accepts an id or a legacy index.

**Frontend.** `GenericListSection` (view/add/edit/delete from the registry; zod schema built from field descriptors in `buildEntrySchema`), `AddSectionBar`, `ResumeDetailView` renders Summary then registry sections in order (optional ones only when enabled). `ContactSection` gains a profiles editor.

**Touches:**
- `backend/src/pktx/resume_sections.py` (new), `resume_order.py` (new)
- `backend/src/pktx/models.py`, `resume_service.py`, `tools/resume_tools.py`, `api/routes.py`, `migrations.py` (mod)
- `backend/tests/{unit,contract,integration}/…` (new/mod)
- `frontend/src/types/resume.ts`, `services/api/resumes.ts`, `hooks/queries/resumes.ts`, `schemas/{resumeEntry,httpUrl}.ts` (mod)
- `frontend/src/pages/resumes/GenericListSection.*`, `AddSectionBar.*` (new); `ResumeDetailView.tsx`, `ContactSection.tsx`, `SkillsSection.tsx` (mod); `ExperienceSection.*`, `EducationSection.*`, `ResumeView.*` (del; `ResumeView` was unused legacy)
- `frontend/src/__tests__/…` (new/mod)
- `AGENTS.md` (mod)

## Steps

Phase 1 — refactor
- [x] `Entry` id base + `resume_sections.py` registry for the existing list sections
- [x] Rewrite service ops over the registry; id + legacy-index resolution; keep error messages compatible
- [x] Fixed order + optional-section handling (`resume_order.py`, `enabled_sections`, `set_section_enabled`)
- [x] Migration v14 → v15 (ids), idempotent; migration test
- [x] REST: entry_ref routes, section enable route, `/api/resume-sections`; register in route-scoping test
- [x] MCP tools driven by the registry (docstrings, entry_id param, `set_resume_section_enabled`)
- [x] Frontend: types, api, `GenericListSection`, migrate experience/education, ordered render, `AddSectionBar`

Phase 2 — new sections
- [x] Models + registry entries: projects, certifications, awards, publications, volunteer, languages
- [x] Contact `profiles` (service + UI)
- [x] Tests for each (validation, URLs, limits, scoping, export contains them)
- [x] Frontend tests; update AGENTS.md; `make check`

## Testing

```bash
make check
cd backend && uv run pytest tests -k resume
cd frontend && npm run test
```

Manual: open an existing resume (no ids/enabled sections) — unchanged; add a Projects section and an entry; remove an empty optional section; MCP `add_resume_entry` + `set_resume_section_enabled` against the local server.

## Out of scope

Reordering / hiding / renaming sections, free-form custom sections, date validation or parsing, resume print/PDF templates, interests/references sections, company URL on experience.
