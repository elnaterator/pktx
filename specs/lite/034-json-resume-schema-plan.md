---
roadmap_id: 034
issue: n/a
branch: refactor/034-json-resume-schema
---

# Plan: 034 Simplify the resume schema: adopt JSON Resume

Research: [research/resume-schema.md](../../research/resume-schema.md)

## Overview

033 left 9 bespoke entry schemas (title/role/name, company/organization/institution/issuer/venue,
start_date/issued/date), an over-built contact model (preset keys, value kinds, presets endpoint,
legacy shortcuts), stored `enabled_sections` duplicating "has entries", and dual id/index entry
addressing. Make JSON Resume (jsonresume.org schema v1.0.0) the canonical shape. LLMs already write
it, import/export is free, naming stops being a design decision.

In scope:

- **JSON Resume nomenclature everywhere outside Python**: section keys, field names and camelCase
  (`startDate`, `studyType`, `releaseDate`) in the DB document, REST, MCP, export and frontend
  types. Python attributes stay snake_case via `alias_generator=to_camel` + `populate_by_name=True`;
  every dump is `by_alias=True`. Input accepts both cases. **Full spec, nothing else**: every JSON Resume section and field is
  modeled (incl. `interests`, `references`, `meta`); no non-spec fields. Only extension: a stable
  `id` on every entry and profile. Unknown keys on import are ignored.
- **Storage**: one JSON Resume document per version in `resume_version.resume_data`, column moved
  `TEXT` → `JSONB` (see Storage).
- `basics` = `{name, label, image, email, phone, url, summary, location, profiles[]}` replaces
  `contact` + `summary`; `location` is the spec object.
- Skills → groups `{id, name, level, keywords[]}`.
- Partial ISO dates (`YYYY`, `YYYY-MM`, `YYYY-MM-DD`) validated, else 422. Missing `endDate` = present.
- **Standard resource shape** (see API and MCP): resume = envelope (`id, label, tags, is_default,
  timestamps`, snake_case like every other resource) + `data` (the JSON Resume document, verbatim).
  Plain CRUD on the resume; sub-paths under `data/` mirror the document. MCP 12 → 10 tools.
- Entry reorder (`PUT .../data/{section}/order`, `reorder_resume_entries`) and optional `position`
  on add.
- Import = `data` on create/update (whole JSON Resume, validated, replaces the document).
- Write tools/routes return the changed object; MCP resume tools raise on error (no `"Error: ..."`
  strings) so the transaction rolls back. Fixing the other resources is 035.
- Entry schemas typed from Pydantic models in MCP; `GET /api/resumes/schema` derived from `model_json_schema()`.
- One migration v16 → v17 (data reshape + column type); delete every legacy path (no shims).
- **Resume page UI** (added during the build, deliberately kept in this item rather than split out;
  details in Amendments 1-3): a JSON view/editor tab; a visual pass (Profiles header, in-page date
  calendar, Add buttons in section headers, add forms opening at the top, skills wording that follows
  JSON Resume: skill = `name`, keyword = `keywords[]`); drag-and-drop reordering via a shared
  `SortableList` (new dependency `@dnd-kit`, justified under constitution IV). Small supporting
  changes ride with them: the `courses` line on education, keyword writes queued so typing keeps
  focus, and the skill-draft hint wording.

Removed: `enabled_sections`, `PUT /api/resumes/{id}/sections/{section}`, `set_resume_section_enabled`,
422 non-empty-disable rule, `contact_keys.py`, `GET /api/resume-contact-keys`,
`ContactInfo.upgrade_legacy`, legacy contact inputs, index addressing, registry `insert` /
`unique_field`, `resume_order.py`, `GET /api/resumes/default`, `POST /api/resumes/{id}/default`,
`GET /api/resumes/{id}/{section}`, `PUT .../contact`, `PUT .../summary`, `GET /api/resume-sections`,
MCP `get_resume_section`, `update_resume_metadata`, `set_default_resume`, `update_resume_section`.

## API and MCP

Rule: envelope fields snake_case (matches notes, contacts, applications); `data` is JSON Resume
camelCase verbatim. Paths under `data/` follow the document, so no section key can collide with
`default`/`tags`.

