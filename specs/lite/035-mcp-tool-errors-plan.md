---
roadmap_id: 035
issue: n/a
---

# Plan: 035 MCP tools: raise errors and return structured results

## Overview

Non-resume MCP tools (`note_tools`, `contact_tools`, `accomplishment_tools`, `link_tools`)
catch `ValueError` and return `"Error: ..."` strings. Call looks successful (no `isError`),
so `DBSessionToolMiddleware` commits instead of rolling back, and clients can't tell
failure from success. Writes return prose (`"Updated note 3"`), forcing a re-fetch.
`application_tools` lets `ValueError` escape un-wrapped and also returns prose.

In scope:
- Every non-resume tool raises `ToolError` on invalid input / not found → `isError: true`
  + rollback. Reuse `tools/errors.raises_tool_error` (034).
- Create/update tools return the created/updated object (service already returns it).
- Delete/remove tools return a small identifying object of what was removed
  (mirrors `delete_resume` → `{id, label}`).
- Link tools return the link `{a_type, a_id, b_type, b_id}`; resource type args typed
  as `Literal[...]` so the schema advertises the enum.
- Return annotations tightened (`dict[str, Any]`, no `| str`).

## Acceptance criteria

- [x] `grep -rn '"Error:\|f"Error:' backend/src/pktx/tools` returns nothing; no tool
      in `tools/` catches `ValueError` locally.
- [x] Every tool in note/contact/accomplishment/application/link modules is decorated with
      `@raises_tool_error`.
- [x] Create/update tools return the full object (incl. `id`); delete/remove tools return
      `{id, <name field>}`; link/unlink return `{a_type, a_id, b_type, b_id}`.
- [x] Contract-style MCP test per module (in-memory `fastmcp.Client`, like
      `tests/integration/test_resume_mcp.py`): a failing write reports `is_error` and leaves
      data unchanged; a successful write returns structured data with the id.
- [x] A test proves rollback through `DBSessionToolMiddleware` on a `ToolError`
      (or existing coverage cited if present).
- [x] `make check` passes (backend + frontend unaffected).

## Open questions

- [x] Delete return shape — _proposed: `{id, title}` / `{id, name}` / `{id, position, company}`
      / `{id, subject}`; small, identifying, matches `delete_resume`._
- [x] Link args: `Literal` resource type — _proposed: yes; invalid type is rejected by
      schema validation (still `isError`), drop the manual pre-checks._

## Design

`raises_tool_error` already exists; apply it under `@mcp.tool()` on every tool and delete
the local `try/except ValueError` blocks. Services already return dicts from
create/update/delete (`note_service.update_note` etc.); `link_service.link/unlink` return
`None` → tool builds the echo dict. `communication_service.remove` returns the subject
string → tool returns `{id: comm_id, subject}`.

Shared MCP test helper (`Mcp` class in `test_resume_mcp.py`) moves to
`tests/mcp_client.py` (new; `user` passed in, tool name positional-only so a tool arg
called `name` doesn't collide). One contract file `tests/contract/test_mcp_tools.py`
covers all five modules (one test per module) instead of five near-identical files.
Rollback on a raised tool error is already covered by
`test_request_connection.py::test_tool_error_rolls_back_despite_200`.

Update MCP server instructions / docstrings if they mention "Error:" strings or prose
results. Update AGENTS.md resume note ("write tools return the changed object, errors
raise") to say this holds for all tools.

**Touches:**
- `backend/src/pktx/tools/note_tools.py` (mod)
- `backend/src/pktx/tools/contact_tools.py` (mod)
- `backend/src/pktx/tools/accomplishment_tools.py` (mod)
- `backend/src/pktx/tools/application_tools.py` (mod)
- `backend/src/pktx/tools/link_tools.py` (mod)
- `backend/tests/mcp_client.py` (new) — shared in-memory client helper
- `backend/tests/integration/test_resume_mcp.py` (mod) — use shared helper
- `backend/tests/contract/test_mcp_tools.py` (new) — client-level contract, all modules
- `backend/tests/contract/test_{note,accomplishment}_api.py`,
  `backend/tests/integration/test_{contact_mcp,contact_comm_mcp,link_integration,input_validation}.py`
  (mod) — prose/error-string asserts → objects / `ToolError`
- `backend/uv.lock` (mod) — `joserfc` 1.7.4 → 1.7.7 (CVE-2026-119283/119284 failed
  pip-audit in `make check`; pre-existing, unrelated)
- `AGENTS.md` (mod)

## Steps

- [x] Extract `Mcp` helper to `tests/integration/mcp_client.py`; resume test uses it.
- [x] note_tools: decorate, drop catches, return objects. Add `test_note_mcp.py`.
- [x] accomplishment_tools: same + test.
- [x] contact_tools (incl. communications + search): same + test.
- [x] application_tools: same + test.
- [x] link_tools: `Literal` types, decorate, return link dict + test.
- [x] Rollback test through `DBSessionToolMiddleware` (check existing
      `test_request_connection.py` first).
- [x] Fix tests that asserted old prose; grep server instructions for stale wording.
- [x] Update AGENTS.md; `make check`.

## Testing

```bash
cd backend && make check
cd backend && uv run pytest tests/integration -k mcp
```

## Out of scope

- Resume tools (already done in 034).
- REST API behaviour (unchanged; services untouched).
- Pydantic output models / `outputSchema` per tool — plain dicts are enough.
