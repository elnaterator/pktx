import { describe, it, expect } from 'vitest'
import { commDirectionLabel } from '../../schemas/communication'

describe('commDirectionLabel', () => {
  it('uses the contact first name', () => {
    expect(commDirectionLabel('sent', 'Jane Doe')).toBe('To Jane')
    expect(commDirectionLabel('received', '  Jane  Doe ')).toBe('From Jane')
  })

  it('falls back to Outgoing / Incoming without a name', () => {
    expect(commDirectionLabel('sent')).toBe('Outgoing')
    expect(commDirectionLabel('received', '')).toBe('Incoming')
  })

  it('shows unknown values as-is', () => {
    expect(commDirectionLabel('cc', 'Jane')).toBe('cc')
  })
})