**REST** (13 routes):

```
GET    /api/resumes                                     summaries (incl. is_default)
POST   /api/resumes                {label, tags?, data?}  no data → copy of default
GET    /api/resumes/tags
GET    /api/resumes/schema         Resume JSON Schema + section labels + widget hints
GET    /api/resumes/{id}           {id, label, tags, is_default, created_at, updated_at, data}
PATCH  /api/resumes/{id}           {label?, tags?, is_default?}
DELETE /api/resumes/{id}           409 if last version

PUT    /api/resumes/{id}/data                           replace whole document (import) → resume
PATCH  /api/resumes/{id}/data/basics                    partial → basics
POST   /api/resumes/{id}/data/{section}?position=N  body = the entry → entry (with id)
PATCH  /api/resumes/{id}/data/{section}/{entryId}       partial → entry
DELETE /api/resumes/{id}/data/{section}/{entryId}       204
PUT    /api/resumes/{id}/data/{section}/order {ids}     exact permutation → section list
```

`is_default: false` on the current default → 422 (set another instead). `position` = 0-based
insert index, default end.

**MCP** (10 tools, CRUD names like other resources; sub-entry verbs like
`add_contact_communication`):

```
list_resumes()
get_resume(id?, section?)                              default when id omitted; section → {id, section, data}
create_resume(label, tags?, data?)                     data = JSON Resume → import on create
update_resume(id, label?, tags?, is_default?, data?)   data replaces whole document
delete_resume(id)
update_resume_basics(id, basics)                       partial
add_resume_entry(id, section, entry, position?)        → entry with id
update_resume_entry(id, section, entry_id, entry)      partial → entry
remove_resume_entry(id, section, entry_id)             → removed entry
reorder_resume_entries(id, section, entry_ids)         → section list
```

Every tool returns structured JSON (the resume, entry or list), never a prose string. Errors raise
(`ToolError`), so `DBSessionToolMiddleware` rolls back. `entry` is typed per section (union of the
section models) so clients see real JSON Schema.

Rejected: per-section tools (`add_work_entry`, …: 27+ tools); a single JSON Patch tool (LLMs write
it poorly, partial-update tools cover it).

## Storage

Keep one document per version (no per-section tables): a resume is always read and written whole by
its single owner, versions are full copies, and the document is JSON Resume itself so import/export
is a pass-through. Neon is stock Postgres, so `JSONB` is fully supported.

- v17 migration: `ALTER TABLE resume_version ALTER COLUMN resume_data DROP DEFAULT`,
  `ALTER COLUMN resume_data TYPE jsonb USING resume_data::jsonb`,
  `ALTER COLUMN resume_data SET DEFAULT '{}'::jsonb`, then the per-row reshape.
- `database.py`: write with `psycopg.types.json.Jsonb(data)`, read the dict straight from the row
  (drop `json.dumps`/`json.loads` for this column). Any SQL text search over `resume_data` switches
  to `resume_data::text`.
- No indexes: access is by `id` + `user_id`. Add GIN only if cross-entry SQL search appears.
- Stored document is camelCase JSON Resume + `id`s, identical to the export body.

## Field mapping (old → JSON Resume)

| Section (old key → new) | Fields: new (old) |
|---|---|
| `contact` + `summary` → `basics` | `name`, `email` (`Email` field), `phone`, `url` (`Website` field), `summary` (top-level `summary`), `location` `{address, postalCode, city, countryCode, region}` (old string split on last comma → `city`, `region`; no comma → `city`), `profiles[]` `{id, network, username, url}` (`LinkedIn`/`GitHub`/other URL fields: `network` = key), `label` (new, headline), `image` (new) |
| `experience` → `work` | `name` (company), `position` (title), `location`, `startDate`, `endDate`, `highlights[]`, `url`, `summary`, `description` (new) |
| `education` | `institution`, `studyType` (degree), `area` (field), `startDate`, `endDate`, `url`, `score`, `courses[]` (new) |
| `skills` | one group per old `category`: `name` (category), `keywords[]` (skill names, original order), `level` (new) |
| `projects` | `name`, `description`, `url`, `keywords[]` (tech), `startDate`, `endDate`, `highlights[]`, `roles[]`, `entity`, `type` (new) |
| `certifications` → `certificates` | `name`, `issuer`, `date` (issued), `url` |
| `awards` | `title`, `awarder` (issuer), `date`, `summary` (description) |
| `publications` | `name` (title), `publisher` (venue), `releaseDate` (date), `url`, `summary` (description) |
| `volunteer` | `organization`, `position` (role), `startDate`, `endDate`, `highlights[]`, `url`, `summary` (new) |
| `languages` | `language`, `fluency` (proficiency) |
| `interests` (new) | `name`, `keywords[]` |
| `references` (new) | `name`, `reference` |
| `meta` (new, not a list) | `canonical`, `version`, `lastModified`: stored and passed through on import/export, not shown in the UI |

