import { describe, it, expect } from 'vitest'
import { resolveAppVersion } from '../../utils/appVersion'

function docWith(meta: Record<string, string>): Document {
  const doc = document.implementation.createHTMLDocument('t')
  for (const [name, content] of Object.entries(meta)) {
    const el = doc.createElement('meta')
    el.name = name
    el.content = content
    doc.head.appendChild(el)
  }
  return doc
}

const SHA = 'a'.repeat(40)

describe('resolveAppVersion', () => {
  it('reads a release version and links its GitHub release', () => {
    expect(resolveAppVersion(docWith({ 'pktx-version': 'v2026.11.24.1', 'pktx-git-sha': SHA }))).toEqual({
      version: 'v2026.11.24.1',
      sha: SHA,
      releaseUrl: 'https://github.com/elnaterator/pktx/releases/tag/v2026.11.24.1',
    })
  })

  it('does not link dev builds', () => {
    const v = resolveAppVersion(docWith({ 'pktx-version': 'dev-81fe87b', 'pktx-git-sha': SHA }))
    expect(v.version).toBe('dev-81fe87b')
    expect(v.releaseUrl).toBeUndefined()
  })

  it('treats unfilled placeholders (vite dev) as local', () => {
    expect(
      resolveAppVersion(docWith({ 'pktx-version': '%PKTX_VERSION%', 'pktx-git-sha': '%PKTX_GIT_SHA%' })),
    ).toEqual({ version: 'local', sha: '', releaseUrl: undefined })
  })

  it('treats missing or empty tags as local', () => {
    expect(resolveAppVersion(docWith({})).version).toBe('local')
    expect(resolveAppVersion(docWith({ 'pktx-version': '' })).version).toBe('local')
  })
})
