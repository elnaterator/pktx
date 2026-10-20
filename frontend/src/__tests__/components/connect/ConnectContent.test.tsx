/**
 * Tests the three-step connect flow: choose an assistant, add pktx, try it,
 * plus the collapsible details and remembered / linkable selection.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router'
import ConnectContent, { ASSISTANT_STORAGE_KEY, TEST_PROMPT } from '../../../components/connect/ConnectContent'

const MCP_URL = 'https://pktx.test/mcp'

let currentSearch = ''
function LocationProbe() {
  currentSearch = useLocation().search
  return null
}

function renderConnect(path = '/connect') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ConnectContent />
      <LocationProbe />
    </MemoryRouter>,
  )
}

const tiles = () => within(screen.getByRole('radiogroup', { name: /choose your assistant/i }))

async function choose(name: RegExp) {
  if (!tiles().queryByRole('radio', { name })) {
    await userEvent.click(screen.getByRole('button', { name: /^more:/i }))
  }
  await userEvent.click(tiles().getByRole('radio', { name }))
}

describe('ConnectContent', () => {
  beforeEach(() => {
    localStorage.clear()
    Object.defineProperty(window, 'location', {
      value: new URL('https://pktx.test/'),
      writable: true,
    })
  })

  it('walks through three numbered steps', () => {
    renderConnect()
    const headings = screen.getAllByRole('heading').map((h) => h.textContent)
    expect(headings).toEqual(['Choose your assistant', 'Add pktx to Claude', 'Try it'])
  })

  it('defaults to Claude, showing only the common assistants up front', () => {
    renderConnect()
    expect(tiles().getByRole('radio', { name: 'Claude' })).toHaveAttribute('aria-checked', 'true')
    expect(tiles().getAllByRole('radio').map((r) => r.textContent)).toEqual([
      'Claude',
      'ChatGPT / Codex',
      'ChatGPT web',
      'Cursor',
      'VS Code (Copilot)',
    ])
    expect(screen.getByText(/Customize → Connectors/)).toBeInTheDocument()
  })

  it('puts the MCP URL, with a copy button, in the step where you paste it', async () => {
    const user = userEvent.setup()
    renderConnect()
    const step = screen.getByText(/paste the MCP URL/).closest('li')!
    expect(within(step).getByText(MCP_URL)).toBeInTheDocument()
    await user.click(within(step).getByRole('button', { name: 'Copy MCP URL' }))
    expect(await navigator.clipboard.readText()).toBe(MCP_URL)
  })

  it('offers one test prompt to copy', async () => {
    const user = userEvent.setup()
    renderConnect()
    expect(screen.getByText(/Ask Claude:/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Copy test prompt' }))
    expect(await navigator.clipboard.readText()).toBe(TEST_PROMPT)
  })

  it('shows a one-click install and the config in the setup step for Cursor', async () => {
    renderConnect()
    await choose(/^cursor$/i)
    expect(screen.getByRole('heading', { name: 'Add pktx to Cursor' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /install in cursor/i }).getAttribute('href')).toMatch(
      /^cursor:\/\/anysphere\.cursor-deeplink\/mcp\/install\?name=pktx&config=/,
    )
    expect(screen.getByText('~/.cursor/mcp.json')).toBeVisible()
  })

  it('reveals the other assistants under More, and keeps Claude Code\'s command in setup', async () => {
    const user = userEvent.setup()
    renderConnect()
    expect(tiles().queryByRole('radio', { name: 'Claude Code' })).not.toBeInTheDocument()
    await choose(/^claude code$/i)
    expect(screen.queryByRole('link', { name: /install in/i })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Copy Claude Code config' }))
    expect(await navigator.clipboard.readText()).toBe(`claude mcp add --transport http pktx ${MCP_URL}`)
  })

  it('keeps alternatives, notes and docs under Details', async () => {
    renderConnect()
    await choose(/chatgpt \/ codex/i)
    const details = screen.getByText('Details for ChatGPT / Codex').closest('details')!
    expect(details).not.toHaveAttribute('open')
    expect(within(details).getByText('~/.codex/config.toml')).toBeInTheDocument()
    expect(within(details).getByText(/^Verified/)).toBeInTheDocument()
    expect(within(details).getByRole('link', { name: /chatgpt \/ codex docs/i })).toBeInTheDocument()
  })

  it('remembers the choice and reflects it in the URL', async () => {
    const { unmount } = renderConnect()
    await choose(/^zed$/i)
    expect(localStorage.getItem(ASSISTANT_STORAGE_KEY)).toBe('"zed"')
    expect(currentSearch).toBe('?assistant=zed')
    unmount()
    renderConnect()
    expect(tiles().getByRole('radio', { name: 'Zed' })).toHaveAttribute('aria-checked', 'true')
  })

  it('opens on the assistant named in the URL', () => {
    renderConnect('/connect?assistant=cursor')
    expect(screen.getByRole('heading', { name: 'Add pktx to Cursor' })).toBeInTheDocument()
  })

  it('falls back to Claude for an unknown assistant', () => {
    localStorage.setItem(ASSISTANT_STORAGE_KEY, '"windsurf"')
    renderConnect('/connect?assistant=nope')
    expect(screen.getByRole('heading', { name: 'Add pktx to Claude' })).toBeInTheDocument()
  })
})
