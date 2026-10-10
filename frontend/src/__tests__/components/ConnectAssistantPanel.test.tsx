/**
 * Tests the connect panel shell: collapse/expand, rail copy, first-visit auto-open,
 * and hiding on the full-page /connect route.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import ConnectAssistantPanel, { SEEN_STORAGE_KEY } from '../../components/ConnectAssistantPanel'

function renderPanel(path = '/') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ConnectAssistantPanel />
    </MemoryRouter>,
  )
}

function mockWideScreen(matches: boolean) {
  vi.stubGlobal('matchMedia', (query: string) => ({ matches, media: query }))
}

describe('ConnectAssistantPanel', () => {
  beforeEach(() => {
    localStorage.clear()
    Object.defineProperty(window, 'location', {
      value: new URL('https://pktx.test/'),
      writable: true,
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('starts collapsed when there is no room to auto-open', () => {
    mockWideScreen(false)
    renderPanel()
    expect(screen.getByRole('button', { name: /connect your ai assistant/i })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
  })

  it('auto-opens once for first-time users on wide screens', () => {
    mockWideScreen(true)
    const { unmount } = renderPanel()
    expect(screen.getByText('https://pktx.test/mcp')).toBeInTheDocument()
    expect(localStorage.getItem(SEEN_STORAGE_KEY)).toBe('true')
    unmount()

    renderPanel()
    expect(screen.queryByText('https://pktx.test/mcp')).not.toBeInTheDocument()
  })

  it('shows the MCP URL first when opened', async () => {
    renderPanel()
    await userEvent.click(screen.getByRole('button', { name: /connect your ai assistant/i }))
    expect(screen.getByText('https://pktx.test/mcp')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /collapse ai assistant panel/i }))
    expect(screen.queryByText('https://pktx.test/mcp')).not.toBeInTheDocument()
  })

  it('copies the MCP URL from the collapsed rail', async () => {
    const user = userEvent.setup()
    renderPanel()
    await user.click(screen.getByRole('button', { name: 'Copy MCP URL' }))
    expect(await navigator.clipboard.readText()).toBe('https://pktx.test/mcp')
  })

  it('links to the full connect page', async () => {
    renderPanel()
    await userEvent.click(screen.getByRole('button', { name: /connect your ai assistant/i }))
    expect(screen.getByRole('link', { name: /open connect page/i })).toHaveAttribute(
      'href',
      '/connect',
    )
  })

  it('renders nothing on /connect', () => {
    renderPanel('/connect')
    expect(screen.queryByRole('complementary')).not.toBeInTheDocument()
  })
})
