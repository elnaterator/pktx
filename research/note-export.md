# Note export: PDF + copy to clipboard

Goal: notes are where cover letters get written, so a note needs to leave pktx in the two
forms employers accept.

## How cover letters are sent (2026-11-03)

| Channel | Format | Share |
|---------|--------|-------|
| ATS application (Greenhouse, Lever, Workday, Ashby) | PDF upload (sometimes DOCX), or a paste box | Most common |
| Email to recruiter / hiring manager | Letter is the email body; resume attached as PDF | Common |
| LinkedIn Easy Apply / referral | None, or a short pasted note | Common, short |
| Formal (government, academia, law) | Required PDF, sometimes letterhead | Niche |

So: **PDF** for uploads and **clean plain text** for paste boxes and email bodies. Both matter.
Letters are short (3–4 paragraphs, ~250–350 words); a PDF should visually match the resume
(same name header, font, colours) — recruiters notice a mismatch.

## Decisions

- **Any note** can be exported; no new resource type. Cover letters are just notes (a
  `cover-letter` tag is a convention, not a gate) — keeps the model simple.
- **PDF reuses 036**: same Typst pipeline (`pdf_service`, data via `sys.inputs`, never spliced),
  same themes and picker, so a letter can match the resume. Letter layout: resume-style name +
  contact header from the **default** resume's `basics`, date, then the note body. Title is not
  printed by default (titles are usually internal, e.g. "Acme cover letter").
- **Markdown**: notes are markdown (`MarkdownContent`). Convert to a small safe block tree in
  Python (paragraphs, bold/italic, bullet/numbered lists, links, headings) and render those as
  Typst content from data — never pass markdown or user text as Typst markup.
- **Copy**: one button on the note page copying plain text with markdown stripped (lists as
  `- ` / `1. `, links as `text (url)`), via the Clipboard API with a toast.

## Open questions

- Sign-off: append `basics.name` under the body, or leave to the note text? Proposed: leave to
  the note (most letters already end "Sincerely, Name").
- Recipient / company block from a linked application? Proposed: follow-up, not v1.
- MCP tool for the PDF: still deferred, same as 036.
