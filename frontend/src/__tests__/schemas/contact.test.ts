import { describe, it, expect } from 'vitest'
import { contactCreateSchema, contactUpdateSchema } from '../../schemas/contact'

describe('contactCreateSchema', () => {
  it('accepts valid minimal input', () => {
    const result = contactCreateSchema.safeParse({ name: 'Alice' })
    expect(result.success).toBe(true)
  })

  it('requires name', () => {
    const result = contactCreateSchema.safeParse({ name: '' })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues[0].path).toContain('name')
    }
  })

  it('trims name', () => {
    const result = contactCreateSchema.safeParse({ name: '  Alice  ' })
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.name).toBe('Alice')
  })

  it('validates email format', () => {
    const result = contactCreateSchema.safeParse({ name: 'Alice', email: 'not-an-email' })
    expect(result.success).toBe(false)
  })

  it('accepts valid email', () => {
    const result = contactCreateSchema.safeParse({ name: 'Alice', email: 'alice@example.com' })
    expect(result.success).toBe(true)
  })

  it('normalizes empty email to undefined', () => {
    const result = contactCreateSchema.safeParse({ name: 'Alice', email: '' })
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.email).toBeUndefined()
  })

  it('validates linkedin_url format', () => {
    const result = contactCreateSchema.safeParse({ name: 'Alice', linkedin_url: 'not-a-url' })
    expect(result.success).toBe(false)
  })

  it.each(['javascript:alert(1)', 'ftp://example.com', 'vbscript:msgbox(1)'])(
    'rejects non-http(s) linkedin_url %j',
    (linkedin_url) => {
      const result = contactCreateSchema.safeParse({ name: 'Alice', linkedin_url })
      expect(result.success).toBe(false)
    },
  )

  it('accepts https linkedin_url', () => {
    const result = contactCreateSchema.safeParse({ name: 'Alice', linkedin_url: 'https://linkedin.com/in/alice' })
    expect(result.success).toBe(true)
  })

  it('normalizes empty linkedin_url to undefined', () => {
    const result = contactCreateSchema.safeParse({ name: 'Alice', linkedin_url: '' })
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.linkedin_url).toBeUndefined()
  })

  it('defaults tags to empty array', () => {
    const result = contactCreateSchema.safeParse({ name: 'Alice' })
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.tags).toEqual([])
  })
})

describe('contactUpdateSchema', () => {
  it('all fields optional', () => {
    const result = contactUpdateSchema.safeParse({})
    expect(result.success).toBe(true)
  })

  it('still validates email when provided', () => {
    const result = contactUpdateSchema.safeParse({ email: 'bad' })
    expect(result.success).toBe(false)
  })
})