UI labels stay human ("Experience", "Certifications & Licenses"); keys are spec keys. Display
order: work, education, skills, projects, certificates, awards, publications, volunteer, languages,
interests, references.

**Dropped by the migration** (no clean spec equivalent): `education.honors`, `education.highlights`,
`certifications.expires`, `certifications.credential_id`, `volunteer.location`, contact custom
text keys (e.g. "Pronouns"), and any second email or website. URL-valued contact keys (LinkedIn,
GitHub, ...) map cleanly to `profiles[]` and are kept.

**Dates:** existing data holds free text, e.g. `03/2011` and `Present`, which are not partial ISO.
The migration normalizes: `YYYY`, `YYYY-MM`, `YYYY-MM-DD` kept; `MM/YYYY`, `M/YYYY` → `YYYY-MM`;
`Mon YYYY` / `Month YYYY` → `YYYY-MM`; `Present`/`Current`/`Now` (any case) → field omitted.
Anything else: date dropped and a warning logged with the version id.

## Acceptance criteria

- [x] `resume_data` column is `jsonb` after migration; `database.py` passes `Jsonb(...)` and reads dicts without `json.loads`.
- [x] `Resume` model = the full JSON Resume v1.0.0 schema (`basics, work, volunteer, education, awards, certificates, publications, skills, languages, interests, references, projects, meta`) with no non-spec fields + `id` on every entry/profile; no `enabled_sections`, `contact`, `summary`, `experience`, `certifications` keys.
- [x] Every REST response, MCP tool result, stored document and export uses JSON Resume camelCase names; input accepts camelCase and snake_case.
- [x] Dates: `2024`, `2024-03`, `2024-03-05` accepted; `March 2024`, `2024-13`, `2024/03` → 422 (REST) / tool error (MCP). Missing `endDate` renders "Present".
- [x] `basics.email` validated as email; `basics.url`, `basics.image`, `profiles[].url`, every entry `url` http(s)-only via `validate_http_url`.
- [x] Migration v16 → v17 converts every row; unit tests on the pure converter: a full fixture (every section, contact custom keys, skill categories, dropped fields, `MM/YYYY` + `Present` + unparseable dates) asserts exact output; converter is idempotent.
- [x] Importing the jsonresume.org sample resume round-trips: every spec field survives `PUT .../data` → `GET` → export (ids added); a non-spec key is dropped silently.
- [x] REST routes exactly as in API and MCP; every removed route → 404 (or 405).
- [x] Entries addressed by id only; a numeric index → 404.
- [x] `PUT .../data/{section}/order` reorders; ids must be an exact permutation, else 422. `POST .../data/{section}` honors `position`.
- [x] `POST /api/resumes` / `create_resume` and `PUT .../data` / `update_resume(data=...)` accept a whole JSON Resume, assign missing ids, ignore unknown top-level keys, 422 / tool error on invalid.
- [x] `PATCH /api/resumes/{id} {is_default: true}` / `update_resume(is_default=True)` moves the default; `false` on the default → 422.
- [x] Write routes and tools return the changed object (entry ids visible on add).
- [x] `GET /api/export` emits resume documents unchanged (JSON Resume + ids).
- [x] MCP resume tools exactly the 10 listed; `entry` / `basics` / `data` args publish real JSON Schema; no tool returns a prose string; invalid input raises and the write rolls back (test: failed `add_resume_entry` leaves the document unchanged).
- [x] `GET /api/resumes/schema` built from `model_json_schema(by_alias=True)` (+ `json_schema_extra={"widget": ...}`) and section labels.
- [x] Deleted: `contact_keys.py`, `resume_order.py`, `ContactInfo`, `ContactField`, `upgrade_legacy`, `normalize_enabled`, index addressing in service.
- [x] Frontend: `BasicsSection` (replaces Contact + Summary) with profiles list + network suggestions constant; skills as groups; `GenericListSection` renders from schema; section shown iff it has entries, "Add section" opens first-entry form; entries reorder by drag and drop (Amendment 3) and call the order endpoint; dates entered as partial ISO with inline validation.
- [x] `test_route_scoping.py` registers the new routes; removed routes deleted from it.
- [x] `make check` green (root).

