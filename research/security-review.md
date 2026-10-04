# Security review (2026-10-02)

**Status: all findings fixed in roadmap item 027** (`fix/027-security-fixes`, plan
`specs/lite/027-security-fixes-plan.md`). Each has a regression test; the route-wide
scoping guard is `backend/tests/integration/test_route_scoping.py`. Out of scope and
still open: CSP/security headers on the SPA, general API rate limiting.

Full-codebase review: auth, server wiring, OAuth store, REST routes, services, `database.py`,
MCP tools, frontend link rendering, infra redirect allowlist, test fixtures. Items marked
**verified** were reproduced against a real Postgres 16 container with `autocommit=True`
(production connection mode).

## Critical — security

1. **Legacy `/api/resume*` routes cross-user IDOR.** `backend/src/pktx/api/routes.py`
   (`get_resume_legacy`, `get_section_legacy`, `update_contact_legacy`,
   `update_summary_legacy`, `add_entry_legacy`, `update_entry_legacy`,
   `remove_entry_legacy`). Auth-protected but call the service with no `user_id`;
   `load_default_resume_version` with `user_id=None` runs
   `SELECT * FROM resume_version WHERE is_default = 1` — returns an arbitrary user's default
   resume. Any signed-in user can read and modify another user's resume. **Verified**
   (unscoped row returned). Frontend does not call these routes.
2. **`user_id=None` means "all users" (fail-open).** Every `database.py` function skips the
   owner filter when `user_id` is `None` (`build_filters`, `load_*`, `*_tags`,
   `set_default_resume_version` updates every row, `delete_resume_version` counts globally).
   Any route that forgets `uid` leaks silently. Should fail closed: require `user_id`;
   explicit opt-in for the no-auth test mode only.
3. **`GET /api/accomplishments/tags` leaks all users' tags.** Calls
   `acc_service.list_tags()` with no user.
4. **Stored XSS via `javascript:` URLs.** `application.url`, `contact.linkedin_url`, resume
   `contact.linkedin/website/github` rendered as `<a href>` in `ApplicationPanel.tsx`,
   `ApplicationListView.tsx`, `ContactPanel.tsx`, `resumes/ContactSection.tsx`. Backend has no
   scheme validation; zod `.url()` accepts `javascript:`; React 18 only warns. Attack path:
   prompt-injected MCP agent (malicious job posting) writes `url="javascript:…"`; user clicks;
   script runs in app origin with access to the Clerk session token. Fix: server-side
   `http(s)`-only validation (mailto where relevant) + shared safe-link component on frontend.

## High — bugs

5. **Resume delete always fails in prod.** `delete_resume_version` issues `SAVEPOINT`; prod
   connection is `autocommit=True` (`server.py` `create_app`) → `NoActiveSqlTransaction:
   SAVEPOINT can only be used in transaction blocks`. **Verified.** Tests miss it because
   `db_conn` fixture is `autocommit=False`.
6. **Single shared DB connection for all requests.** `create_app` checks one raw connection
   out of the pool and gives it to every service; `get_db()` exists but is unused. Dead
   connection (Neon autosuspend, Lambda freeze) → every request fails until cold start
   (keep-warm hits `/health`, no DB touch). Threadpool requests serialize on one connection;
   any future `conn.transaction()` interleaves statements from concurrent requests.
   Multi-step ops (unlink-then-delete) are not atomic.
7. **`tags: null` poisons tag listing.** PATCH `{"tags": null}` stores `"null"`; every later
   `list_tags` raises `TypeError` → `/api/tags` 500 for that user permanently. **Verified.**
8. **String `tags` split into characters.** `{"tags": "backend"}` →
   `['b','a','c','k','e','n','d']`; `[1]` → `AttributeError` 500. **Verified.** REST bodies
   are raw `dict[str, Any]`, no schema.
9. **`update_entry` skips validation.** `model_copy(update=data)` does not validate; arbitrary
   keys/types stored; later `Resume(**…)` fails → resume unreadable.

## Medium

10. **JWKS refresh amplification + event-loop block.** Unknown `kid` → JWKS refetch every
    request, no rate limit (`auth._get_jwks_key`). Fetch is blocking `httpx.get` (10s timeout)
    called from async `UserContextMiddleware.dispatch` → stalls event loop. REST JWT also
    verified twice per request (middleware + dependency).
11. **`PKTX_USER_ID` fallback in HTTP mode.** If set on a deployed instance, any request
    without a valid token runs as that user (`server.py` `UserContextMiddleware`). Meanwhile
    stdio mode never sets the context var, so all MCP tools raise "No user context". Move to
    stdio path only.
12. **No `azp` check on REST JWTs.** `verify_clerk_jwt` checks signature + issuer only. Any
    token from the same Clerk instance accepted (possibly upstream OAuth access tokens). Clerk
    recommends authorized-parties (`azp`) validation.
13. **Blocking `upsert_user` in MCP middleware.** Sync DB write per tool call on shared conn
    inside async middleware.
14. **Minor hardening.** Raw library exception text in 401 detail; unknown `/api/*` paths
    return SPA `index.html` with 200; `%`/`_` not escaped in `ILIKE` filters; no length
    limits on text fields / resume JSON; communication PATCH/DELETE ignore `cid` path param.

## Test-suite gaps

- Fixture runs in a transaction (`autocommit=False`), prod uses autocommit — hid #5.
- No route-wide user-scoping test: iterate every router route as Bob with Alice's data,
  assert nothing of Alice's visible/mutable. Would have caught #1, #3.
- Cross-user REST update/delete tests cover resumes/applications/accomplishments only — not
  notes, contacts, communications, links, search, export.
- No bad-input tests (tags null/string/int, wrong field types, oversized bodies,
  `javascript:` URLs).
- No tests for `PKTX_USER_ID` fallback, `kid` refresh behaviour, webhook invalid signature /
  `user.deleted`.
- Frontend tests: render-level only; nothing on URL sanitizing.

## Already solid

OAuth proxy (DCR, CIMD, audience binding, loopback matching, root metadata alias), FastMCP
redirect validation (rejects userinfo, dot-segments, unsafe schemes), Fernet-encrypted
`oauth_kv`, Svix webhook verification, link ownership checks.
