import { describe, it, expect } from 'vitest'
import {
  PARTIAL_DATE,
  basicsSchema,
  buildEntrySchema,
  withScheme,
} from '../../schemas/resumeEntry'
import type { SectionField } from '../../types'

describe('withScheme', () => {
  it('adds https:// to bare hosts only', () => {
    expect(withScheme('github.com/me')).toBe('https://github.com/me')
    expect(withScheme(' http://a.io ')).toBe('http://a.io')
    expect(withScheme('//cdn.io/x')).toBe('//cdn.io/x')
  })
})

describe('PARTIAL_DATE', () => {
  it.each(['2024', '2024-03', '2024-03-05'])('accepts %s', (d) => {
    expect(PARTIAL_DATE.test(d)).toBe(true)
  })
  it.each(['24', 'March 2024', '2024-13', '2024/03', '2024-3', '03/2024', ''])(
    'rejects %s',
    (d) => {
      expect(PARTIAL_DATE.test(d)).toBe(false)
    },
  )
})

describe('buildEntrySchema', () => {
  const fields: SectionField[] = [
    { name: 'position', label: 'Position', widget: 'text' },
    { name: 'url', label: 'URL', widget: 'url' },
    { name: 'startDate', label: 'Start date', widget: 'date' },
    { name: 'summary', label: 'Summary', widget: 'textarea' },
    { name: 'keywords', label: 'Technologies', widget: 'tags' },
    { name: 'highlights', label: 'Highlights', widget: 'bullets' },
  ]
  const schema = buildEntrySchema(fields, 'position')

  it('accepts a minimal entry, trims it and defaults bullets', () => {
    const r = schema.safeParse({ position: ' Dev ' })
    expect(r.success).toBe(true)
    if (r.success) {
      expect(r.data.position).toBe('Dev')
      expect(r.data.highlights).toEqual([])
      expect(r.data.url).toBeUndefined()
    }
  })

  it('requires only the primary field', () => {
    const r = schema.safeParse({ position: '' })
    expect(r.success).toBe(false)
    if (!r.success) expect(r.error.issues[0].message).toBe('Position is required')
  })

  it('validates partial ISO dates and treats blank as absent', () => {
    expect(schema.safeParse({ position: 'x', startDate: '2024-03' }).success).toBe(true)
    expect(schema.safeParse({ position: 'x', startDate: '' }).success).toBe(true)
    expect(schema.safeParse({ position: 'x', startDate: 'March 2024' }).success).toBe(false)
  })

  it('adds https:// to bare hosts and rejects non-http(s) urls', () => {
    const ok = schema.safeParse({ position: 'x', url: 'github.com/me' })
    expect(ok.success).toBe(true)
    if (ok.success) expect(ok.data.url).toBe('https://github.com/me')
    for (const url of ['javascript:alert(1)', 'ftp://a.com']) {
      expect(schema.safeParse({ position: 'x', url }).success).toBe(false)
    }
  })

  it('treats an empty optional url as absent', () => {
    const r = schema.safeParse({ position: 'x', url: '' })
    expect(r.success).toBe(true)
  })
})

describe('basicsSchema', () => {
  const ok = (v: object) => basicsSchema.safeParse({ profiles: [], ...v })

  it('accepts an empty form', () => {
    expect(ok({}).success).toBe(true)
  })

  it('validates email', () => {
    expect(ok({ email: 'bad' }).success).toBe(false)
    expect(ok({ email: 'a@b.co' }).success).toBe(true)
    expect(ok({ email: '' }).success).toBe(true)
  })

  it('normalizes the website and rejects unsafe schemes', () => {
    const r = ok({ url: 'janedoe.dev' })
    expect(r.success && r.data.url).toBe('https://janedoe.dev')
    expect(ok({ url: 'javascript:alert(1)' }).success).toBe(false)
  })

  it('requires a network on each profile and validates its url', () => {
    expect(ok({ profiles: [{ network: '', url: 'github.com/me' }] }).success).toBe(false)
    expect(ok({ profiles: [{ network: 'GitHub', url: 'ftp://x.io' }] }).success).toBe(false)
    const r = ok({ profiles: [{ network: 'GitHub', url: 'github.com/me', profileId: 'p1' }] })
    expect(r.success && r.data.profiles[0]).toMatchObject({
      network: 'GitHub',
      url: 'https://github.com/me',
      profileId: 'p1',
    })
  })

  it('caps the number of profiles', () => {
    const profiles = Array.from({ length: 31 }, () => ({ network: 'N' }))
    expect(ok({ profiles }).success).toBe(false)
  })
})
