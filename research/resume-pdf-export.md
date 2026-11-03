# Resume PDF export

Goal: download any resume version as a clean, ATS-friendly PDF. Since 034 the resume is a
JSON Resume v1.0.0 document (`resume_version.resume_data`), so reuse the JSON Resume
rendering ecosystem instead of a bespoke layout engine.

Constraints: backend is Python 3.11 on AWS Lambda (container image, cold starts matter);
no Node runtime in the final image; user data must not leave our infra (no hosted
render APIs).

## Options (searched 2026-11-02)

| Option | How | Fit |
|--------|-----|-----|
| **Typst via `typst` (PyPI)** + JSON Resume template | `typst.compile(tpl, sys_inputs={"resume": json})`; template reads `json(bytes(sys.inputs.resume))` | **Best.** In-process Rust compiler with prebuilt wheels, no Chromium, ms-level render, small image delta, Python 3.11 OK. |
| RenderCV 2.x (MIT) | JSON Resume → RenderCV YAML (`jsonresume-to-rendercv`, or JSON Resume's own converter) → `rendercv render` (Typst under the hood) | Nine polished themes (classic, sb2nov, engineeringresumes, harvard, …). But needs Python ≥3.12 (we're on 3.11), CLI-first (no documented Python API), extra mapping layer that drops sections (volunteer, languages, certificates, …). Revisit for a theme picker. |
| `resumed` / `resume-cli` + `jsonresume-theme-*` | Node, render theme HTML, Puppeteer prints PDF | Largest theme catalogue, but adds Node + Chromium (~300 MB) to the Lambda image, slow cold starts, `--no-sandbox` in containers. Reject. |
| ferrocv (Rust) | JSON Resume → Typst → PDF CLI, bundles `typst-jsonresume-cv` theme | Native JSON Resume, but a Rust binary to ship and young (0.x). Good prior art for the template. |
| WeasyPrint + Jinja port of a theme | HTML/CSS → PDF in Python | Needs Pango/system libs in the image; we'd port a theme by hand anyway. |
| Browser print (frontend print CSS) | `window.print()` on a print view | Zero deps, but output varies by browser, no MCP/API path, no control over pagination. Fine as a stopgap only. |

## Recommendation

1. Backend renders PDF with the `typst` Python package (pin version; check Linux x86_64/arm64
   wheels for the Lambda arch).
2. Vendor one JSON Resume Typst template in `backend/src/pktx/templates/` — start from
   [fruggiero/typst-jsonresume-cv](https://github.com/fruggiero/typst-jsonresume-cv)
   (already reads JSON Resume; based on stuxf `basic-resume`, ATS-friendly). Check its
   license before vendoring; otherwise write our own on top of `@preview/basic-resume`.
   Vendor rather than fetch Typst Universe packages at runtime (no network on render).
3. Cover every section we store (basics, work, education, skills, projects, certificates,
   awards, publications, volunteer, languages, interests, references); empty sections hidden;
   array order = display order; missing `endDate` = "Present"; partial ISO dates formatted.
4. Bundle fonts in the package (Typst embeds only defaults; set `font_paths`) so output is
   identical locally and on Lambda.
5. REST: `GET /api/resumes/{id}/pdf` → `application/pdf`, `Content-Disposition` filename from
   `basics.name` + label; owner-scoped like every route (register in `test_route_scoping.py`).
   Frontend: "Download PDF" on the resume detail page.
6. Escape user text — pass data via `sys.inputs` JSON, never string-interpolate into Typst
   source (Typst markup injection).

## Open questions

- MCP: expose PDF too? Tools return JSON/text; an option is a tool returning a short-lived
  download URL, or an MCP resource with a blob. Defer unless asked.
- One theme or a picker? Start with one; a picker (more vendored templates, or RenderCV after a
  3.12 bump) is a follow-up.
- Page size: Letter vs A4 — user setting or derive from `basics.location.countryCode`.

## Sources

- resumed (Puppeteer PDF export): https://github.com/rbardini/resumed
- jsonresume/resume-cli: https://github.com/jsonresume/resume-cli
- typst-py: https://github.com/leiserfg/typst-py, https://pypi.org/project/typst/
- RenderCV: https://pypi.org/project/rendercv/, https://github.com/sinaatalay/rendercv
- jsonresume-to-rendercv: https://pypi.org/project/jsonresume-to-rendercv
- ferrocv: https://docs.rs/crate/ferrocv/latest
- typst-jsonresume-cv: https://github.com/fruggiero/typst-jsonresume-cv
