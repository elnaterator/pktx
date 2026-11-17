// pktx resume template: one single-column, ATS-friendly layout (real text,
// no icons, no multi-column body) styled by a theme from theme.typ.

#import "theme.typ": *

#show: setup

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

#header()

#if r.summary != none {
  section-title("Summary")
  par(t(r.summary))
}

// ── Sections (registry order, empty ones already dropped) ─────────────────

#for s in r.sections {
  section-title(s.title)
  if s.layout == "rows" { rows(s.items) } else { for e in s.items { entry(e) } }
}
