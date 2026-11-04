// pktx resume template: one single-column, ATS-friendly layout (real text,
// no icons, no multi-column body) styled by a theme.
//
// Input: sys.inputs.resume, a JSON payload built by pktx.pdf_service.
// Every value is read as data and placed as text, never evaluated as markup.

#let r = json(bytes(sys.inputs.resume))

// ── Themes ────────────────────────────────────────────────────────────────
// classic: serif, centred header, ruled headings.
// modern:  sans, left header, accent headings with a trailing rule.
// compact: sans, tight spacing to fit more on a page.

#let themes = (
  classic: (
    font: "Libertinus Serif", size: 10.5pt, name-size: 22pt, label-size: 11.5pt,
    header-align: center, accent: rgb("#1f3a5f"), margin: (x: 0.7in, y: 0.6in),
    heading: "ruled", leading: 0.6em, entry-gap: 0.9em, section-gap: 0.9em,
  ),
  modern: (
    font: "Lato", size: 10pt, name-size: 24pt, label-size: 12pt,
    header-align: left, accent: rgb("#0e6f8f"), margin: (x: 0.7in, y: 0.6in),
    heading: "inline", leading: 0.62em, entry-gap: 0.9em, section-gap: 1em,
  ),
  compact: (
    font: "Lato", size: 9.5pt, name-size: 18pt, label-size: 10.5pt,
    header-align: left, accent: rgb("#2b2b2b"), margin: (x: 0.55in, y: 0.5in),
    heading: "ruled", leading: 0.5em, entry-gap: 0.6em, section-gap: 0.9em,
  ),
)
#let th = themes.at(r.theme)

#let ink = rgb("#1a1a1a")
#let muted = rgb("#5a5a5a")

#set document(title: if r.name != none { r.name } else { "Resume" })
#set text(font: th.font, size: th.size, fill: ink, lang: "en")
#set par(leading: th.leading, spacing: th.leading + 0.2em)
#set list(
  indent: 0.2em, body-indent: 0.55em, spacing: th.leading + 0.05em,
  marker: text(fill: th.accent, sym.bullet),
)
#show link: set text(fill: th.accent)
#set page(
  paper: r.paper,
  margin: th.margin,
  // Name and page count on every page of a multi-page resume.
  footer: context {
    let total = counter(page).final().first()
    if total > 1 {
      set text(size: 8pt, fill: muted)
      align(center)[#if r.name != none [#r.name #h(0.4em)·#h(0.4em)] #counter(page).display() of #total]
    }
  },
)

// `none` prints as nothing.
#let t(value) = if value == none { [] } else { [#value] }
#let linked(value, url) = if url == none { t(value) } else { link(url, t(value)) }

#let heading-row(start, end) = grid(
  columns: (1fr, auto),
  column-gutter: 1em,
  start, align(right, end),
)

// Sticky: a heading never ends a page without the content under it.
#let section-title(title) = block(sticky: true, above: th.section-gap, below: 0.55em, {
  set text(size: th.size + 1pt, weight: "bold", fill: th.accent, tracking: 0.08em)
  if th.heading == "inline" {
    grid(
      columns: (auto, 1fr),
      column-gutter: 0.6em,
      align: horizon,
      upper(title), line(length: 100%, stroke: 0.6pt + th.accent.lighten(55%)),
    )
  } else {
    upper(title)
    v(-0.6em)
    line(length: 100%, stroke: 0.6pt + th.accent)
  }
})

#let entry(e) = block(width: 100%, breakable: true, below: th.entry-gap, {
  block(sticky: true, below: th.leading + 0.15em, {
    if e.heading != none or e.aside != none {
      heading-row(strong(linked(e.heading, e.url)), text(fill: muted, t(e.aside)))
    }
    if e.sub != none or e.subAside != none {
      v(-0.4em)
      heading-row(emph(t(e.sub)), text(fill: muted, t(e.subAside)))
    }
  })
  if e.text != none { par(t(e.text)) }
  if e.bullets.len() > 0 { list(..e.bullets.map(t)) }
  if e.tags != none { text(fill: muted, size: th.size - 0.75pt, t(e.tags)) }
})

#let rows(items) = grid(
  columns: (auto, 1fr),
  column-gutter: 1.2em,
  row-gutter: th.leading + 0.1em,
  ..items.map(i => (strong(t(i.label)), t(i.value))).flatten(),
)

// Each contact group is one line; items never split across lines.
#let contact-sep = text(fill: muted)[#h(0.45em)·#h(0.45em)]
#let contact-line(items) = items.map(c => box(linked(c.text, c.url))).join(contact-sep)

// ── Header ────────────────────────────────────────────────────────────────

#align(th.header-align, {
  if r.name != none {
    text(size: th.name-size, weight: "bold", tracking: 0.01em, t(r.name))
    linebreak()
  }
  if r.label != none {
    v(-0.15em)
    text(size: th.label-size, fill: if th.heading == "inline" { th.accent } else { muted }, t(r.label))
    linebreak()
  }
  set text(size: th.size - 1pt)
  for group in r.contact {
    contact-line(group)
    linebreak()
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
