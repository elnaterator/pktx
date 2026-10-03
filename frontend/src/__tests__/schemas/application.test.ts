import { describe, it, expect } from 'vitest'
import { applicationCreateSchema, applicationUpdateSchema } from '../../schemas/application'

describe('applicationCreateSchema', () => {
  it('accepts valid input', () => {
    const result = applicationCreateSchema.safeParse({ company: 'Acme', position: 'Engineer' })
    expect(result.success).toBe(true)
  })

  it('requires company', () => {
    const result = applicationCreateSchema.safeParse({ company: '', position: 'Engineer' })
    expect(result.success).toBe(false)
    if (!result.success) expect(result.error.issues[0].path).toContain('company')
  })

  it('requires position', () => {
    const result = applicationCreateSchema.safeParse({ company: 'Acme', position: '' })
    expect(result.success).toBe(false)
    if (!result.success) expect(result.error.issues[0].path).toContain('position')
  })

  it('trims company and position', () => {
    const result = applicationCreateSchema.safeParse({ company: '  Acme  ', position: '  Eng  ' })
    expect(result.success).toBe(true)
    if (result.success) {
      expect(result.data.company).toBe('Acme')
      expect(result.data.position).toBe('Eng')
    }
  })

  it('validates url format', () => {
    const result = applicationCreateSchema.safeParse({ company: 'A', position: 'B', url: 'not-url' })
    expect(result.success).toBe(false)
  })

  it('normalizes empty url to undefined', () => {
    const result = applicationCreateSchema.safeParse({ company: 'A', position: 'B', url: '' })
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.url).toBeUndefined()
  })

  it.each(['javascript:alert(1)', 'JaVaScRiPt:alert(1)', 'ftp://example.com/file', 'data:text/html,x'])(
    'rejects non-http(s) url %j',
    (url) => {
      const result = applicationCreateSchema.safeParse({ company: 'A', position: 'B', url })
      expect(result.success).toBe(false)
    },
  )

  it('accepts and trims an https url', () => {
    const result = applicationCreateSchema.safeParse({ company: 'A', position: 'B', url: ' https://acme.com/job ' })
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.url).toBe('https://acme.com/job')
  })

  it('defaults status to Interested', () => {
    const result = applicationCreateSchema.safeParse({ company: 'A', position: 'B' })
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.status).toBe('Interested')
  })
})

describe('applicationUpdateSchema', () => {
  it('all fields optional', () => {
    const result = applicationUpdateSchema.safeParse({})
    expect(result.success).toBe(true)
  })
})
