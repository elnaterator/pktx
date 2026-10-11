import { describe, it, expect } from 'vitest'
import {
  workExperienceSchema,
  educationSchema,
  skillSchema,
  buildContactSchema,
  buildEntrySchema,
} from '../../schemas/resumeEntry'
import type { ContactKind, SectionField } from '../../types'

describe('workExperienceSchema', () => {
  it('accepts valid input', () => {
    const result = workExperienceSchema.safeParse({ title: 'Engineer', company: 'Acme' })
    expect(result.success).toBe(true)
  })

  it('requires title', () => {
    const result = workExperienceSchema.safeParse({ title: '', company: 'Acme' })
    expect(result.success).toBe(false)
  })

  it('requires company', () => {
    const result = workExperienceSchema.safeParse({ title: 'Engineer', company: '' })
    expect(result.success).toBe(false)
  })

  it('defaults highlights to empty array', () => {
    const result = workExperienceSchema.safeParse({ title: 'Engineer', company: 'Acme' })
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.highlights).toEqual([])
  })
})

describe('educationSchema', () => {
  it('accepts valid input', () => {
    const result = educationSchema.safeParse({ institution: 'MIT', degree: 'BS' })
    expect(result.success).toBe(true)
  })

  it('requires institution', () => {
    const result = educationSchema.safeParse({ institution: '', degree: 'BS' })
    expect(result.success).toBe(false)
  })

  it('requires degree', () => {
    const result = educationSchema.safeParse({ institution: 'MIT', degree: '' })
    expect(result.success).toBe(false)
  })
})

describe('skillSchema', () => {
  it('accepts valid input', () => {
    const result = skillSchema.safeParse({ name: 'TypeScript' })
    expect(result.success).toBe(true)
  })

  it('requires name', () => {
    const result = skillSchema.safeParse({ name: '' })
    expect(result.success).toBe(false)
  })

  it('normalizes empty category to undefined', () => {
    const result = skillSchema.safeParse({ name: 'TypeScript', category: '' })
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.category).toBeUndefined()
  })
})

describe('buildContactSchema', () => {
  const kinds: Record<string, ContactKind> = { email: 'email', github: 'url', website: 'url' }
  const schema = buildContactSchema((key) => kinds[key.toLowerCase()] ?? 'text')

  it('accepts an empty object and defaults fields', () => {
    const r = schema.safeParse({})
    expect(r.success).toBe(true)
    if (r.success) expect(r.data.fields).toEqual([])
  })

  it('validates email values', () => {
    expect(schema.safeParse({ fields: [{ key: 'Email', value: 'bad' }] }).success).toBe(false)
    expect(schema.safeParse({ fields: [{ key: 'Email', value: 'a@b.co' }] }).success).toBe(true)
  })

  it.each(['javascript:alert(1)', 'ftp://example.com'])('rejects %s for a URL key', (value) => {
    expect(schema.safeParse({ fields: [{ key: 'GitHub', value }] }).success).toBe(false)
  })

  it('adds https:// to bare hosts for URL keys only', () => {
    const r = schema.safeParse({
      fields: [
        { key: 'GitHub', value: 'github.com/me' },
        { key: 'Pronouns', value: 'github.com/me' },
      ],
    })
    expect(r.success).toBe(true)
    if (r.success) {
      expect(r.data.fields[0].value).toBe('https://github.com/me')
      expect(r.data.fields[1].value).toBe('github.com/me')
    }
  })

  it('requires a key and a value', () => {
    expect(schema.safeParse({ fields: [{ key: '', value: 'x' }] }).success).toBe(false)
    expect(schema.safeParse({ fields: [{ key: 'Pronouns', value: '  ' }] }).success).toBe(false)
  })

  it('rejects duplicate keys case-insensitively', () => {
    const r = schema.safeParse({
      fields: [
        { key: 'Pronouns', value: 'a' },
        { key: 'pronouns', value: 'b' },
      ],
    })
    expect(r.success).toBe(false)
  })

  it('caps the number of details', () => {
    const fields = Array.from({ length: 31 }, (_, i) => ({ key: `k${i}`, value: 'v' }))
    expect(schema.safeParse({ fields }).success).toBe(false)
  })
})

describe('buildEntrySchema', () => {
  const fields = [
    { name: 'name', label: 'Name', widget: 'text', required: true },
    { name: 'url', label: 'Url', widget: 'url', required: false },
    { name: 'homepage', label: 'Homepage', widget: 'url', required: true },
    { name: 'description', label: 'Description', widget: 'textarea', required: false },
    { name: 'highlights', label: 'Highlights', widget: 'bullets', required: false },
  ] as SectionField[]
  const schema = buildEntrySchema(fields)

  it('accepts a minimal valid entry and defaults bullets', () => {
    const r = schema.safeParse({ name: ' X ', homepage: 'https://a.com' })
    expect(r.success).toBe(true)
    if (r.success) {
      expect(r.data.name).toBe('X')
      expect(r.data.highlights).toEqual([])
    }
  })

  it('rejects missing required fields', () => {
    const r = schema.safeParse({ name: '', homepage: '' })
    expect(r.success).toBe(false)
  })

  it('rejects non-http(s) urls in optional and required url fields', () => {
    expect(schema.safeParse({ name: 'x', homepage: 'javascript:alert(1)' }).success).toBe(false)
    expect(
      schema.safeParse({ name: 'x', homepage: 'https://a.com', url: 'ftp://a.com' }).success,
    ).toBe(false)
  })

  it('treats an empty optional url as absent', () => {
    const r = schema.safeParse({ name: 'x', homepage: 'https://a.com', url: '' })
    expect(r.success).toBe(true)
  })
})
