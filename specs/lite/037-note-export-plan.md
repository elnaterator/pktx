---
roadmap_id: 037
issue: n/a
branch: feat/037-note-export
---

# Plan: 037 Export notes: PDF download and copy to clipboard

## Overview

Notes are where cover letters get written. Employers take them as a PDF upload or as pasted
plain text, so every note gets both. No new resource type — cover letters stay ordinary notes.

The roadmap points at `research/note-export.md`; that file does not exist in the repo, so this
plan is derived from the roadmap text and the 036 pipeline as shipped.

- `GET /api/notes/{id}/pdf?theme=&date=` → `application/pdf`, owner-scoped, attachment filename.
- Letter layout reusing the 036 themes: name + contact header from the user's default resume,
  date, then the note body with markdown rendered as data.
- "Download PDF" (style picker, same remembered style as resumes) and "Copy" (plain text,
  markdown stripped) on the note detail page.

## Acceptance criteria

- [x] `GET /api/notes/{id}/pdf` returns 200, `Content-Type: application/pdf`, body starts `%PDF-`, `Content-Disposition: attachment; filename="<name>-<note-title>.pdf"` (slugified, ASCII-safe, fallback `note-<id>.pdf`).
- [x] Other user's / missing note → 404; route registered in `tests/integration/test_route_scoping.py`.
- [x] `?theme=` accepts every `PdfTheme` (default Modern); unknown → 422. `?date=YYYY-MM-DD` sets the letter date (default: server's today, UTC); malformed → 422. Date prints long-form (`November 11, 2026`).
- [x] Header (name, label, contact lines) comes from the default resume's `basics`, identical in look to the resume PDF for that theme; page size follows the same `countryCode` rule. User with no resume → PDF still renders, no header, A4.
- [x] Markdown renders: paragraphs (a single newline joins lines, as on screen; two trailing spaces or `\` break the line), `#`–`###` headings (deeper levels render as `###`), bold, italic, inline code, links, bullet and ordered lists (nested), blockquote, fenced/indented code block, horizontal rule, hard line break. Verified via extracted PDF text.
- [x] Markdown is data: Typst markup in note text (`#`, `*`, `$`, `[`, `]`, `\`, `@`, `<`) prints literally; raw HTML prints as literal text; no `eval`, no compile error. Link targets other than `http(s)`/`mailto` render as plain text (no link).
- [x] Empty note content → PDF with header + date only, no error.
- [x] Note title is not printed in the PDF (used for the filename only).
- [x] Resume PDF output unchanged (existing `test_pdf_service.py` + `TestPdf` still pass untouched).
- [x] Frontend: note detail (view mode) shows "Copy text" and the style picker + "Download PDF". Copy writes plain text to the clipboard (markdown syntax stripped, paragraph breaks and typed line breaks kept, list items as `- ` / `1. `, links as `text (url)` unless text equals url), shows "Copied" state, error toast on failure. Download shows busy state, saves via `saveBlob`, error toast on failure. Empty note: Copy disabled, PDF still allowed. Hidden while editing.
- [x] PDF style choice shared with the resume picker (same `pktx.pdfTheme` key).
- [x] Vitest covers copy text conversion, the Copy button, and the note PDF download; `make check` passes.

## Open questions

- [x] Print the note title in the PDF? — _proposed: no. Titles are working names ("Cover letter – Acme"); a letter that needs a heading can start with `# …`._
- [x] Which resume supplies the header? — _proposed: always the default resume. A `?resume_id=` picker is a later add if needed._
- [x] Where is markdown stripped for Copy? — _proposed: in the browser (instant, works inside the click gesture Safari requires for clipboard writes). Server stays PDF-only._

## Design

**Markdown → data (backend).** New `markdown_blocks.py`: parse with `markdown-it-py`
(`MarkdownIt("commonmark", {"html": False})` — already in `uv.lock` via `rich`; promote to a
direct dependency) and fold the token stream into a small JSON tree:

```python
# blocks
{"type": "paragraph", "inlines": [...]}
{"type": "heading", "level": 1..3, "inlines": [...]}
{"type": "list", "ordered": bool, "start": int, "items": [[block, ...], ...]}
{"type": "quote", "blocks": [...]}
{"type": "code", "text": str}
{"type": "rule"}
# inlines
{"type": "text", "text": str}            # also raw html, image alt text
{"type": "strong" | "emph", "inlines": [...]}
{"type": "code", "text": str}
{"type": "link", "url": str, "inlines": [...]}   # http(s)/mailto only, else unwrapped
{"type": "break"}
```

Unknown token types degrade to their text content — never dropped silently, never passed
through as markup.

**PDF (backend).** `pdf_service.py` gains:

```python
def _header(resume: Resume, theme) -> dict   # theme, paper, name, label, contact — extracted from build_payload, shared
def build_note_payload(content: str, resume_doc: dict | None, theme, on: date | None) -> dict
def render_note_pdf(content: str, resume_doc: dict | None, theme=DEFAULT_PDF_THEME, on: date | None = None) -> bytes
def note_pdf_filename(name: str | None, title: str | None, note_id: int) -> str
```

`pdf_filename` and `note_pdf_filename` share one slug/fallback helper.

**Templates.** Split `templates/resume.typ` so both documents share one definition of the
themes, page setup, helpers (`t`, `linked`, `contact-line`) and header:

- `templates/theme.typ` (new) — reads `sys.inputs.data` (key renamed from `resume`); `base`, `themes`, `setup` (document/text/par/list/page rules, applied with `#show: setup`), `header()` (renders nothing when name, label and contact are all missing — also drops the empty Executive band on a blank resume).
- `templates/resume.typ` (mod) — `#import "theme.typ": *` + sections only.
- `templates/letter.typ` (new) — header, right/left-aligned date per theme alignment, then a
  recursive `render-block` / `render-inline` over the JSON tree using Typst functions
  (`strong`, `emph`, `raw`, `link`, `list`, `enum`, `quote`, `line`, `heading`-styled text) —
  values only. Letter body uses roomier paragraph spacing than the resume.

Imports need files, so `_compile(template, payload)` compiles by path with `root` = the
templates directory (resolved via `importlib.resources.as_file`) instead of passing template
bytes. Both `.typ` siblings ship in the wheel (checked with `uv build`).

**Route.** `GET /api/notes/{note_id}/pdf` in `api/routes.py`: `note_service.get_note` (404 on
miss) → default resume via `resume_service.get_resume(None, ...)` (miss → `None`, no header)
→ `render_note_pdf`. `theme: PdfTheme`, `date: datetime.date | None` query params (FastAPI
422s bad values). The browser sends its local date so the letter is not a day off in UTC.

**Frontend.**

- `components/PdfDownload` (moved from `pages/resumes/`, now used by two pages): takes
  `fetchPdf: (theme: PdfTheme) => Promise<DataExport>`; resume page passes `fetchResumePdf`,
  note page `fetchNotePdf`. `PDF_THEMES` moves with it.
- `services/api/export.ts`: `fetchNotePdf(id, theme)` (adds `date` = local `YYYY-MM-DD`).
- `utils/markdownToText.ts` (new): `unified` + `remark-parse` (promote from transitive to
  direct deps; no new packages installed) → small mdast walker → plain text.
- `hooks/useCopyToClipboard` (new): extracted from `connect/CopyButton` (copied flag, 2 s
  reset, error toast); `CopyButton` switches to it; notes use it with the `Button` primitive.
- `pages/notes/NoteActions` (new): Copy button + `PdfDownload`, rendered in `NotePanel`
  view mode on the meta row (right-aligned; wraps under the date on phones).

**Touches:**
- `backend/pyproject.toml`, `backend/uv.lock` (mod) — `markdown-it-py>=4,<5` direct
- `backend/src/pktx/markdown_blocks.py` (new)
- `backend/src/pktx/pdf_service.py` (mod)
- `backend/src/pktx/templates/theme.typ` (new), `letter.typ` (new), `resume.typ` (mod)
- `backend/src/pktx/api/routes.py` (mod)
- `backend/tests/unit/test_markdown_blocks.py` (new), `test_pdf_service.py` (mod)
- `backend/tests/contract/test_note_api.py` (mod) — `TestNotePdf`
- `backend/tests/integration/test_route_scoping.py` (mod)
- `frontend/package.json`, `package-lock.json` (mod) — `unified`, `remark-parse` direct
- `frontend/src/components/PdfDownload.tsx` + `.module.css` (moved), `pages/resumes/ResumeDetailView.tsx` (mod)
- `frontend/src/services/api/export.ts` (mod)
- `frontend/src/utils/markdownToText.ts` (new)
- `frontend/src/hooks/useCopyToClipboard.ts` (new), `components/connect/CopyButton.tsx` (mod)
- `frontend/src/pages/notes/NoteActions.tsx` + `.module.css` (new), `NotePanel.tsx` (mod)
- `frontend/src/__tests__/` — `utils/markdownToText` (new), `components/NoteDetailView` (export actions), `services/export` (`fetchNotePdf`)
- `AGENTS.md` (mod) — note PDF paragraph, layout entries, Recent Changes

## Steps

- [x] Backend: add `markdown-it-py` direct dep; `markdown_blocks.py` + unit tests (each node type, nesting, html-as-text, unsafe link schemes).
- [x] Backend: split `resume.typ` into `theme.typ` + `resume.typ`, switch to path compile; confirm existing PDF tests pass unchanged.
- [x] Backend: `letter.typ`, `build_header` extraction, `build_note_payload`, `render_note_pdf`, `note_pdf_filename`; unit tests (text extraction per construct, injection, empty note, no resume, date format, all six themes compile).
- [x] Backend: route + contract tests + route-scoping registration.
- [x] Frontend: move/generalise `PdfDownload`; `fetchNotePdf`; update resume page + its test.
- [x] Frontend: `markdownToText` + tests; `useCopyToClipboard`; refactor `CopyButton`.
- [x] Frontend: `NoteActions` in `NotePanel`; tests; check phone layout.
- [x] Render a real cover-letter note in all six themes; eyeballed Modern, Executive, Jake's as images.
- [ ] Verify the note page in a live browser — **not done**: the local app sits behind Clerk sign-in. Covered by component tests only; worth a manual look (button row on phones).
- [x] Update `AGENTS.md`; `make check`.

## Testing

```bash
cd backend && make check
cd frontend && make check
make check          # root: both + Trivy
```

Not run: the Docker image build (templates verified in the wheel instead) and the manual
browser checks below.

Manual: note detail → Copy → paste into a plain-text field; Download PDF in each style;
note with no resume on the account; long two-page letter (footer page count).

## Out of scope

- MCP tool for note/resume PDFs (still the 036 follow-up).
- Choosing a non-default resume for the header; recipient/address block; signature image.
- Tables, images, footnotes and other GFM extensions in the PDF (render as their text).
- Bulk export of notes; DOCX.
- A dedicated cover-letter resource type.
