---
roadmap_id: 033
issue: n/a
---

# Plan: 033 Complete the resume: projects, certifications, more sections, and a section registry

Branch: `feat/033-resume-section-registry`. Research: `research/resume-sections.md`.

## Overview

Resume has contact, summary, experience, education, skills. Section names are repeated in `resume_service.py` tuples, `resume_tools.py`, `api/routes.py`, and one hand-written frontend component each. Entries are index-addressed; no per-version order/visibility.

Two phases in one branch (refactor justified by real sections; split only if phase 1 alone exceeds review size):

1. **Registry + stable ids + layout** (behavior-preserving for existing data).
2. **New sections** as registry entries: projects, certifications, awards, publications/talks, volunteer, languages, profiles, custom.

## Acceptance criteria

- [x] Backend `resume_sections.py` registry: one definition per section (key, label, kind singleton|list, pydantic model, summary formatter, sort/insert rule, uniqueness rule). Service, MCP tools, REST routes, export, and `Resume` model derive from it; no other section tuples remain.
- [x] Every list entry has a stable `id` (uuid4 hex). Existing blobs get ids lazily on read and are persisted via a schema migration (v14 → v15); no entry loses data.
- [x] Entries addressable by `entry_id` in service, REST (`/entries/{entry_id}`) and MCP tools. Index addressing still accepted (compat shim: numeric string/int resolves to index).
- [x] Per-version `layout`: ordered list of `{section, visible, title?}`. Default = current order, all visible, for existing resumes. Endpoint + MCP tool to update layout; new versions copy layout from default.
- [x] New sections work end to end (service, REST, MCP, UI, export): projects, certifications, awards, publications, volunteer, languages, custom (title + entries with free-form text/bullets); contact gains generic `profiles` list (label + http(s) URL); existing linkedin/website/github fields untouched.
- [x] URLs in new entries pass `validate_http_url`; length limits enforced; tags unaffected.
- [x] Frontend: generic registry-driven list section renders/edits any list section; experience/education migrated to it; skills keep bespoke grouped UI; resume detail renders sections in layout order with hide/show, reorder (up/down buttons, keyboard accessible), and title override; hidden sections still editable via a "Manage sections" panel.
- [x] Section metadata served by `GET /api/resume-sections` so frontend does not duplicate field definitions.
- [x] `tests/integration/test_route_scoping.py` covers every new route; `make check` passes.
- [x] Existing resume tests pass unchanged (index addressing, blobs without ids/layout).

## Open questions

- [x] MCP: generic `add_resume_entry(section=...)` stays, no per-section tools — _proposed: generic, plus new `update_resume_layout`; docstrings generated from the registry_
- [x] Ids: migrate in schema migration or on read? — _proposed: both; migration backfills, read path tolerates missing ids (defensive)_
- [x] Dates stay free-form strings — _proposed: yes, out of scope; validation later_
- [x] Custom section count — _proposed: multiple allowed, keyed `custom:<id>` in layout, each with own title_
- [x] Reorder UX — _proposed: up/down buttons (no drag-and-drop dependency)_

## Design

**Registry (backend).** `SectionDef(key, label, kind, model, summary(entry)->str, insert='prepend'|'append', unique_key=None, fields=[FieldDef])`. `FieldDef` (name, label, type text|textarea|url|bullets|select, required) is derived from pydantic model fields plus json_schema_extra for labels/widgets, so the UI descriptor is generated, not hand-maintained. `Resume` model fields for list sections are produced from the registry (`create_model`) or validated against it; unknown sections in stored blobs are preserved.

**Entry ids.** Base `Entry` model with `id: str = Field(default_factory=uuid4 hex)`. Service ops: `add_entry`, `update_entry(entry_id)`, `remove_entry(entry_id)`, plus `resolve_entry(section, ref)` that accepts id or legacy index.

**Layout.** Stored in blob as `layout: [{section, visible, title}]`. `normalize_layout` appends missing registry sections (so adding sections later is backward compatible) and drops unknown keys. Singletons contact/summary are layout members too (contact pinned first, not hideable — header).

**Custom section.** Instances stored in `custom_sections: {id: {title, entries:[{id, heading?, body?, highlights[]}]}}`; layout key `custom:<id>`. Add/remove custom section via layout tool.

**Frontend.** `types/resume.ts` extended; `hooks/queries` gain `useResumeSections()`; `pages/resumes/GenericListSection.tsx` (uses `EditableSection`/`EntryForm`), `ManageSections.tsx`. `SkillsSection` unchanged except plumbing. Per-section files for experience/education removed once migrated.

**Touches:**
- `backend/src/pktx/resume_sections.py` (new)
- `backend/src/pktx/models.py` (mod: Entry base, new models, Resume, layout)
- `backend/src/pktx/resume_service.py` (mod)
- `backend/src/pktx/tools/resume_tools.py` (mod)
- `backend/src/pktx/api/routes.py` (mod; entry_id routes, layout, sections metadata)
- `backend/src/pktx/migrations.py` (mod: v15 backfill ids + layout)
- `backend/src/pktx/export_service.py` (mod only if it filters sections)
- `backend/tests/{unit,contract,integration}/…` (new/mod)
- `frontend/src/types/resume.ts`, `services/api/resumes.ts`, `hooks/queries/*`, `schemas/resume.ts` (mod)
- `frontend/src/pages/resumes/*` (new generic + manage; del Experience/Education sections)
- `frontend/src/__tests__/…` (mod/new)
- `AGENTS.md` (mod: schema v15, registry note)

## Steps

Phase 1 — refactor
- [x] Add `Entry` id base + `resume_sections.py` registry for existing 3 list sections + 2 singletons
- [x] Rewrite service ops over registry; id + legacy-index resolution; keep error messages compatible
- [x] Layout model, `normalize_layout`, service `get/update_layout`; copy on create_resume
- [x] Migration v14 → v15 (ids + layout), idempotent; migration test
- [x] REST: entry_id routes, layout route, `/api/resume-sections`; register in route-scoping test
- [x] MCP tools driven by registry (docstrings, section enums, entry_id param, layout tool)
- [x] Frontend: types, api, `GenericListSection`, migrate experience/education, layout-ordered render, ManageSections
- [x] Run `make check`; green before phase 2

Phase 2 — new sections
- [x] Models + registry entries: projects, certifications, awards, publications, volunteer, languages
- [x] Contact `profiles` list (service + UI in ContactSection)
- [x] Custom sections (data shape, layout key, add/remove, UI)
- [x] Tests for each (validation, URLs, limits, scoping, export contains them)
- [x] Frontend tests; update AGENTS.md; `make check`

## Testing

```bash
make check
cd backend && uv run pytest tests -k resume
cd frontend && npm run test
```

Manual: open an existing resume (no ids/layout) — unchanged; add project/cert; hide + reorder sections; MCP `add_resume_entry` + `update_resume_layout` against local server.

## Out of scope

Date validation/parsing, resume print/PDF templates, drag-and-drop reorder, interests/references sections, per-application layout overrides, company URL on experience.