## Decisions

- `basics.location` is the spec object; UI edits `city`, `region`, `countryCode`.
- Full spec only: no non-spec fields; fields without a clean equivalent are dropped by the migration (no real data to keep).
- Full spec sections incl. `interests`, `references`, `meta`; unknown keys ignored on import.
- Section keys and field names follow JSON Resume exactly (`work`, `certificates`, camelCase in `data`); storage stays one `JSONB` document per version; import is `data` on create/update (no `import_resume` tool); API/MCP shape per API and MCP.

## Design

**Models (`json_resume.py`, new; `models.py` keeps the other resources).** `JRModel(BaseModel)` with `ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore", field_title_generator=...)` and a before-validator that treats blank strings as absent. Reusable `Annotated` types (`Name`/`Short`/`Long`/`Bullet` length-capped strings, `Url` via `validate_http_url`, `PartialDate`, `Email`). Every spec field optional; `Entry(JRModel)` adds `id`. `dump()` = `model_dump(mode="json", by_alias=True, exclude_defaults=True)` (compact camelCase); `alias_keys()` renames snake_case patch keys and rejects unknown ones; `validate()` raises a one-line `ValueError`. Fields carry `title` (label) and `widget` hints in the JSON Schema.

**Registry (`resume_sections.py`).** `SectionDef(key, label, model, primary_field)`; dict order = display order (`resume_order.py` deleted); `section_data()` reads one part of a document; `describe_sections()` → `{key, label, kind, primaryField, schema}` from `model_json_schema(by_alias=True)`; `entry_fields()` renders field lists for MCP tool descriptions. Import-time check that the registry matches `Resume`.

**Service (`resume_service.py`).** Returns dicts, raises (`ValueError` → 422 / `ToolError`, `NotFound` → 404). Ids only (`_find(entries, entry_id)`). `create_resume(label, tags, data=None)`, `update_resume(id, label, tags, is_default)`, `replace_data(id, data)` (`Resume.model_validate`, assign uuids where missing, dedupe ids), `update_basics`, `add_entry(position=None)`, `update_entry`, `remove_entry`, `reorder_entries(ids)`. Array order = display order.

**MCP (`tools/resume_tools.py`).** The 10 tools above. `section` is a `Literal` enum (checked against the registry at import); `basics` and `data` are typed with the Pydantic models (real JSON Schema); `entry` is `dict[str, Any]` whose description lists each section's fields, generated from the models. A union of the section models was rejected: every field is optional, so a payload validates against several members and would be coerced to the wrong one. Errors raise `ToolError` via `tools/errors.raises_tool_error`.

**Migration v16 → v17 (`migrations.py`).** Pure `_v16_to_v17(data: dict) -> dict` + `_normalize_date(raw) -> str | None` (both unit-tested), column `ALTER` first, then per-row loop writing `Jsonb`. Preserves entry ids; skill groups get fresh ids in first-seen category order; unmapped fields dropped.

**Export (`export_service.py`).** Resume documents pass through as stored.

