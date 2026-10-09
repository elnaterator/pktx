---
roadmap_id: 030
issue: n/a
---

# Plan: 030 MCP connect experience that pops

Branch: `feat/030-mcp-connect-ux`
Notes: [research/mcp-connect-ux.md](../../research/mcp-connect-ux.md)

## Overview

Connect panel (`components/ConnectAssistantPanel.tsx`, mounted app-wide in `App.tsx` as
left rail) = front door to core value. Today: native `<select>`, steps hardcoded in JSX,
URL buried in per-assistant snippet, pitch at bottom, no icons, wrong/missing noun per
assistant, steps drift (026 patched ChatGPT rename by hand).

In scope:
- Plain MCP URL first, big mono, one-click copy — visible in collapsed rail too (copy icon).
- Value pitch: 3–4 catchy example prompts, each copyable.
- Custom listbox assistant picker w/ icons; remembers last pick (localStorage, try/catch).
- Per assistant: noun badge ("connector" / "app" / "MCP server"), ordered steps, snippet,
  one-click install link where vendor supports, `lastVerified` date.
- All assistant data in one data file (`connectAssistants.ts`), no JSX — updates = one-line diff.
- Visual pop: accent card, theme tokens (009), dark mode + mobile clean.
- `/connect` route rendering same content full-page, linkable from README.

## Acceptance criteria

- [x] Opened panel: first element under header = `<origin>/mcp` URL + Copy button; copy writes exact URL.
- [x] Collapsed rail exposes copy-URL action (icon button, accessible label).
- [x] 3–4 example prompts render, each with copy action.
- [x] Picker = ARIA listbox (button + `role="listbox"` / `role="option"`), keyboard nav (↑/↓/Home/End/Enter/Esc, type-ahead optional), icon per assistant.
- [x] Selected assistant persists across reloads (localStorage key `pktx.connect.assistant`); bad/unknown stored id falls back to default; storage throwing doesn't break render.
- [x] Each assistant shows noun badge, numbered steps, snippet (if any) w/ copy, install link (if any), "Verified <date>".
- [x] Install links: Cursor (`cursor://anysphere.cursor-deeplink/mcp/install?name=pktx&config=<base64>`), VS Code/Copilot (`vscode:mcp/install?<urlencoded json>`); Claude Code = copyable `claude mcp add` command. Each link verified vs vendor docs before ship.
- [x] All steps re-verified against vendor docs on build date; `lastVerified` set per entry; unverifiable assistant dropped or flagged rather than guessed.
- [x] Assistant data lives only in `components/connect/connectAssistants.ts`; panel + page contain no per-assistant strings.
- [x] `/connect` route renders full-page version; panel header + README link to it (no top-nav item — nav already at 6 items, tight on mobile).
- [x] Theme tokens only (app is dark-only — no light theme exists) + 375px width: no overflow; open panel goes full-width under 540px.
- [x] `make check` green; panel tests updated + new tests for picker, persistence, install links, data-file shape.

## Open questions

- [x] Logos — _done: monochrome brand marks for every assistant in `AssistantIcon.tsx` — Simple Icons (CC0) for Claude, Claude Code, Cursor, Copilot, Zed, Cline; LobeHub Icons (MIT, `@lobehub/icons-static-svg` 1.95.1, paths inlined, no dep) for OpenAI (both ChatGPT entries), Grok, Kiro, Devin. No lucide fallbacks left._
- [x] Panel placement — _proposed: keep app-wide collapsible rail (existing behavior) + add `/connect` page; rail and page share one `ConnectContent` component._
- [x] Default collapsed state — _proposed: keep collapsed by default, but auto-open once for first-time users (no stored assistant pick) so pitch + URL seen at least once._

## Design

```
components/connect/
  connectAssistants.ts   # data only: Assistant[] built from mcpUrl
  icons.tsx              # AssistantIcon({ id })
  AssistantPicker.tsx    # custom listbox
  CopyButton.tsx         # shared copy w/ "Copied" state (aria-live)
  ConnectContent.tsx     # URL hero, pitch, picker, steps — used by panel + page
  ConnectContent.module.css
components/ConnectAssistantPanel.tsx  # rail shell only (collapse, rail copy icon)
pages/connect/ConnectView.tsx         # full-page shell
hooks/useStoredState.ts               # localStorage-backed state, try/catch
```

Data shape:

```ts
type Noun = 'connector' | 'app' | 'MCP server'
interface Assistant {
  id: string
  name: string
  noun: Noun
  steps: string[]                 // ordered, plain text
  snippet?: { label: string; text: string }   // file path / command label
  installUrl?: string             // deep link, opens client
  notes?: string[]
  docsUrl: string                 // vendor source used to verify
  lastVerified: string            // ISO date
}
export function buildAssistants(mcpUrl: string): Assistant[]
export const EXAMPLE_PROMPTS: string[]
```

