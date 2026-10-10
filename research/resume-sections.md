# Resume sections and structure

Question: what common resume parts are missing (certifications, projects, ...) and is the resume structure the right shape to add them?

## Today

`Resume` (models.py) is one JSON blob per `ResumeVersion`: `contact`, `summary`, `experience[]`, `education[]`, `skills[]`. Sections are named in tuples in `resume_service.py` (`SECTION_UPDATE`, `SECTION_LIST`, `ALL_SECTIONS`), again in `resume_tools.py`, and again as one hand-written frontend component per section (`pages/resumes/*Section.tsx`).

## Missing sections

Likely to matter for a job search:

- **Projects**: name, description, URL, tech, highlights, dates. Biggest gap for engineers and career changers.
- **Certifications and licenses**: name, issuer, issued/expires dates, credential id and URL.
- **Awards and honors**.
- **Publications, talks, patents**: title, venue, date, URL.
- **Volunteer / community work**: same shape as experience.
- **Languages**: language plus proficiency.
- **Custom section**: title plus free-form entries or bullets, so nothing else needs a code change.

Probably skip: interests, references ("available on request" is standard).

Also thin inside existing sections:

- `ContactInfo` has fixed link fields (linkedin/website/github); needs a generic profiles list.
- `Skill` is flat name + category; no proficiency or years, which is fine, but categories are free text.
- Experience has no company URL; dates are free-form strings so sorting relies on `sortEntriesByDate.ts` parsing.

## Structure evaluation

What works: version-per-resume with tags, links to other resources, JSON blob keeps reads simple, singleton vs list split is sound.

What hurts when adding 5+ sections:

1. **Section list repeated in 3+ places** (service tuples, MCP tool enums/docs, frontend routes/components). Each new section touches all of them.
2. **Per-section branching** in `resume_service.add_entry` (`if section == "skills"`, `("experience", "education")` date sorting).
3. **Index-addressed entries** (`update_entry(index)`, `remove_entry(index)`): fragile under concurrent edits and sorting; entries have no stable id.
4. **No per-version layout**: no section order, no hide/show, no section title override. Tailoring a resume per application (the product's point) wants this.
5. **No schema version inside the blob**: adding sections is backward compatible only because everything defaults to `[]`.
6. **Free-string dates** with no validation.

## Proposed direction (for the plan phase to confirm)

Section registry: one definition per section (key, label, kind = singleton | list, pydantic entry model, summary formatter, sort rule). Service, MCP tools, and frontend render from it. Entries get stable ids; keep index addressing as a compatibility shim. Per-version `layout`: ordered list of section keys with visible flag and optional title. Add the new sections as registry entries. Data migration: none needed for existing sections; `layout` defaults to current order.

Open questions for planning:

- Do new sections get their own MCP tools, or does a generic `add_resume_entry(section=...)` stay (it already does)?
- Stable ids: migrate existing blobs on read or in a schema migration?
- Does the frontend resume preview/print output need new templates per section?
- Export (020) must include the new sections.

## Split suggestion

Two items could be cleaner: (a) registry refactor with layout, (b) new sections on top. Kept as one item here so the refactor is justified by real sections; split at plan time if it grows.