**Frontend.** `types/resume.ts` rewritten to JSON Resume camelCase; `services/api/resumes.ts` rewritten to the new routes (`updateResume`, `replaceResumeData`, `updateBasics`, `addEntry`, `updateEntry`, `removeEntry`, `reorderEntries`, `getResumeSchema`); callers of `/default` use the list's `is_default`. `BasicsSection` (new) replaces `ContactSection` + `SummarySection`; `SkillsSection` edits groups (name, level, keyword chips) replacing `SkillAdder`; `GenericListSection` reads `schema.properties` + widget; `AddSectionBar` lists sections without entries; `sortEntriesByDate.ts` deleted (array order wins); entries reorder by dragging a grip (`SortableList`, Amendment 3). `NETWORKS` suggestion constant (LinkedIn, GitHub, X, Mastodon, Bluesky, Website).

**Touches:**
- backend: `json_resume.py` (new), `models.py`, `resume_sections.py`, `resume_service.py`, `tools/resume_tools.py`, `tools/errors.py` (new), `api/routes.py`, `migrations.py` (v17), `database.py` (JSONB, `update_resume_version`) (mod); `resume_order.py`, `contact_keys.py` (del)
- backend tests: `unit/test_json_resume.py` (new, replaces `test_models.py`), `unit/test_resume_sections.py`, `unit/test_resume_service.py`, `unit/test_migrations.py` (v17), `unit/test_database.py`, `contract/test_resume_api.py` (new, replaces `test_resume_sections_api.py`), `contract/test_rest_api.py`, `contract/test_export_api.py`, `integration/test_resume_mcp.py` (new, replaces `test_resume_mcp_sections.py`), `integration/test_route_scoping.py`, `integration/test_input_validation.py`, `integration/test_cross_interface.py`, `integration/test_static_serving.py`, `integration/test_security_regressions.py`, `integration/test_mcp_user_scoping.py`, `conftest.py`
- frontend: `types/resume.ts`, `services/api/{resumes,client}.ts`, `hooks/queries/resumes.ts`, `schemas/resumeEntry.ts`, `pages/resumes/{ResumeDetailView,GenericListSection,AddSectionBar,SkillsSection}.tsx`, `pages/resumes/sectionFields.ts` (new), `pages/resumes/BasicsSection.tsx` + css (new); `ContactSection*`, `SummarySection*`, `sortEntriesByDate.ts` (del); tests for each
- docs: `AGENTS.md`

## Steps

Shape → storage → deletions → additions.

- [x] 1. Models: `JRModel`, `PartialDate`, section models, `Basics`/`Location`/`Profile`, `Resume`. Unit tests: aliasing both ways, dates, url/email.
- [x] 2. Migration v16 → v17: column `TEXT` → `JSONB`, `_normalize_date`, `_v16_to_v17`; fixture tests incl. real-world dates (`03/2011`, `Present`).
- [x] 3. `database.py`: `Jsonb` writes, dict reads; adjust any text search on `resume_data`.
- [x] 4. Registry: slim `SectionDef`, schema-derived `describe_sections`; delete `resume_order.py`, `contact_keys.py`.
- [x] 5. Service: return objects + raise; ids only; `create_resume(data?)`, `update_resume(is_default?)`, `replace_data`, `update_basics`, `add_entry(position?)`, `reorder_entries`; drop enabled logic.
- [x] 6. REST: the 13 routes in API and MCP; delete the rest; update `test_route_scoping.py`.
- [x] 7. MCP: the 10 tools, typed args, structured returns, raise on error; delete the other resume tools; trim docstrings.
- [x] 8. Export pass-through.
- [x] 9. `cd backend && make check`.
- [x] 10. Frontend types + API module.
- [x] 11. Frontend UI: `BasicsSection`, skill groups, schema-driven `GenericListSection`, show-iff-entries + add-section flow, reorder buttons, date validation; delete dead components.
- [x] 12. `cd frontend && make check`.
- [x] 13. Docs: `AGENTS.md`.
- [x] 14. Manual: `make run-local` against a DB restored from a prod snapshot (Neon branch); confirm the migration log has no unparseable-date warnings, every section renders, edit/add/reorder/delete work, import a sample jsonresume.org file, export validates against the JSON Resume schema.

## Build notes

Where the build diverged from the plan:

