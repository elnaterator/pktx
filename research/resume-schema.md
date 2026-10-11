# Resume schema simplification (034)

Review of the resume shape after 033. Goal: a solid, simple, maintainable data structure.

## Problems with the 033 shape

- 9 entry schemas with 9 naming schemes: who (`title`, `role`, `name`, `language`), where
  (`company`, `organization`, `institution`, `issuer`, `venue`), dates (`start_date`/`end_date`,
  `issued`/`expires`, `date`). Each is a decision to maintain, document in tool docstrings, and
  teach the LLM.
- Contact is over-built: phone is a fixed field but email is a key/value; preset keys, value kinds
  (email/url/text), a presets endpoint, and legacy `email`/`website`/`linkedin`/`github` shortcuts.
- `enabled_sections` is stored state derivable from "has entries", plus rules to keep them
  consistent (a section with entries is always shown; 422 when disabling a non-empty section).
- Entries addressed by id or 0-based index: ambiguous when an id looks numeric, and indexes shift
  after deletes.
- No way to reorder entries.
- Section field definitions REST-only; MCP docstrings list keys in plain text and will drift.

## Recommendations

1. **JSON Resume as canonical schema**, plus a stable `id` per entry. LLMs already write it
   correctly with no docs (the biggest MCP win), import/export and rendering themes come free, and
   naming stops being a design decision. Its internal inconsistency (`work.name`, `awards.awarder`)
   is accepted once. Snake_case internally; camelCase on import/export via Pydantic
   `alias_generator=to_camel` + `populate_by_name=True`.
2. **Contact + summary merge into `basics`**:
   `{name, label, email, phone, url, location, summary, profiles: [{id, network, username, url}]}`.
   `label` is the headline. Removes `contact_keys.py`, `GET /api/resume-contact-keys`,
   `ContactInfo.upgrade_legacy`, the shortcuts. Network suggestions become a frontend constant.
   `update_resume_section` becomes `update_resume_basics`.
3. **Drop `enabled_sections`**: a section is shown when it has entries. "Add section" in the UI
   opens a form for the first entry; an empty section is transient UI state. Removes a field, an
   endpoint, an MCP tool, the 422 rule, and most of `resume_order.py`.
4. **Skills as groups**: `{id, name, level?, keywords[]}`. Matches how resumes render, fewer
   entries and MCP calls, no `"Other"` default.
5. **Partial ISO dates**: `YYYY`, `YYYY-MM`, `YYYY-MM-DD`, else 422. Missing `end_date` = present.
6. **Ids only** for entry addressing; drop the index path.
7. **Reorder**: `PUT /api/resumes/{id}/{section}/order {ids: [...]}` and
   `reorder_resume_entries(id, section, entry_ids)`. Array order is the order. Drops the `insert`
   registry hint.
8. **Schemas from the models**: MCP `data` typed per section (discriminated union of the Pydantic
   models) so tool input carries real JSON Schema. Add `import_resume(id, data)` + matching `PUT`
   (whole JSON Resume, validated, replaces `resume_data`) for bulk creation, imports and one-call
   tailoring. Derive `GET /api/resume-sections` from `model_json_schema()` with
   `json_schema_extra={"widget": ...}`; drop `unique_field` unless a bug needs it.
9. **Keep full copies per version.** A master entry library with per-version selections/overrides
   brings sync and override problems; copy-on-create plus LLM tailoring is the right trade here.

## Net effect

| Removed | Added |
|---|---|
| `enabled_sections`, toggle endpoint + tool, 422 rule | reorder op |
| contact keys/kinds, presets endpoint, legacy shortcuts | `import_resume` |
| index addressing | date validation |
| 9 ad-hoc field vocabularies | one external spec |

MCP tool count stays at 12 (`set_resume_section_enabled` out; `reorder_resume_entries`,
`import_resume` in; `update_resume_section` renamed `update_resume_basics`), each simpler and
fully typed.

## Migration

One data migration (v16 → v17) maps the old shape to the new one, then every legacy path is
deleted. Single owner per record, no external consumers: no back-compat shims.

## Suggested order

Shape first (1, 2), then deletions (3, 6, 8), then additions (4, 5, 7).
