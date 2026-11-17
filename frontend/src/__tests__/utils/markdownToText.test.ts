import { describe, it, expect } from 'vitest'
import { markdownToText } from '../../utils/markdownToText'

describe('markdownToText', () => {
  it('returns an empty string for blank input', () => {
    expect(markdownToText('')).toBe('')
    expect(markdownToText('  \n\n')).toBe('')
  })

  it('strips inline syntax and keeps paragraphs a blank line apart', () => {
    expect(markdownToText('Dear **team**,\n\nI *really* like `code`.')).toBe(
      'Dear team,\n\nI really like code.',
    )
  })

  it('drops heading marks, quote marks, rules and code fences', () => {
    expect(markdownToText('# Title\n\n> quoted\n\n---\n\n```js\nlet x = 1\n```')).toBe(
      'Title\n\nquoted\n\nlet x = 1',
    )
  })

  it('keeps line breaks inside a paragraph as typed', () => {
    expect(markdownToText('Sincerely,\nJane')).toBe('Sincerely,\nJane')
    expect(markdownToText('Sincerely,  \nJane')).toBe('Sincerely,\nJane')
  })

  it('writes lists with plain markers, numbering and nesting', () => {
    expect(markdownToText('* one\n* two\n  * inner\n\n3. three\n4. four')).toBe(
      '- one\n- two\n  - inner\n\n3. three\n4. four',
    )
  })

  it('keeps a link address unless the text already is it', () => {
    expect(markdownToText('See [my site](https://example.com/me).')).toBe(
      'See my site (https://example.com/me).',
    )
    expect(markdownToText('[https://example.com](https://example.com)')).toBe('https://example.com')
    expect(markdownToText('[jane@example.com](mailto:jane@example.com)')).toBe('jane@example.com')
    expect(markdownToText('[Mail me](mailto:jane@example.com)')).toBe('Mail me (jane@example.com)')
  })

  it('uses alt text for images and leaves raw HTML as text', () => {
    expect(markdownToText('![a logo](https://example.com/l.png)')).toBe('a logo')
    expect(markdownToText('a <b>bold</b> move')).toBe('a <b>bold</b> move')
  })

  it('leaves characters that only look like markdown alone', () => {
    expect(markdownToText('2 * 3 = 6, snake_case_name, C#')).toBe('2 * 3 = 6, snake_case_name, C#')
  })
})
