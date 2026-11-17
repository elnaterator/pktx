// pktx letter template: a note (cover letter) under the resume's header.
//
// The body arrives as a block tree (pktx.markdown_blocks) and is built here
// with Typst functions, so note text is data and never parsed as markup.

#import "theme.typ": *

#show: setup

// Letters read as prose: more air between paragraphs than a resume.
#let gap = th.leading + 0.75em
#set par(spacing: gap)
#set list(spacing: th.leading + 0.3em)
#set enum(indent: 0.2em, body-indent: 0.55em, spacing: th.leading + 0.3em)
#show raw: set text(size: th.size - 0.5pt)

#let heading-sizes = (th.size + 5pt, th.size + 2.5pt, th.size + 0.5pt)

#let render-inline(n) = {
  if n.type == "text" { [#n.text] }
  else if n.type == "strong" { strong(n.inlines.map(render-inline).join()) }
  else if n.type == "emph" { emph(n.inlines.map(render-inline).join()) }
  else if n.type == "code" { raw(n.text) }
  else if n.type == "link" { link(n.url, n.inlines.map(render-inline).join()) }
  else if n.type == "break" { linebreak() }
}

#let render-block(b) = {
  if b.type == "paragraph" {
    par(b.inlines.map(render-inline).join())
  } else if b.type == "heading" {
    // Sticky: a heading never ends a page without the text under it.
    block(sticky: true, above: gap + 0.3em, below: gap - 0.2em, text(
      size: heading-sizes.at(b.level - 1), weight: "bold", fill: th.accent,
      b.inlines.map(render-inline).join(),
    ))
  } else if b.type == "list" {
    let items = b.items.map(item => item.map(render-block).join())
    if b.ordered { enum(start: b.start, ..items) } else { list(..items) }
  } else if b.type == "quote" {
    block(
      inset: (left: 1em, y: 0.2em), stroke: (left: 1.5pt + muted.lighten(50%)),
      text(fill: muted, b.blocks.map(render-block).join()),
    )
  } else if b.type == "code" {
    block(width: 100%, inset: 0.7em, radius: 2pt, fill: luma(245), raw(b.text, block: true))
  } else if b.type == "rule" {
    line(length: 100%, stroke: th.rule + muted.lighten(40%))
  }
}

#header()

#block(above: 1.8em, below: 1.6em, text(fill: muted, t(r.date)))

#for b in r.blocks { render-block(b) }
