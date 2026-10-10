import { describe, it, expect } from 'vitest'
import {
  workExperienceSchema,
  educationSchema,
  skillSchema,
  contactInfoSchema,
  buildEntrySchema,
  profileSchema,
} from '../../schemas/resumeEntry'
import type { SectionField } from '../../types'

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

describe('contactInfoSchema', () => {
  it('accepts empty object', () => {
    const result = contactInfoSchema.safeParse({})
    expect(result.success).toBe(true)
  })

  it('validates email', () => {
    const result = contactInfoSchema.safeParse({ email: 'bad' })
    expect(result.success).toBe(false)
  })

  it('accepts valid email', () => {
    const result = contactInfoSchema.safeParse({ email: 'alice@example.com' })
    expect(result.success).toBe(true)
  })

  it('validates linkedin URL', () => {
    const result = contactInfoSchema.safeParse({ linkedin: 'not-a-url' })
    expect(result.success).toBe(false)
  })

  it.each(['linkedin', 'website', 'github'] as const)('rejects javascript: and ftp: for %s', (field) => {
    expect(contactInfoSchema.safeParse({ [field]: 'javascript:alert(1)' }).success).toBe(false)
    expect(contactInfoSchema.safeParse({ [field]: 'ftp://example.com' }).success).toBe(false)
  })

  it.each(['linkedin', 'website', 'github'] as const)('accepts https for %s', (field) => {
    const result = contactInfoSchema.safeParse({ [field]: 'https://example.com' })
    expect(result.success).toBe(true)
    if (result.success) expect(result.data[field]).toBe('https://example.com')
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

describe('profileSchema', () => {
  it('requires label and an http(s) url', () => {
    expect(profileSchema.safeParse({ label: 'GitLab', url: 'https://gitlab.com/me' }).success).toBe(true)
    expect(profileSchema.safeParse({ label: '', url: 'https://gitlab.com/me' }).success).toBe(false)
    expect(profileSchema.safeParse({ label: 'x', url: 'javascript:1' }).success).toBe(false)
  })
})
