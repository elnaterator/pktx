// pktx resume template: one single-column, ATS-friendly layout (real text,
// no icons, no multi-column body) styled by a theme.
//
// Input: sys.inputs.resume, a JSON payload built by pktx.pdf_service.
// Every value is read as data and placed as text, never evaluated as markup.

#let r = json(bytes(sys.inputs.resume))

// ── Themes ────────────────────────────────────────────────────────────────
// Each theme is `base` plus the values it changes.
//   modern:    sans, left header, accent headings with a trailing rule (default).
//   compact:   sans, tight spacing to fit more on a page.
//   classic:   serif, centred header, ruled headings.
//   jakes:     after the "Jake's Resume" LaTeX template: Computer Modern, small
//              caps headings, employer + location over title + dates, all black.
//   executive: dark name band across the top, navy ruled headings.
//   minimal:   no rules, small grey letter-spaced headings, open spacing.
//
// heading: "inline" (title then rule) | "ruled" (rule under) | "smallcaps" | "plain"
// header:  "plain" | "band" (filled strip bleeding to the page edges)
// employer-first: work-like entries put the employer row above the role row.

#let base = (
  font: "Lato", size: 10pt, name-size: 24pt, label-size: 12pt,
  header: "plain", header-align: left, name-smallcaps: false,
  ink: rgb("#1a1a1a"), muted: rgb("#5a5a5a"), accent: rgb("#0e6f8f"),
  label-accent: true, rule: 0.6pt, margin: (x: 0.7in, y: 0.6in),
  heading: "inline", leading: 0.62em, entry-gap: 0.9em, section-gap: 1em,
  employer-first: false, contact-sep: "·",
)
#let themes = (
  modern: base,
  compact: base + (
    size: 9.5pt, name-size: 18pt, label-size: 10.5pt, accent: rgb("#2b2b2b"),
    label-accent: false, margin: (x: 0.55in, y: 0.5in), heading: "ruled",
    leading: 0.5em, entry-gap: 0.6em, section-gap: 0.9em,
  ),
  classic: base + (
    font: "Libertinus Serif", size: 10.5pt, name-size: 22pt, label-size: 11.5pt,
    header-align: center, accent: rgb("#1f3a5f"), label-accent: false,
    heading: "ruled", leading: 0.6em, section-gap: 0.9em,
  ),
  jakes: base + (
    font: "New Computer Modern", size: 10.5pt, name-size: 25pt, label-size: 11pt,
    header-align: center, name-smallcaps: true, ink: black, muted: black,
    accent: black, label-accent: false, rule: 0.5pt, margin: (x: 0.6in, y: 0.5in),
    heading: "smallcaps", leading: 0.55em, entry-gap: 0.75em, section-gap: 0.85em,
    employer-first: true, contact-sep: "|",
  ),
  executive: base + (
    header: "band", accent: rgb("#1f2a44"), label-accent: false,
    heading: "ruled", margin: (x: 0.7in, y: 0.55in), section-gap: 1.05em,
  ),
  minimal: base + (
    size: 10pt, name-size: 26pt, label-size: 11.5pt, accent: rgb("#1a1a1a"),
    muted: rgb("#777777"), label-accent: false, margin: (x: 0.8in, y: 0.7in),
    heading: "plain", leading: 0.68em, entry-gap: 1em, section-gap: 1.4em,
  ),
)
#let th = themes.at(r.theme)
#let ink = th.ink
#let muted = th.muted

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
  let rule = line(length: 100%, stroke: th.rule + th.accent)
  if th.heading == "smallcaps" {
    text(size: th.size + 2pt, fill: th.accent, smallcaps(title))
    v(-0.65em)
    rule
  } else if th.heading == "plain" {
    text(size: th.size - 1pt, weight: "bold", fill: muted, tracking: 0.18em, upper(title))
  } else {
    set text(size: th.size + 1pt, weight: "bold", fill: th.accent, tracking: 0.08em)
    if th.heading == "inline" {
      grid(
        columns: (auto, 1fr),
        column-gutter: 0.6em,
        align: horizon,
        upper(title), line(length: 100%, stroke: th.rule + th.accent.lighten(55%)),
      )
    } else {
      upper(title)
      v(-0.6em)
      rule
    }
  }
})

#let entry(e) = block(width: 100%, breakable: true, below: th.entry-gap, {
  // Employer-first themes swap the rows of role/employer entries, so the
  // employer leads with its location and the role carries the dates.
  let swap = th.employer-first and e.employer
  let (top, top-aside, sub, sub-aside) = if swap {
    (e.sub, e.subAside, e.heading, e.aside)
  } else {
    (e.heading, e.aside, e.sub, e.subAside)
  }
  let top-url = if swap { none } else { e.url }
  block(sticky: true, below: th.leading + 0.15em, {
    if top != none or top-aside != none {
      heading-row(strong(linked(top, top-url)), text(fill: muted, t(top-aside)))
    }
    if sub != none or sub-aside != none {
      v(-0.4em)
      let aside = text(fill: muted, t(sub-aside))
      heading-row(emph(t(sub)), if th.employer-first { emph(aside) } else { aside })
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
#let contact-line(items, sep-fill) = {
  let sep = text(fill: sep-fill)[#h(0.45em)#th.contact-sep#h(0.45em)]
  items.map(c => box(linked(c.text, c.url))).join(sep)
}

// ── Header ────────────────────────────────────────────────────────────────

#let header-body(name-fill, label-fill, contact-fill, link-fill, sep-fill) = align(th.header-align, {
  if r.name != none {
    let name = text(size: th.name-size, weight: "bold", tracking: 0.01em, fill: name-fill, t(r.name))
    if th.name-smallcaps { smallcaps(text(weight: "regular", name)) } else { name }
    linebreak()
  }
  if r.label != none {
    v(-0.15em)
    text(size: th.label-size, fill: label-fill, t(r.label))
    linebreak()
  }
  set text(size: th.size - 1pt, fill: contact-fill)
  show link: set text(fill: link-fill)
  for group in r.contact {
    contact-line(group, sep-fill)
    linebreak()
  }
})

#if th.header == "band" {
  let light = rgb("#e8ecf3")
  block(
    width: 100%, fill: th.accent, below: 1.2em,
    inset: (y: 1.4em), outset: (x: th.margin.x, top: th.margin.y),
    header-body(white, light, light, white, light.transparentize(40%)),
  )
} else {
  header-body(ink, if th.label-accent { th.accent } else { muted }, ink, th.accent, muted)
}

#if r.summary != none {
  section-title("Summary")
  par(t(r.summary))
}

// ── Sections (registry order, empty ones already dropped) ─────────────────

#for s in r.sections {
  section-title(s.title)
  if s.layout == "rows" { rows(s.items) } else { for e in s.items { entry(e) } }
}
