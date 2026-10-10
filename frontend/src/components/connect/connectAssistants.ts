/**
 * Every assistant's connect instructions, as data. Vendors rename menus often —
 * when one does, fix the steps here, re-check `docsUrl`, and bump `lastVerified`.
 * No per-assistant strings belong in the components.
 */

/** What the assistant itself calls an MCP integration, so users search the right menu. */
export type AssistantNoun = 'connector' | 'plugin' | 'MCP server'

export interface Assistant {
  id: string
  name: string
  noun: AssistantNoun
  /** Ordered setup steps, plain text. */
  steps: string[]
  /** Config file or command to copy, with where it goes. */
  snippet?: { label: string; text: string }
  /** One-click deep link that opens the client's own install prompt. */
  install?: { label: string; url: string }
  notes?: string[]
  /** Vendor doc the steps were checked against. */
  docsUrl: string
  /** ISO date (YYYY-MM-DD) the steps were last checked against `docsUrl`. */
  lastVerified: string
}

export const SERVER_NAME = 'pktx'

export const EXAMPLE_PROMPTS = [
  'Tailor my default resume to this job post: <paste link>',
  'Log a win: I cut our deploy time from 40 minutes to 6.',
  "Prep me for Friday's interview — pull the application, contacts, and notes.",
  "Which applications haven't I followed up on in two weeks?",
]

const json = (value: unknown) => JSON.stringify(value, null, 2)

