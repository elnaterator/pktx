// pktx resume template: single column, ATS-friendly (real text, no tables
// for layout beyond two-column heading rows, no icons).
//
// Input: sys.inputs.resume, a JSON payload built by pktx.pdf_service.
// Every value is read as data and placed as text, never evaluated as markup.

#let r = json(bytes(sys.inputs.resume))

#let ink = rgb("#1a1a1a")
#let muted = rgb("#555555")
#let accent = rgb("#1f3a5f")

#set document(title: if r.name != none { r.name } else { "Resume" })
#set page(paper: r.paper, margin: (x: 0.65in, y: 0.6in))
#set text(font: "Libertinus Serif", size: 10.5pt, fill: ink, lang: "en")
#set par(leading: 0.55em, spacing: 0.7em)
#set list(indent: 0.4em, body-indent: 0.5em, spacing: 0.45em)
#show link: set text(fill: accent)

// `none` prints as nothing.
#let t(value) = if value == none { [] } else { [#value] }
#let linked(value, url) = if url == none { t(value) } else { link(url, t(value)) }

#let heading-row(start, end) = grid(
  columns: (1fr, auto),
  column-gutter: 1em,
  start, align(right, end),
)

#let section-title(title) = {
  v(0.5em)
  text(size: 11pt, weight: "bold", tracking: 0.06em, fill: accent, upper(title))
  v(-0.55em)
  line(length: 100%, stroke: 0.5pt + accent)
  v(0.1em)
}

#let entry(e) = block(width: 100%, breakable: true, below: 0.85em, {
  if e.heading != none or e.aside != none {
    heading-row(strong(linked(e.heading, e.url)), text(fill: muted, t(e.aside)))
  }
  if e.sub != none or e.subAside != none {
    v(-0.35em)
    heading-row(emph(t(e.sub)), text(fill: muted, t(e.subAside)))
  }
  if e.text != none { par(t(e.text)) }
  if e.bullets.len() > 0 { list(..e.bullets.map(t)) }
  if e.tags != none { text(fill: muted, size: 9.5pt, t(e.tags)) }
})

#let rows(items) = grid(
  columns: (auto, 1fr),
  column-gutter: 1em,
  row-gutter: 0.5em,
  ..items.map(i => (strong(t(i.label)), t(i.value))).flatten(),
)

// ── Header ────────────────────────────────────────────────────────────────

#align(center, {
  if r.name != none { text(size: 20pt, weight: "bold", t(r.name)) }
  if r.label != none {
    v(-0.4em)
    text(size: 11.5pt, fill: muted, t(r.label))
  }
  if r.contact.len() > 0 {
    v(-0.2em)
    text(size: 9.5pt, r.contact.map(c => linked(c.text, c.url)).join([ #h(0.3em)|#h(0.3em) ]))
  }
})

#if r.summary != none {
  section-title("Summary")
  par(t(r.summary))
}

// ── Sections (registry order, empty ones already dropped) ─────────────────

#for s in r.sections {
  section-title(s.title)
  if s.layout == "rows" { rows(s.items) } else { for e in s.items { entry(e) } }
}
