import { describe, it, expect } from 'vitest'
import { workExperienceSchema, educationSchema, skillSchema, contactInfoSchema } from '../../schemas/resumeEntry'

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