export function buildAssistants(mcpUrl: string): Assistant[] {
  return [
    {
      id: 'claude',
      name: 'Claude',
      noun: 'connector',
      steps: [
        'In Claude (desktop or claude.ai), open Customize → Connectors.',
        'Click + Add → Add custom connector.',
        `Name it ${SERVER_NAME}, paste the MCP URL, and click Continue.`,
        'Pick Sign in now, then finish sign-in in the browser window.',
      ],
      notes: [
        'Turn it on per chat from the + button → Connectors.',
        'Free plans allow one custom connector.',
        'Team and Enterprise: an owner adds it first under Organization settings → Connectors, then members click Connect.',
      ],
      docsUrl:
        'https://support.claude.com/en/articles/11175166-getting-started-with-custom-connectors-using-remote-mcp',
      lastVerified: '2026-10-04',
    },
    {
      id: 'chatgpt',
      name: 'ChatGPT / Codex',
      noun: 'MCP server',
      steps: [
        'In the ChatGPT desktop app (or Codex app), open Settings → Plugins → MCPs → Add.',
        `Name it ${SERVER_NAME}, choose Streamable HTTP, and paste the MCP URL. Leave the token and header fields empty.`,
        'Save, then click Restart if asked.',
        `Click Authenticate next to ${SERVER_NAME} and sign in when the browser opens.`,
        `In a chat, type /mcp to check ${SERVER_NAME} is connected.`,
      ],
      snippet: {
        label: '~/.codex/config.toml',
        text: `[mcp_servers.${SERVER_NAME}]\nurl = "${mcpUrl}"`,
      },
      notes: [
        'Older builds: Settings → MCP servers → Add server.',
        `Shares config with Codex CLI and the IDE extension, so ${SERVER_NAME} shows up there too.`,
        `Codex CLI only: codex mcp add ${SERVER_NAME} --url ${mcpUrl}, then codex mcp login ${SERVER_NAME}.`,
      ],
      docsUrl: 'https://learn.chatgpt.com/docs/extend/mcp?surface=app',
      lastVerified: '2026-10-09',
    },
    {
      id: 'chatgpt-web',
      name: 'ChatGPT web',
      noun: 'plugin',
      steps: [
        'On chatgpt.com, open Settings → Apps → Advanced settings and turn on Developer mode.',
        'Go to chatgpt.com/plugins, click +, then Add custom MCP server.',
        `Name it ${SERVER_NAME}, add a description, and paste the MCP URL under Connection.`,
        'Pick OAuth, click I understand and want to continue, then Create as a plugin. Sign in when the browser opens.',
        `In a new chat, type @ and pick ${SERVER_NAME}.`,
      ],
      notes: [
        'Web only. Writing data (logging an application, adding a win) needs a Business, Enterprise, or Edu plan; Pro connects read-only.',
        'Business: only admins and owners can use developer mode. Enterprise/Edu: an admin grants it first under Workspace Settings → Permissions & Roles → Connected Data.',
        'ChatGPT reads the description when deciding whether to use pktx — say what it holds.',
        'Older builds put this under Settings → Apps → Create, with a Scan Tools step before Create.',
      ],
      docsUrl:
        'https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt',
      lastVerified: '2026-10-09',
    },
    {
      id: 'claude-code',
      name: 'Claude Code',
      noun: 'MCP server',
      steps: [
        'Run the command below in your terminal.',
        `In Claude Code, run /mcp, pick ${SERVER_NAME}, and sign in (or run claude mcp login ${SERVER_NAME}).`,
      ],
      snippet: {
        label: 'Terminal',
        text: `claude mcp add --transport http ${SERVER_NAME} ${mcpUrl}`,
      },
      docsUrl: 'https://code.claude.com/docs/en/mcp',
      lastVerified: '2026-10-04',
    },
    {
      id: 'cursor',
      name: 'Cursor',
      noun: 'MCP server',
      steps: [
        'Click Install in Cursor, or add the config below to ~/.cursor/mcp.json.',
        `Sign in when Cursor shows ${SERVER_NAME} as needing login.`,
      ],
      install: {
        label: 'Install in Cursor',
        url: `cursor://anysphere.cursor-deeplink/mcp/install?name=${SERVER_NAME}&config=${encodeURIComponent(
          btoa(JSON.stringify({ url: mcpUrl })),
        )}`,
      },
      snippet: {
        label: '~/.cursor/mcp.json',
        text: json({ mcpServers: { [SERVER_NAME]: { url: mcpUrl } } }),
      },
      docsUrl: 'https://cursor.com/docs/context/mcp/install-links',
      lastVerified: '2026-10-04',
    },
    {
      id: 'github-copilot',
      name: 'VS Code (Copilot)',
      noun: 'MCP server',
      steps: [
        'Click Install in VS Code, or add the config below to .vscode/mcp.json.',
        `Start ${SERVER_NAME} and sign in when VS Code asks.`,
        'Use it from Copilot Chat in agent mode.',
      ],
      install: {
        label: 'Install in VS Code',
        url: `vscode:mcp/install?${encodeURIComponent(
          JSON.stringify({ name: SERVER_NAME, type: 'http', url: mcpUrl }),
        )}`,
      },
      snippet: {
        label: '.vscode/mcp.json',
        text: json({ servers: { [SERVER_NAME]: { type: 'http', url: mcpUrl } } }),
      },
      docsUrl: 'https://code.visualstudio.com/docs/copilot/customization/mcp-servers',
      lastVerified: '2026-10-04',
    },
    {
      id: 'grok-build',
      name: 'Grok Build',
      noun: 'MCP server',
      steps: [
        'Run the command below in your terminal.',
        'A browser window opens to sign in on first use.',
        'Check it with grok mcp list.',
      ],
      snippet: {
        label: 'Terminal',
        text: `grok mcp add --transport http ${SERVER_NAME} ${mcpUrl}`,
      },
      docsUrl: 'https://docs.x.ai/build/features/mcp-servers',
      lastVerified: '2026-10-04',
    },
    {
      id: 'amazon-kiro',
      name: 'Kiro',
      noun: 'MCP server',
      steps: [
        'Add the config below to ~/.kiro/settings/mcp.json (or .kiro/settings/mcp.json for one workspace).',
        'Kiro reloads it automatically. Sign in when the browser opens.',
      ],
      snippet: {
        label: '~/.kiro/settings/mcp.json',
        text: json({ mcpServers: { [SERVER_NAME]: { url: mcpUrl } } }),
      },
      docsUrl: 'https://kiro.dev/docs/mcp/configuration/',
      lastVerified: '2026-10-04',
    },
    {
      id: 'devin-desktop',
      name: 'Devin Desktop',
      noun: 'MCP server',
      steps: [
        'Open the agent panel actions menu → MCPs → Open MCP config file.',
        'Add the config below and save.',
        'Sign in when the browser opens.',
      ],
      snippet: {
        label: '~/.config/devin/mcp_config.json',
        text: json({ mcpServers: { [SERVER_NAME]: { serverUrl: mcpUrl } } }),
      },
      notes: ['Formerly Windsurf (renamed June 2026).'],
      docsUrl: 'https://docs.devin.ai/desktop/cascade/mcp',
      lastVerified: '2026-10-04',
    },
    {
      id: 'zed',
      name: 'Zed',
      noun: 'MCP server',
      steps: [
        'Open Settings → AI → MCP Servers → Add Server → Add Remote Server, or add the config below to settings.json.',
        'Sign in when Zed prompts.',
      ],
      snippet: {
        label: '~/.config/zed/settings.json',
        text: json({ context_servers: { [SERVER_NAME]: { url: mcpUrl } } }),
      },
      docsUrl: 'https://zed.dev/docs/ai/mcp',
      lastVerified: '2026-10-04',
    },
    {
      id: 'cline',
      name: 'Cline',
      noun: 'MCP server',
      steps: [
        'Click the MCP Servers icon → Remote Servers.',
        `Name it ${SERVER_NAME}, paste the MCP URL, pick Streamable HTTP, and click Add Server.`,
        'Sign in when the browser opens.',
      ],
      snippet: {
        label: 'cline_mcp_settings.json',
        text: json({ mcpServers: { [SERVER_NAME]: { type: 'streamableHttp', url: mcpUrl } } }),
      },
      docsUrl: 'https://docs.cline.bot/mcp/connecting-to-a-remote-server',
      lastVerified: '2026-10-04',
    },
  ]
}
