---
roadmap_id: 036
issue: n/a
branch: feat/036-resume-pdf-export
---

# Plan: 036 Export resume as PDF

## Overview

Download any resume version as a clean, ATS-friendly PDF from the resume detail page.
Resume is already a JSON Resume v1.0.0 document (034), so render it server-side with the
`typst` Python package (in-process Rust compiler, no Chromium, Lambda-friendly) and one
vendored JSON Resume Typst template. Research: `research/resume-pdf-export.md`.

- `GET /api/resumes/{id}/pdf` → `application/pdf`, owner-scoped, attachment filename.
- All stored sections render; empty ones hidden; array order kept.
- Data passed via `sys.inputs` JSON — never interpolated into Typst source.
- Fonts deterministic (no system fonts), same output locally and on Lambda (arm64).
- "Download PDF" action on the resume detail page.

## Acceptance criteria

- [x] `GET /api/resumes/{id}/pdf` returns 200, `Content-Type: application/pdf`, body starts `%PDF-`, `Content-Disposition: attachment; filename="<name>-<label>.pdf"` (slugified, ASCII-safe, fallback `resume-<id>.pdf`).
- [x] Other user's / missing id → 404 (route registered in `tests/integration/test_route_scoping.py`).
- [x] Every list section in `SECTIONS` + basics renders when non-empty, and is absent when empty (checked via extracted PDF text in tests).
- [x] Entry order in PDF matches array order.
- [x] Partial ISO dates format as `2021`, `Mar 2021`, `Mar 2021`; missing `endDate` → "Present".
- [x] Typst markup in user text (`#`, `*`, `$`, `[`, `]`, `\`, `@`, `<`) prints literally — no injection, no compile error.
- [x] Minimal resume (empty `{}` / only `basics.name`) renders without error.
- [x] Page size: Letter when `basics.location.countryCode` ∈ {US, CA}, else A4.
- [x] Template ships in the wheel (`backend/src/pktx/templates/resume.typ`), no runtime network fetch, system fonts ignored.
- [x] `typst` dep pinned; Docker image builds and renders on linux/arm64 (abi3 manylinux wheel).
- [x] Frontend: "Download PDF" button on `ResumeDetailView` header, shows busy state, saves via `saveBlob`, error toast on failure; Vitest covers it.
- [x] `make check` passes.

## Open questions

- [x] Template source — _proposed: write our own `resume.typ` (single-column, ATS-friendly, modelled on stuxf `basic-resume` layout). `fruggiero/typst-jsonresume-cv` has no license, so it can't be vendored._
- [x] Fonts — _proposed: use Typst's embedded fonts (Libertinus Serif / New Computer Modern) with `ignore_system_fonts=True`; no extra font files. Bundle a custom OFL font later with a theme picker._
- [x] Page size — _proposed: derive from `countryCode` (above); no user setting yet._

## Design

`pdf_service.py` (new) — pure render, no DB:

```python
def render_resume_pdf(doc: dict[str, Any]) -> bytes
```

- Reads `templates/resume.typ` via `importlib.resources`.
- `build_payload` flattens each section (per-section builder in `_LAYOUTS`, import-time drift check vs `SECTIONS`) into a generic `entries` (heading/aside/sub/subAside/text/bullets/tags) or `rows` (label/value) layout; formats dates, computes `paper`, drops empty sections, keeps registry order. Template is one generic renderer.
- Calls `typst.compile(template_bytes, sys_inputs={"resume": json.dumps(payload)}, ignore_system_fonts=True)` (typst 0.15 accepts template bytes directly).
- Template: `#let r = json(bytes(sys.inputs.resume))`; every string inserted as content via
  value (never `eval`), so markup chars are literal.

Route in `api/routes.py`: `GET /api/resumes/{version_id}/pdf` → `service.get_resume(...)` (404 on
miss) → `render_resume_pdf(version.data)` → `Response(media_type="application/pdf", headers=Content-Disposition)`. Filename builder `_pdf_filename(name, label, id)`. Register before any `/{version_id}/...` catch-all ordering issue (no conflict: literal `pdf` segment).

Frontend: `services/api/export.ts` gains shared `fetchDownload(path, what, fallback)`; `fetchDataExport` + new `fetchResumePdf(id)` use it. `ResumeDetailView` header gets `IconButton`/`Button` "Download PDF" (lucide `FileDown`).

**Touches:**
- `backend/pyproject.toml`, `backend/uv.lock` (mod) — `typst==0.15.*`
- `backend/src/pktx/pdf_service.py` (new)
- `backend/src/pktx/templates/resume.typ` (new)
- `backend/src/pktx/api/routes.py` (mod)
- `backend/tests/unit/test_pdf_service.py` (new) — dates, filename, paper, render smoke, injection, section presence via `pypdf` text extraction (new dev dep)
- `backend/tests/contract/test_resume_api.py` (mod) — `TestPdf`
- `backend/tests/integration/test_route_scoping.py` (mod)
- `frontend/src/services/api/export.ts` (mod)
- `frontend/src/__tests__/services/export.test.ts` (mod)
- `frontend/src/pages/resumes/ResumeDetailView.tsx` (mod)
- `frontend/src/__tests__/` resume detail test (mod)
- `AGENTS.md` (mod) — note PDF route + template location

## Steps

- [x] Add `typst` dep; spike `typst.compile` with `sys_inputs` + bytes/root; confirm embedded fonts and arm64 wheel.
- [x] Write `resume.typ` covering basics (name, label, contact line, profiles, summary) + work, volunteer, education, awards, certificates, publications, skills, languages, interests, references, projects.
- [x] `pdf_service.py`: payload builder (dates, paper, empty-section pruning, ordering) + render.
- [x] Unit tests: date fmt, filename, paper, full + minimal + injection renders, section presence/order via text extraction.
- [x] REST route + contract test + scoping registration.
- [x] Frontend API helper + button + Vitest.
- [x] Docker build smoke: `docker build --platform linux/arm64` + render in container → `%PDF-1.7`.
- [x] AGENTS.md note; `make check`.

## Testing

```bash
cd backend && make check
cd frontend && make check
make check
```

Manual: `make run-local`, open a resume, click Download PDF, eyeball layout + copy-paste text (ATS check).

## Out of scope

- Theme picker / multiple templates; RenderCV.
- MCP tool or resource for PDF.
- Per-user page-size setting.
- Custom bundled fonts.
