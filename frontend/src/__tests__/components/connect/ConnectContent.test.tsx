/**
 * Tests the shared connect content: URL hero, prompts, assistant picker,
 * per-assistant details, and remembered selection.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ConnectContent, { ASSISTANT_STORAGE_KEY } from '../../../components/connect/ConnectContent'
import { EXAMPLE_PROMPTS } from '../../../components/connect/connectAssistants'

const MCP_URL = 'https://pktx.test/mcp'

async function pick(name: RegExp) {
  await userEvent.click(screen.getByRole('button', { name: /assistant/i }))
  await userEvent.click(within(screen.getByRole('listbox')).getByRole('option', { name }))
}

describe('ConnectContent', () => {
  beforeEach(() => {
    localStorage.clear()
    Object.defineProperty(window, 'location', {
      value: new URL('https://pktx.test/'),
      writable: true,
    })
  })

  it('puts the MCP URL first with a copy button', async () => {
    const user = userEvent.setup()
    render(<ConnectContent />)
    const url = screen.getByText(MCP_URL)
    const firstHeading = screen.getAllByRole('heading')[0]
    expect(firstHeading).toHaveTextContent(/mcp server url/i)
    expect(firstHeading.compareDocumentPosition(url) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Copy MCP URL' }))
    expect(await navigator.clipboard.readText()).toBe(MCP_URL)
    expect(screen.getByText('Copied to clipboard')).toBeInTheDocument()
  })

  it('lists copyable example prompts', async () => {
    const user = userEvent.setup()
    render(<ConnectContent />)
    for (const prompt of EXAMPLE_PROMPTS) {
      expect(screen.getByText(new RegExp(prompt.slice(0, 20)))).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: `Copy prompt: ${EXAMPLE_PROMPTS[1]}` }))
    expect(await navigator.clipboard.readText()).toBe(EXAMPLE_PROMPTS[1])
  })

  it('defaults to Claude and names it a connector', () => {
    render(<ConnectContent />)
    expect(screen.getByRole('button', { name: /assistant claude$/i })).toBeInTheDocument()
    expect(screen.getByText(/Claude calls this a/)).toHaveTextContent('connector')
    expect(screen.getByText(/Customize → Connectors/)).toBeInTheDocument()
  })

  it('shows ChatGPT / Codex MCP steps with Streamable HTTP and Authenticate', async () => {
    render(<ConnectContent />)
    await pick(/chatgpt \/ codex/i)
    expect(screen.getByText(/ChatGPT \/ Codex calls this an/)).toHaveTextContent('MCP server')
    expect(screen.getByText(/Settings → Plugins → MCPs → Add/)).toBeInTheDocument()
    expect(screen.getByText(/choose Streamable HTTP/)).toBeInTheDocument()
    expect(screen.getByText(/Click Authenticate/)).toBeInTheDocument()
    expect(screen.getByText('~/.codex/config.toml')).toBeInTheDocument()
  })

  it('shows ChatGPT web plugin steps and plan notes', async () => {
    render(<ConnectContent />)
    await pick(/chatgpt web/i)
    expect(screen.getByText(/ChatGPT web calls this a/)).toHaveTextContent('plugin')
    expect(screen.getByText(/Add custom MCP server/)).toBeInTheDocument()
    expect(screen.getByText(/Pro connects read-only/)).toBeInTheDocument()
  })

  it('shows a one-click install link for Cursor', async () => {
    render(<ConnectContent />)
    await pick(/cursor/i)
    expect(screen.getByRole('link', { name: /install in cursor/i }).getAttribute('href')).toMatch(
      /^cursor:\/\/anysphere\.cursor-deeplink\/mcp\/install\?name=pktx&config=/,
    )
    expect(screen.getByText('~/.cursor/mcp.json')).toBeInTheDocument()
  })

  it('shows a copyable command for Claude Code and no install link', async () => {
    const user = userEvent.setup()
    render(<ConnectContent />)
    await pick(/claude code/i)
    expect(screen.queryByRole('link', { name: /install in/i })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Copy Claude Code config' }))
    expect(await navigator.clipboard.readText()).toBe(
      `claude mcp add --transport http pktx ${MCP_URL}`,
    )
  })

  it('shows the verified date and vendor docs link', () => {
    render(<ConnectContent />)
    expect(screen.getByText(/^Verified/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /claude docs/i })).toHaveAttribute(
      'href',
      expect.stringMatching(/^https:\/\/support\.claude\.com\//),
    )
  })

  it('remembers the picked assistant', async () => {
    const { unmount } = render(<ConnectContent />)
    await pick(/^zed/i)
    expect(localStorage.getItem(ASSISTANT_STORAGE_KEY)).toBe('"zed"')
    unmount()
    render(<ConnectContent />)
    expect(screen.getByRole('button', { name: /assistant zed$/i })).toBeInTheDocument()
  })

  it('falls back to the default for an unknown stored assistant', () => {
    localStorage.setItem(ASSISTANT_STORAGE_KEY, '"windsurf"')
    render(<ConnectContent />)
    expect(screen.getByRole('button', { name: /assistant claude$/i })).toBeInTheDocument()
  })
})
