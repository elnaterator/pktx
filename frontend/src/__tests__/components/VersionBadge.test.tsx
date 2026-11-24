import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

const SHA = 'b'.repeat(40)

async function renderWith(version: string, sha = SHA) {
  for (const [name, content] of [['pktx-version', version], ['pktx-git-sha', sha]]) {
    const el = document.createElement('meta')
    el.name = name
    el.content = content
    document.head.appendChild(el)
  }
  // The badge reads the meta tags once at module load.
  vi.resetModules()
  const { default: VersionBadge } = await import('../../components/VersionBadge')
  return render(<VersionBadge />)
}

afterEach(() => {
  document.head.querySelectorAll('meta[name^="pktx-"]').forEach((el) => el.remove())
})

describe('VersionBadge', () => {
  it('links a release version to its GitHub release, sha in the tooltip', async () => {
    await renderWith('v2026.11.24')
    const link = screen.getByRole('link', { name: 'v2026.11.24' })
    expect(link).toHaveAttribute('href', 'https://github.com/elnaterator/pktx/releases/tag/v2026.11.24')
    expect(link.closest('[title]')).toHaveAttribute('title', `pktx v2026.11.24 (${SHA})`)
  })

  it('shows dev builds as plain text', async () => {
    await renderWith('dev-81fe87b')
    expect(screen.getByText('dev-81fe87b')).toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })
})
