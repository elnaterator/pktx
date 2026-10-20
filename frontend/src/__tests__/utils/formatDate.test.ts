import { describe, it, expect } from 'vitest'
import { formatDate } from '../../utils/formatDate'

describe('formatDate', () => {
  it('keeps a date-only value on its calendar day in any time zone', () => {
    const expected = new Date(2026, 9, 3).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
    expect(formatDate('2026-10-03')).toBe(expected)
  })

  it('formats timestamps as instants', () => {
    const iso = '2026-10-03T12:00:00Z'
    expect(formatDate(iso)).toBe(
      new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }),
    )
  })
})