Keep `MCP_SERVER_URL` derivation (origin + `/mcp`, `VITE_MCP_SERVER_URL` override) in one
helper (`connect/mcpUrl.ts`). Clipboard failure → toast error (010 provider) instead of
silent swallow. Copy-done feedback via `aria-live="polite"`.

Assistants (keep current list, re-verify each): Claude (desktop/web — one entry, custom
connector), ChatGPT, Claude Code, Grok Build, Cursor, GitHub Copilot (VS Code), Amazon
Kiro, Windsurf, Zed, Cline.

**Touches:**
- `frontend/src/components/connect/*` (new)
- `frontend/src/components/ConnectAssistantPanel.tsx` (mod — slim to shell)
- `frontend/src/components/ConnectAssistantPanel.module.css` (mod — shell only)
- `frontend/src/pages/connect/ConnectView.tsx` + `.module.css` (new)
- `frontend/src/hooks/useStoredState.ts` (new)
- `frontend/src/router.tsx` (mod — `/connect`)
- `frontend/src/components/Navigation.tsx` (mod — Connect link, if fits nav pattern)
- `frontend/src/__tests__/components/ConnectAssistantPanel.test.tsx` (mod)
- `frontend/src/__tests__/components/connect/*.test.tsx` (new)
- `README.md` (mod — Connect tab line, link `/connect`, trim duplicated per-client snippets)
- `AGENTS.md` (mod — note data file location)

## Steps

- [x] Re-verify every assistant flow vs vendor docs (context7 / web); record `docsUrl` + date; confirm deep-link formats for Cursor + VS Code.
- [x] Add `mcpUrl.ts`, `connectAssistants.ts` (data + example prompts), unit test data shape (unique ids, valid ISO dates, install URLs parse).
- [x] Add `useStoredState` hook + test (throwing storage, unknown value fallback).
- [x] Add `CopyButton` (toast on failure, aria-live) + test.
- [x] Add `AssistantIcon.tsx`.
- [x] Add `AssistantPicker` listbox + keyboard tests.
- [x] Build `ConnectContent`: URL hero → pitch prompts → picker → noun badge + steps + snippet + install link + verified date → read/write callout.
- [x] Slim `ConnectAssistantPanel` to shell; rail copy-URL icon; first-visit auto-open.
- [x] Add `/connect` route + `ConnectView`; full-page link in panel header; panel hidden on `/connect`.
- [x] Styling: accent card via theme tokens; check light/dark/mobile in browser pane.
- [x] Update existing panel tests; README + AGENTS.md.
- [x] `make check`.

## As built (deviations)

- File names: `AssistantIcon.tsx` (not `icons.tsx`), one `Connect.module.css` for all connect pieces, `mcpUrl.ts` helper.
- Docs re-check 2026-10-04 changed content: Claude menu is now **Customize → Connectors → + Add → Add custom connector** (one "Claude" entry for desktop + web, was "Claude Desktop"); **Windsurf renamed Devin Desktop** (June 2026), config moved to `~/.config/devin/mcp_config.json`; Kiro snippet now user-level `~/.kiro/settings/mcp.json`; Copilot entry labelled "VS Code (Copilot)" with `vscode:mcp/install` link. ChatGPT re-verified 2026-10-09 (help page via browser pane; WebFetch 403s): new flow chatgpt.com/plugins → + → Add custom MCP server → Create as a plugin, use via @; noun is now **plugin** (not "app"); write actions need Business/Enterprise/Edu, Pro is read-only, Plus not listed. README ChatGPT steps updated to match.
- ChatGPT split into two entries (user feedback 2026-10-09): **ChatGPT / Codex** (desktop app, id `chatgpt`): Settings → Plugins → MCPs → Add → Streamable HTTP → Authenticate (learn.chatgpt.com/docs/extend/mcp, shares `~/.codex/config.toml` with Codex). OAuth via CIMD/DCR over loopback `http://127.0.0.1:<port>/callback/<id>` — already allowed by `DEFAULT_LOCALHOST_PATTERNS`, no backend change. **ChatGPT web** (`chatgpt-web`) keeps the plugin flow.
- Stored ids from the old panel (`claude-desktop`, `windsurf`) fall back to default.
- First-visit auto-open only at ≥1024px (panel overlays small screens); `pktx.connect.seen` flag.
- Clipboard failure now toasts instead of failing silently.
- Test setup: in-memory `localStorage` fallback in `__tests__/setup.ts` — Node 25's global `localStorage` shadows jsdom's and lacks `clear()`.

## Testing

```bash
cd frontend && make check
make check
make run-local   # then manual: /, /connect
```

Manual: copy URL (rail + panel + page), pick each assistant, reload → pick kept, keyboard-only
picker nav, install links open Cursor / VS Code, dark mode, 375px viewport.

## Out of scope

- Verifying end-to-end connect on second machine (022).
- Backend / OAuth changes.
- Auto-fetching vendor docs or a staleness checker for `lastVerified`.
- New assistants beyond current list.
