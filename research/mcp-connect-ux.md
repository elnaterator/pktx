# MCP connect UX

## Current state (2026-10-04)

`frontend/src/components/ConnectAssistantPanel.tsx` (home page) already has an assistant
`<select>` (Claude Desktop, ChatGPT, Claude Code, Grok Build, Cursor, GitHub Copilot,
Amazon Kiro, Windsurf, Zed, Cline), per-assistant steps, copy-config button, and a
collapse toggle. Gaps: MCP URL not the first thing seen, no value pitch, no assistant
icons, terminology per assistant inconsistent, steps hand-maintained and drift (026 had
to patch ChatGPT's July 2026 rename).

## Goals

- **URL first.** `<PKTX_PUBLIC_URL>/mcp` in large mono text with one-click copy, top of
  panel, visible even when collapsed.
- **Value pitch.** 2–4 short, catchy lines on what the connector does ("Ask Claude to
  tailor your resume to this job", "Log a win from chat", "Prep for an interview with
  your contacts + notes"). Example prompts, copyable.
- **Picker with icons.** Icon/logo next to each assistant in the dropdown (custom listbox,
  native `<select>` cannot render icons). Remember last pick (localStorage). Collapsible.
- **Right noun per assistant.** Show what the assistant calls it: Claude = "connector"
  (custom connector), ChatGPT = "app"/developer-mode connector, IDEs = "MCP server".
  Badge the term next to the name so users search the right settings menu.
- **Fresh, accurate steps.** Re-verify every assistant's current flow against vendor
  docs; record "last verified" date per entry; one data file (not JSX) so updates are
  one-line diffs. Include deep links / one-click install where vendor supports it
  (Cursor `cursor://` install link, VS Code `vscode:mcp/install`, Claude Code
  `claude mcp add` command).
- **Pop.** Distinct accent card, theme tokens (009), works in dark mode + mobile.

## Open questions

- Logo usage: vendor brand marks vs generic glyphs (lucide). Brand marks likely fine as
  identification (nominative use) but keep small + monochrome.
- Should panel move to its own `/connect` route as well as home? Probably yes for
  linking from README.
- Overlap: 022 (MCP connect flow verified on other machine) — this item makes that flow
  smoother; 022 still verifies it.