- JSON Resume models live in `json_resume.py`, not `models.py`.
- REST add takes the entry as the body and `?position=` as a query parameter (not `{entry, position}`); unknown sections are 404, not 400.
- `get_resume(section=...)` returns `{id, section, data}`: FastMCP drops an empty list return, so a bare list is unreadable for an empty section.
- MCP `entry` is a described `dict`, not a union (see Design).
- The v17 migration also sorts period sections (`work`, `education`, `projects`, `volunteer`) newest-first: the old UI sorted them on display and array order is now the display order. Found by running the real chain (v12 → v17) on a copy of the real resume.
- `SkillsSection` serialises keyword writes through a `written` ref: a write replaces the whole `keywords` list, so two writes before the refetch lands must build on each other.
- Step 14 was run against a throwaway Postgres seeded with the real (pre-033) resume at v12, the app served through a stubbed Clerk, and driven in the browser (add section, date validation, reorder, basics + profile edit). Not run against a Neon snapshot.

## Amendments (UI work, in scope)

The three amendments below were added after the first build. They are part of this item, not scope creep: they were requested while the new resume model was being exercised in the UI, and are kept here so the resume page ships coherent with the new data shape.

## Amendment 1: JSON view

Added after the first build: see and edit a resume as raw JSON Resume.

- **What:** the resume detail page gets a `Resume | JSON` tab switch. The JSON tab is one view for reading and editing: the whole document, pretty-printed (ids included), in an editable monospace textarea. **Save** sits top right of the view and replaces the document (`PUT /api/resumes/{id}/data`, the same call as import). No new backend: the route already validates, assigns missing ids and ignores unknown keys.
- **Behavior:**
  - Save is disabled until the text differs from the saved document, and while the text is not valid JSON or not an object (message shown under the editor, border turns red).
  - A rejected save (422) keeps the text and toasts the server message, e.g. `work.0.startDate: Date must be YYYY, YYYY-MM or YYYY-MM-DD`.
  - **Revert** (shown only when edited) discards the draft. The draft lives in `ResumeDetailView` state, so switching to the Resume tab and back keeps it; the JSON tab shows a `•` while a draft is unsaved. A successful save clears the draft and reformats from the server's copy.
- **Acceptance criteria**
  - [x] `JSON` tab shows the saved document as formatted JSON, ids included; `Resume` tab is unchanged.
  - [x] Save (top right) calls `PUT /api/resumes/{id}/data` with the parsed text and toasts on success.
  - [x] Invalid JSON, or JSON that is not an object, cannot be saved and says why; a server 422 keeps the text and shows the message.
  - [x] Unsaved text survives switching tabs; Revert restores the saved document.
- **Touches:** `pages/resumes/ResumeJsonView.tsx` + css (new), `pages/resumes/ResumeDetailView.tsx` + css (tab switch, draft state), `hooks/queries/resumes.ts` (`replaceData` mutation); tests `ResumeJsonView.test.tsx` (new), `ResumeDetailView.test.tsx`.
- **Out of scope:** syntax highlighting / a code editor library, JSON Schema validation in the browser (the server is the validator), copy/download buttons, diffing against the saved copy.

## Amendment 2: resume page visual pass

