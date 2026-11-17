import { describe, it, expect } from 'vitest'
import { resolveClerkPublishableKey } from '../../utils/clerkPublishableKey'

function docWith(content?: string): Document {
  const doc = document.implementation.createHTMLDocument('t')
  if (content !== undefined) {
    const meta = doc.createElement('meta')
    meta.name = 'pktx-clerk-publishable-key'
    meta.content = content
    doc.head.appendChild(meta)
  }
  return doc
}

describe('resolveClerkPublishableKey', () => {
  it('prefers the server-injected meta tag', () => {
    expect(resolveClerkPublishableKey(docWith('pk_live_srv'), 'pk_test_env')).toBe('pk_live_srv')
  })

  it('falls back to the build env when the placeholder is unfilled (vite dev)', () => {
    expect(
      resolveClerkPublishableKey(docWith('%PKTX_CLERK_PUBLISHABLE_KEY%'), 'pk_test_env'),
    ).toBe('pk_test_env')
  })

  it('falls back when the server injected nothing', () => {
    expect(resolveClerkPublishableKey(docWith(''), 'pk_test_env')).toBe('pk_test_env')
    expect(resolveClerkPublishableKey(docWith(), 'pk_test_env')).toBe('pk_test_env')
  })

  it('returns undefined when neither is set', () => {
    expect(resolveClerkPublishableKey(docWith(''), '')).toBeUndefined()
  })
})
