import { describe, it, expect } from 'vitest'
import { buildAssistants, EXAMPLE_PROMPTS } from '../../../components/connect/connectAssistants'

const URL_ = 'https://pktx.test/mcp'
const assistants = buildAssistants(URL_)

describe('connectAssistants data', () => {
  it('has unique ids', () => {
    const ids = assistants.map((a) => a.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it.each(assistants)('$name has steps, https docs, and a valid verified date', (a) => {
    expect(a.steps.length).toBeGreaterThan(0)
    expect(new URL(a.docsUrl).protocol).toBe('https:')
    expect(a.lastVerified).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(Number.isNaN(Date.parse(a.lastVerified))).toBe(false)
  })

  it('embeds the MCP URL in every snippet', () => {
    for (const a of assistants) {
      if (a.snippet) expect(a.snippet.text).toContain(URL_)
    }
  })

  it('builds a Cursor deep link with a base64 url config', () => {
    const cursor = assistants.find((a) => a.id === 'cursor')!
    const link = new URL(cursor.install!.url)
    expect(link.protocol).toBe('cursor:')
    expect(link.searchParams.get('name')).toBe('pktx')
    expect(JSON.parse(atob(link.searchParams.get('config')!))).toEqual({ url: URL_ })
  })

  it('builds a VS Code install link with an http server config', () => {
    const vscode = assistants.find((a) => a.id === 'github-copilot')!
    const url = vscode.install!.url
    expect(url.startsWith('vscode:mcp/install?')).toBe(true)
    expect(JSON.parse(decodeURIComponent(url.split('?')[1]))).toEqual({
      name: 'pktx',
      type: 'http',
      url: URL_,
    })
  })

  it('has a few example prompts', () => {
    expect(EXAMPLE_PROMPTS.length).toBeGreaterThanOrEqual(3)
    expect(EXAMPLE_PROMPTS.length).toBeLessThanOrEqual(4)
  })
})