- **Profiles header:** the basics section labels the profile links (LinkedIn, GitHub, ...) with a `Profiles` heading, in view mode (only when there are profiles) and in the editor, where `+ Add profile` sits at the heading's right.
- **Date pickers:** every date field (`widget: date`) uses a new `DateInput`: a text input that still takes typed `YYYY`, `YYYY-MM` or `YYYY-MM-DD`, plus a calendar button that opens an in-page popover: year stepper (typeable), month grid, `Year only` and `Clear`. Single dates (awarded, issued, released) go on to a day grid; start/end dates stop at the month. It is our own calendar, not the browser's native `<input type=month>` picker, which first shipped and did not work reliably (no picker in some browsers, and `showPicker()` is unavailable or blocked in others). Validation is unchanged.
- **Add buttons top right:** `Add Experience`, `Add Education`, `+ Add Skill`, etc. moved from the bottom of each section to its header's right (new shared `SectionHeader`); `Remove section` for an empty section sits beside it. The buttons hide while a form is open. Adding a whole new section stays in the bar at the bottom.
- **Forms open at the top:** the add form of a list section opens directly under the section header, beside the button that opened it (above the entries and the empty placeholder), and a new skill and a new profile row are added at the top of their lists. Saved placement is unchanged: period sections still insert first, others append.
- **Skills wording follows JSON Resume:** what the UI called a category is a skill (its `name`), and what it called a skill is a keyword. Buttons, placeholders, aria labels and toasts say so (`+ Add Skill`, `add keyword…`, `Add keyword to Languages`, `New skill name`). The migration notes above still say "category" because they describe the old v16 data.
- **Touches:** `components/DateInput.tsx` + css (new), `components/EntryForm.tsx` (`date` field type), `pages/resumes/SectionHeader.tsx` + css (new), `GenericListSection`, `SkillsSection`, `BasicsSection` (+ css); tests for each.
- **Acceptance criteria**
  - [x] A `Profiles` heading labels the profile links in view and edit mode; no heading without profiles in view mode.
  - [x] Every date field has a calendar button; a picked date lands in the field in partial ISO form and saves; single dates can pick a day.
  - [x] Add forms (list sections, skill, profile) appear at the top of their section, next to the Add button.
  - [x] Add buttons are in the section header (top right) for list sections and skills; hidden while editing.

## Amendment 3: drag and drop reordering

Replaces the up/down arrow buttons.

- **Shared component:** `components/SortableList` takes `items`, `getId`, `getLabel`, `onReorder(ids, {from, to})` and a `renderItem(item, row)` render prop (`row` gives the row's `setNodeRef`/`style` and the drag `handle`); `layout` is `vertical` (default) or `grid`. It owns the drag behavior only: what a row looks like and what a drop saves are the caller's. After a drop it shows the new order at once and snaps back if `onReorder` rejects. No grip is shown for a single item.
- **Used for:**
  - every list section of the resume (experience, education, projects, certifications, awards, publications, volunteer, languages, interests, references): saves through `PUT .../data/{section}/order`;
  - skills (a grid): same endpoint;
  - profiles and highlights inside their edit forms: reorders the form's own rows, saved with the form.
  - Not done: keywords inside a skill (chips in a wrapping row), left alone for now.
- **Input:** drag by the grip with a mouse or finger (6px of travel before a drag starts, so clicks still click), or from the keyboard: focus the grip, Space to pick up, arrows to move, Space to drop, Esc to cancel. Screen readers get announcements that name the item ("Dropped Senior Engineer at position 2 of 3").
- **Dependency (constitution IV):** `@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities` (MIT, React-only, no further runtime dependencies). Justified because native HTML5 drag and drop has no touch support and no keyboard story; the arrow buttons were the only accessible way to reorder, so removing them needed a library that keeps it accessible. Hand-rolled pointer, touch and keyboard handling would be more code to own than the dependency.
- **Acceptance criteria**
  - [x] Experience, education and the other list sections reorder by dragging a grip; the new order saves and survives a reload; a failed save shows an error and restores the old order.
  - [x] Skills reorder by dragging within their grid; profiles and highlights reorder in their forms.
  - [x] Reordering works from the keyboard and announces moves; up/down buttons are gone.
  - [x] A single item has no grip; the entry being edited has no grip.
- **Touches:** `components/SortableList.tsx` + css (new), `GenericListSection`, `SkillsSection`, `BasicsSection`, `EntryForm`, `package.json`; tests `SortableList.test.tsx` and `dnd-test-utils.tsx` (new), plus the section tests. jsdom cannot run a real drag, so tests fire the drop through the real `DndContext` handler; real mouse, pointer-stream and keyboard drags were exercised in the browser.

## Testing

```bash
make check
cd backend && uv run pytest -k "resume or migration" -q
cd frontend && npm run test -- ResumeDetailView
```

Manual: step 15. Validate export with `npx resume-cli validate` (or the JSON Resume schema via `ajv`).

## Out of scope

- Rendering themes / PDF.
- Per-section tables, master entry library, per-version overrides.
- Dragging keywords within a skill, and reordering whole sections (their order is fixed).
- Custom sections.
- Back-compat shims for old REST/MCP shapes.
