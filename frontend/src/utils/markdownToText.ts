import remarkParse from 'remark-parse'
import { unified } from 'unified'

/** The slice of an mdast node this module reads. */
interface MdNode {
  type: string
  value?: string
  url?: string
  alt?: string | null
  ordered?: boolean | null
  start?: number | null
  children?: MdNode[]
}

const parser = unified().use(remarkParse)

const inline = (nodes: MdNode[] = []): string => nodes.map(inlineNode).join('')

function inlineNode(node: MdNode): string {
  switch (node.type) {
    case 'break':
      return '\n'
    case 'image':
      return node.alt ?? ''
    case 'link': {
      const text = inline(node.children)
      const url = node.url ?? ''
      // Plain text has no links: keep the address unless the text already is it.
      const shown = url.replace(/^mailto:/, '')
      if (!url || !text || text === url || text === shown) return text || shown
      return `${text} (${shown})`
    }
    default:
      return node.children ? inline(node.children) : (node.value ?? '')
  }
}

function listText(node: MdNode): string {
  const first = node.start ?? 1
  return (node.children ?? [])
    .map((item, i) => {
      const marker = node.ordered ? `${first + i}. ` : '- '
      const body = (item.children ?? []).map(blockText).filter(Boolean).join('\n')
      return marker + body.replace(/\n/g, `\n${' '.repeat(marker.length)}`)
    })
    .join('\n')
}

function blockText(node: MdNode): string {
  switch (node.type) {
    case 'list':
      return listText(node)
    case 'blockquote':
      return blocks(node.children)
    case 'code':
    case 'html':
      return node.value ?? ''
    case 'thematicBreak':
    case 'definition':
      return ''
    default:
      return inline(node.children)
  }
}

const blocks = (nodes: MdNode[] = []): string =>
  nodes.map(blockText).filter(Boolean).join('\n\n')

/**
 * Markdown as the plain text a reader would paste into a form: syntax
 * stripped, paragraphs a blank line apart, list items as `- ` / `1. `, and
 * links as `text (url)`. Line breaks inside a paragraph stay as typed.
 */
export function markdownToText(markdown: string): string {
  return blocks((parser.parse(markdown) as MdNode).children).trim()
}
