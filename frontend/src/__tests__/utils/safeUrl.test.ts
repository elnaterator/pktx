import { describe, it, expect } from 'vitest'
import { isHttpUrl, safeHref } from '../../utils/safeUrl'

describe('safeHref', () => {
  it.each([
    ['http://example.com', 'http://example.com'],
    ['https://example.com/a?b=c#d', 'https://example.com/a?b=c#d'],
    ['HTTPS://Example.com', 'HTTPS://Example.com'],
    ['  https://example.com  ', 'https://example.com'],
  ])('allows %j', (input, expected) => {
    expect(safeHref(input)).toBe(expected)
  })

  it.each([
    'javascript:alert(1)',
    'JaVaScRiPt:alert(1)',
    '  javascript:alert(1)',
    '\u0000javascript:alert(1)',
    'java\tscript:alert(1)',
    'java\nscript:alert(1)',
    'data:text/html,<script>alert(1)</script>',
    'vbscript:msgbox(1)',
    'file:///etc/passwd',
    'ftp://example.com',
    '/foo',
    '//evil.example.com',
    'example.com',
    'not a url at all',
    '',
    '   ',
    null,
    undefined,
  ])('rejects %j', (input) => {
    expect(safeHref(input)).toBeUndefined()
  })

  it('rejects mailto by default', () => {
    expect(safeHref('mailto:a@example.com')).toBeUndefined()
  })

  it('allows mailto when allowMailto is set', () => {
    expect(safeHref('mailto:a@example.com', { allowMailto: true })).toBe('mailto:a@example.com')
    expect(safeHref('MAILTO:a@example.com', { allowMailto: true })).toBe('MAILTO:a@example.com')
  })

  it('still rejects script URLs when allowMailto is set', () => {
    expect(safeHref('javascript:alert(1)', { allowMailto: true })).toBeUndefined()
  })
})

describe('isHttpUrl', () => {
  it('is true only for http(s)', () => {
    expect(isHttpUrl('https://example.com')).toBe(true)
    expect(isHttpUrl('javascript:alert(1)')).toBe(false)
    expect(isHttpUrl('mailto:a@example.com')).toBe(false)
  })
})
