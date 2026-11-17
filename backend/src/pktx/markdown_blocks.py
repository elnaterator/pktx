"""Markdown as data: parse CommonMark into a small JSON-able block tree.

The PDF templates walk this tree and build content with Typst functions, so
note text is never spliced into Typst source. Anything the tree has no node
for (raw HTML, images, tables) degrades to its text rather than vanishing.

Blocks::

    {"type": "paragraph", "inlines": [...]}
    {"type": "heading", "level": 1..3, "inlines": [...]}
    {"type": "list", "ordered": bool, "start": int, "items": [[block, ...], ...]}
    {"type": "quote", "blocks": [...]}
    {"type": "code", "text": str}
    {"type": "rule"}

Inlines::

    {"type": "text", "text": str}
    {"type": "strong" | "emph", "inlines": [...]}
    {"type": "code", "text": str}
    {"type": "link", "url": str, "inlines": [...]}
    {"type": "break"}
"""

from typing import Any

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

Node = dict[str, Any]

MAX_HEADING_LEVEL = 3
_LINK_SCHEMES = ("http://", "https://", "mailto:")
_PARSER = MarkdownIt("commonmark", {"html": False})


def _text(value: str) -> Node:
    return {"type": "text", "text": value}


def _plain(node: SyntaxTreeNode) -> str:
    """All text under a node, for constructs with no node of their own."""
    if node.children:
        return "".join(_plain(c) for c in node.children)
    return node.content


def _merge(inlines: list[Node]) -> list[Node]:
    """Join neighbouring text nodes and drop empty ones."""
    out: list[Node] = []
    for n in inlines:
        if n["type"] == "text":
            if not n["text"]:
                continue
            if out and out[-1]["type"] == "text":
                out[-1] = _text(out[-1]["text"] + n["text"])
                continue
        out.append(n)
    return out


def _inlines(nodes: list[SyntaxTreeNode]) -> list[Node]:
    out: list[Node] = []
    for n in nodes:
        kind = n.type
        if kind == "softbreak":
            out.append(_text(" "))
        elif kind == "hardbreak":
            out.append({"type": "break"})
        elif kind == "code_inline":
            out.append({"type": "code", "text": n.content})
        elif kind in ("strong", "em"):
            children = _inlines(n.children)
            if children:
                out.append(
                    {
                        "type": "strong" if kind == "strong" else "emph",
                        "inlines": children,
                    }
                )
        elif kind == "link":
            children = _inlines(n.children)
            url = str(n.attrs.get("href", ""))
            if url.lower().startswith(_LINK_SCHEMES) and children:
                out.append({"type": "link", "url": url, "inlines": children})
            else:
                out.extend(children)
        elif kind == "image":
            out.append(_text(_plain(n) or str(n.attrs.get("alt", ""))))
        else:
            out.append(_text(_plain(n)))
    return _merge(out)


def _inline_children(node: SyntaxTreeNode) -> list[Node]:
    """Inlines of a paragraph/heading (its single ``inline`` child's children)."""
    return _inlines([c for inline in node.children for c in inline.children])


def _blocks(nodes: list[SyntaxTreeNode]) -> list[Node]:
    out: list[Node] = []
    for n in nodes:
        kind = n.type
        if kind == "paragraph":
            inlines = _inline_children(n)
            if inlines:
                out.append({"type": "paragraph", "inlines": inlines})
        elif kind == "heading":
            inlines = _inline_children(n)
            if inlines:
                level = min(int(n.tag[1:]), MAX_HEADING_LEVEL)
                out.append({"type": "heading", "level": level, "inlines": inlines})
        elif kind in ("bullet_list", "ordered_list"):
            out.append(
                {
                    "type": "list",
                    "ordered": kind == "ordered_list",
                    "start": int(n.attrs.get("start", 1)),
                    "items": [_blocks(item.children) for item in n.children],
                }
            )
        elif kind == "blockquote":
            out.append({"type": "quote", "blocks": _blocks(n.children)})
        elif kind in ("fence", "code_block"):
            out.append({"type": "code", "text": n.content.rstrip("\n")})
        elif kind == "hr":
            out.append({"type": "rule"})
        else:
            text = _plain(n).strip()
            if text:
                out.append({"type": "paragraph", "inlines": [_text(text)]})
    return out


def parse_markdown(source: str) -> list[Node]:
    """Parse CommonMark ``source`` into the block tree described above."""
    return _blocks(SyntaxTreeNode(_PARSER.parse(source or "")).children)
