---
roadmap_id: 027
issue: n/a
---

# Plan: 027 Security and data-integrity fixes from code review

Branch: `fix/027-security-fixes`. Full findings + repro notes: `research/security-review.md`.

## Overview

The 2026-10-02 review found cross-user data exposure, a stored-XSS path reachable through MCP
prompt injection, a resume-delete bug that breaks in production, and a shared DB connection
that will fail when Neon suspends. Fix all of it in one item, before beta (021+), and add the
tests that would have caught each one.

In scope:

- **C1** Delete the unscoped legacy `/api/resume*` routes (IDOR).
- **C2** Make user scoping fail closed: `user_id` is required throughout `database.py` and the services.
- **C3** Fix the cross-user leak in `GET /api/accomplishments/tags`.
- **C4** Block `javascript:` and other non-http URLs, on both server and client.
- **H5** Fix resume delete under autocommit (SAVEPOINT error).
- **H6** Replace the single shared connection with a per-request pooled connection and one transaction per request.
- **H7/H8** Validate tags (`null`, string and non-string values) and share one normalizer.
- **H9** Validate `update_entry` through the model.
- **M10** Rate-limit JWKS refetches, stop blocking fetches in async code, and drop the duplicate JWT check.
- **M11** Use `PKTX_USER_ID` only in stdio mode, and make stdio actually set the user.
- **M12** Check `azp` (authorized parties) on REST JWTs.
- **M13** Stop the MCP middleware's upsert from blocking the event loop, and upsert once per user per process.
- **M14** Minor hardening:
  - generic 401 details
  - `/api/*` 404s
  - `ILIKE` escaping
  - length limits
  - `cid` check on communications
  - `link_tools` requires a user
- Close the test gaps listed in the research doc.

## Acceptance criteria

- [ ] `/api/resume`, `/api/resume/{section}` and the legacy `/api/resume/...entries` routes are gone (404).
- [ ] No `database.py` or service function accepts `user_id=None`. Every call site passes a real user id. In no-auth test mode the user is `"legacy"`.
- [ ] `GET /api/accomplishments/tags` returns only the caller's tags.
- [ ] Server rejects (422 REST / tool error MCP) any non-`http(s)` value for `application.url`, `contact.linkedin_url`, and resume `contact.linkedin|website|github`.
- [ ] The frontend renders a stored non-http URL as plain text, never as `href`. The zod schemas reject non-http(s) URLs.
- [ ] Deleting a non-last resume works on an autocommit connection and on the production pool path. Default promotion is atomic.
- [ ] Each request (REST, MCP HTTP tool call, stdio tool call, webhook) checks out its own pooled connection on first DB use and runs in one transaction: commit on success, rollback on error. `/health` and static files never touch the DB.
- [ ] Killing the DB connection between requests does not break later requests: the pool's `check` validates the connection and replaces it.
- [ ] `tags: null` → stored `[]`. `tags: "x"`, `[1]` or a non-list value → 422. Existing `"null"` rows are repaired by a migration.
- [ ] Bad `update_entry` data (unknown types, wrong field types) → 422. Stored data stays valid.
- [ ] A token with an unknown `kid` triggers at most one JWKS fetch per 60s window. No sync HTTP call runs on the event loop. The REST JWT is verified once per request.
- [ ] With `PKTX_USER_ID` set, an HTTP request without a valid token → 401. The stdio MCP server runs tools as `PKTX_USER_ID`, and refuses to start without it.
- [ ] A REST JWT whose `azp` is not in the authorized-parties list → 401.
- [ ] The MCP tool middleware does no sync DB work on the event loop, and upserts each `sub` at most once per process.
- [ ] 401 details are generic.
- [ ] Unknown `/api/...` paths → JSON 404, not `index.html`.
- [ ] `%` and `_` in `q` and tags match literally.
- [ ] Text fields have max lengths (422 when exceeded).
- [ ] Communication PATCH/DELETE → 404 when `cmid` is not under `cid`.
- [ ] `link_resources` and `unlink_resources` require an authenticated user.
- [ ] New tests (see Testing) pass, and every fix has a test that fails before it.
- [ ] `make check` is green (backend + frontend).

## Open questions

All resolved 2026-10-02: user accepted proposed defaults.

- [x] Delete the legacy `/api/resume*` routes outright (no external callers known)? _proposed: yes, delete._
- [x] Authorized parties for `azp`: new optional env `CLERK_AUTHORIZED_PARTIES` (comma list). _proposed: default to the origin of `PKTX_PUBLIC_URL`. Add `http://localhost:5173` in dev tfvars/compose. Wire it through Terraform the same way as `extra_client_redirect_uris`._
- [x] Max text lengths. _proposed:_
  - labels/titles/names/company/position: 200
  - URLs: 2,048
  - tag: 50 (existing)
  - tags per resource: 50
  - short text (email, phone, location, subject): 500
  - long text (note content, contact notes, application description/notes, STAR fields, comm body, summary): 100,000
  - request body: 1 MB
- [x] Production transaction model: one transaction per request (`autocommit=False`, commit at the end). _proposed: yes. This matches the test fixture and makes multi-step operations atomic._

## Design

### Per-request connection (H6, fixes H5)

- New `pktx/db.py` `RequestConnection`. It implements the `DBConnection` protocol and holds no connection of its own: every call resolves the request-scoped connection from a ContextVar `_request_conn`.
  - On first use it checks out a connection with `pool.getconn()`, using `check=ConnectionPool.check_connection` so dead connections get replaced.
  - Services stay constructed once with a `RequestConnection` instead of a raw connection, so the service and route code does not change shape.
  - Tests keep passing a raw psycopg connection directly (both satisfy `DBConnection`).
- New pure ASGI middleware `DBSessionMiddleware`:
  - sets an empty holder in the ContextVar
  - calls the app
  - on exit, if a connection was checked out: commit (or roll back on exception or a 5xx status), then `putconn`, using `asyncio.to_thread` for the blocking pool calls
  - Starlette copies the context into the threadpool for sync handlers, so the lazy checkout made inside a handler lands in the holder. The holder is a mutable object, so the mutation stays visible after the copy.
- stdio: a FastMCP middleware does the same holder setup around each tool call.
- Webhook: uses the same `RequestConnection`. Remove `from pktx.server import _conn`.
- Remove `_raw_conn`, the `_conn` globals, `auth._conn`, and the unused `get_db`.
- Pool: `autocommit` stays False (the default). Keep `dict_row`.
- `delete_resume_version`: drop the manual SAVEPOINT and wrap the work in `conn.transaction()`. That works on both autocommit and transactional connections, because psycopg uses a savepoint when a transaction is already open.
- `delete_resume` and `delete_application`: unlinking and deleting become atomic (same transaction), and the ownership check runs before the unlink.

### Fail-closed scoping (C1–C3)

- `database.py` and the services: `user_id: str`, required, everywhere. Remove every `if user_id is not None` branch, every unscoped `else` query, and every `user_id or "legacy"`.
- `build_filters` always adds the user condition.
- `routes._make_user_dep`: in no-auth mode return `UserContext(id="legacy", email=None, display_name=None)`. That lets routes use `current_user.id` unconditionally (type `UserContext`, not `| None`), and deletes the repeated `uid = ... if ... else None` lines.
- The export and search services take `user_id: str`.
- Delete the legacy routes. `list_accomplishment_tags` gets the user dependency.
- `tools/link_tools.py`: use `require_user_id()`.
- Load-by-id: keep the 403/404 split, but run the owner check in SQL (`WHERE id = %s AND user_id = %s`). A miss returns 404, so no cross-user existence oracle. Routes stop mapping `PermissionError` → 403. The 403 tests change to expect 404.

### Input validation (C4, H7–H9, M14 lengths)

- New `pktx/validation.py`:
  - `normalize_tags(value) -> list[str]`: `None` → `[]`; non-list or a non-str item → `ValueError`; trim, lowercase, max 50 chars, max 50 tags, dedupe. Replaces the six copies of `_normalize_tags`.
  - `validate_http_url(value) -> str | None`: empty → `None`; `urlparse` scheme must be `http`/`https` with a netloc; max 2,048 chars.
  - `check_len(field, value, max)`.
- Services call these for every create/update. The database layer applies `json.dumps` only to normalized lists.
- `models.py`: add `field_validator`s that use `validate_http_url` on `ContactInfo.linkedin|website|github`, `Application.url` and `Contact.linkedin_url`.
- `update_entry`: `model_cls.model_validate({**entries[index], **data})` replaces `model_copy(update=...)`.
- Migration v13→v14: `UPDATE <t> SET tags = '[]' WHERE tags = 'null' OR tags IS NULL` for every tagged table.
- Request-size cap: middleware rejects `Content-Length` over 1 MB with 413.

### Auth (M10–M13, M14 detail)

- Delete the JWT branch of `UserContextMiddleware`. No REST route reads `current_user_id_var`; the routes use the dependency, so this removes the double verification and the blocking fetch on the event loop.
- Delete `UserContextMiddleware` entirely. `PKTX_USER_ID` moves into `main()`'s stdio path, which sets `current_user_id_var` for the process. stdio exits with an error if `PKTX_USER_ID` is unset.
- `_get_jwks_key`:
  - unknown `kid` → refetch only if 60s have passed since the last fetch, else 401
  - guard it with a `threading.Lock`
  - it still runs sync, but only inside the threadpool dependency, never on the event loop
- `verify_clerk_jwt`:
  - when `azp` is present it must be in `resolve_authorized_parties()`
  - when it is missing, reject (Clerk session tokens always carry it)
  - 401 details become fixed strings ("Invalid token"); the cause is logged at DEBUG
- `UserContextToolMiddleware`: a per-process `set[str]` of upserted subs. The first call per sub runs `await asyncio.to_thread(upsert_user, RequestConnection, ...)`.

### Minor (M14)

- `build_filters`: escape `\`, `%` and `_` in `q` words and tags, and use `ILIKE %s ESCAPE '\'`.
- An `api` catch-all `@api.api_route("/api/{path:path}", methods=[...])` registered last → 404 JSON.
- Communication PATCH/DELETE: the service takes `contact_id` and checks `c.contact_ref_id = cid` in the same owner query. A mismatch returns 404.

### Frontend (C4)

- New `src/utils/safeUrl.ts`: `safeHref(url): string | undefined` returns the URL only for `http:`/`https:` (and `mailto:` where the caller allows it). Uses `new URL()` in a try/catch.
- New `components/ExternalLink.tsx`: renders `<a target=_blank rel=noopener noreferrer>` when `safeHref` passes, else a plain `<span>`. Use it in:
  - `ApplicationPanel.tsx:234`
  - `ApplicationListView.tsx:157`
  - `ContactPanel.tsx:274`
  - `resumes/ContactSection.tsx:39`
  - `mailto` in `ContactPanel.tsx:244` stays as is, built from validated email text
- zod: shared `httpUrl()` helper (`z.string().url().refine(protocol http/https)`) in `schemas/` used by application, contact and resumeEntry.

**Touches:**

- backend:
  - `db.py` (mod)
  - `server.py` (mod)
  - `auth.py` (mod)
  - `config.py` (mod: `resolve_authorized_parties`)
  - `database.py` (mod)
  - `migrations.py` (mod: v14)
  - `validation.py` (new)
  - `models.py` (mod)
  - `resume_service.py`, `application_service.py`, `accomplishment_service.py`, `note_service.py`, `contact_service.py`, `communication_service.py`, `link_service.py`, `search_service.py`, `export_service.py` (mod)
  - `api/routes.py` (mod)
  - `tools/link_tools.py` (mod)
  - `tools/contact_tools.py` (mod: comm contact id)
- backend tests:
  - `conftest.py` (mod)
  - `tests/integration/test_route_scoping.py` (new)
  - `tests/unit/test_validation.py` (new)
  - `tests/integration/test_request_connection.py` (new)
  - `tests/unit/test_auth.py`, `tests/contract/test_auth_contract.py`, `tests/contract/test_rest_api.py`, `tests/integration/test_multi_user.py` and the 403 tests (mod)
  - webhook tests (new in `test_auth_contract.py`)
- frontend:
  - `utils/safeUrl.ts` (new)
  - `components/ExternalLink.tsx` (new)
  - the 4 pages above (mod)
  - `schemas/{application,contact,resumeEntry}.ts` (mod)
  - `schemas/httpUrl.ts` (new)
  - `__tests__/utils/safeUrl.test.ts` (new)
  - `__tests__/components/ExternalLink.test.tsx` (new)
- infra:
  - `infra/{dev,prod}/main.tf`, `variables.tf`, `terraform.tfvars` (mod: `authorized_parties`)
  - `docker-compose.yml` (mod: env)
- docs:
  - `AGENTS.md` (mod: request-connection model, fail-closed scoping, new env var)
  - `README.md` env table (mod)

## Steps

Work runs in **waves**. Inside a wave, the tracks run **in parallel as subagents**, each in its
own git worktree (`isolation: "worktree"`). Inside a track, steps run in order. Tracks are cut
by **file ownership**, so parallel agents never edit the same file. The single exception is
`api/routes.py`, where track B touches only the webhook handler; the conflict is small and
resolved in wave 2.

### Wave 0: serial, main agent (prerequisite for everything)

- [x] 1. **Test harness first.** Commit it before spawning wave 1, so every worktree starts from it.
  - Add an `autocommit_conn` fixture (`autocommit=True`) with manual cleanup of the rows each test creates.
  - Add a `two_users` fixture (alice, bob) seeding one of every resource type plus links and communications for alice.
  - Write the failing tests for H5 and C1–C3 now, including a skeleton of `test_route_scoping.py`.
  - _Done:_
    - shared helpers in `tests/helpers.py`: JWT minting with an `azp` default, `build_full_app`, and an `X-Test-User` client
    - `autocommit_conn`, `two_users` and `snapshot_user_rows` in `conftest.py`
    - `test_route_scoping.py`, written in full rather than as a skeleton; it walks FastAPI's `_IncludedRouter.original_router`
    - `test_security_regressions.py`
  - The harness was committed on the branch as a local commit, which worktrees need. This deviates from build's no-commit rule; ship will add the rest.

### Wave 1: three parallel subagents (tracks A, B, C)

**Track A: data layer** (serial within the track; the largest track)

Owns: `validation.py`, `database.py`, `migrations.py`, `models.py`, every `*_service.py`,
`link_service.py`, `api/routes.py` (everything except the webhook), `tools/*.py`, and the
matching tests.

- [ ] 2. **`validation.py` + unit tests.**
  - `normalize_tags`, `validate_http_url`, `check_len`.
  - Replace the six `_normalize_tags` copies.
- [ ] 3. **Fail-closed scoping.**
  - Make `user_id` required throughout `database.py` and the services. Move owner checks into SQL.
  - Make the routes use a non-optional `UserContext` (`"legacy"` in no-auth mode).
  - Delete the legacy routes. Fix the accomplishment tags route and `link_tools`.
  - Update the tests that relied on `None` or on 403.
- [ ] 4. **`delete_resume_version`.** Replace the SAVEPOINT with `conn.transaction()`. Make delete + unlink atomic, with the ownership check first.
- [ ] 6. **Input validation in services and models.**
  - URL validators, `update_entry` via `model_validate`, length limits.
  - Migration v14 to repair `"null"` tags. Add a migration test.
- [ ] 8a. **Minor (data).** `ILIKE` escaping in `build_filters`, the `/api` catch-all 404, the communication `cid` check. Tests for each.

**Track B: runtime + auth** (serial within the track)

Owns: `db.py`, `server.py`, `auth.py`, `config.py`, the webhook handler in `api/routes.py`,
`infra/**`, `docker-compose.yml`, and the auth/connection tests.

- [x] 5. **Per-request connection.**
  - `RequestConnection`, `DBSessionMiddleware`, the stdio tool middleware, pool `check`, webhook rewiring.
  - Remove the shared-connection globals.
  - Add `test_request_connection.py`, covering:
    - commit on success
    - rollback on raised exception
    - a closed connection replaced on the next request
    - `/health` never checks out a connection
    - two concurrent requests get distinct connections
  - _Done, with divergences:_
    - pool `check=ConnectionPool.check_connection` added inside `database.init_pool` (3-line kwarg change in Track A's file).
    - `DBSessionMiddleware` commits when the response *starts* (before the status line goes out), so a failed commit becomes a 500 instead of a false 200; anything after that is committed at request end. Blocking calls use `anyio.to_thread` inside a shielded cancel scope (a client disconnect still returns the connection), not `asyncio.to_thread`.
    - one FastMCP `DBSessionToolMiddleware` covers both transports: over HTTP it only marks the ASGI scope failed on a tool exception (MCP answers 200); with no scope (stdio) it owns one per tool call and sets `PKTX_USER_ID` as the user.
    - `create_app` gained keyword-only `pool=` / `enable_auth=` for tests of the production path; `create_app(service=, conn=)` unchanged.
    - webhook gets the connection as `service._conn` (no `create_router` signature change) and runs `delete_user` via `asyncio.to_thread`; `clerk_webhook(request: Any)` fixed to `request: Request` (adds `Request` to the `fastapi` import at the top of `routes.py`).
- [x] 7. **Auth.**
  - Remove `UserContextMiddleware`. Move `PKTX_USER_ID` to stdio.
  - JWKS rate limit + lock.
  - `azp` check + `CLERK_AUTHORIZED_PARTIES` config.
  - Generic 401 details.
  - MCP middleware: upsert off the event loop, once per sub.
  - Tests for each.
  - _Done:_ a failed JWKS fetch falls back to the stale cache and answers 401 (was 500). The MCP upsert commits right away, so a later tool rollback cannot undo it while the per-process cache skips it. Token minting in `test_auth_contract.py` / `test_multi_user.py` gained `azp`, plus a per-module `CLERK_AUTHORIZED_PARTIES` fixture.
- [x] 8b. **Minor (runtime).** A middleware that caps request bodies at 1 MB (413). Test it.
- [x] 10a. **Infra.** Wire `CLERK_AUTHORIZED_PARTIES` through dev/prod Terraform (`variables.tf`, `main.tf`, `terraform.tfvars`) and docker-compose.
  - _Divergence:_ a non-empty `authorized_parties` replaces the app's default, so `main.tf` prepends the `PKTX_PUBLIC_URL` origin (regex on the SSM value) and passes `""` when the list is empty. dev = `["http://localhost:5173"]`, prod = `[]`. Compose defaults to `http://localhost:8000,http://localhost:5173`.

**Track C: frontend** (fully independent)

Owns: `frontend/**`.

- [ ] 9. **Frontend.** `safeHref`, `ExternalLink`, the zod `httpUrl`, and swapping out the 4 call sites. Vitest coverage. Run `cd frontend && make check`.

**Wave 1 rules:**

- Each agent runs its own track's tests (`uv run pytest <paths>` or `make check` in its directory) before reporting.
- Each agent reports changed files plus test output.
- Track A may assume the `RequestConnection` interface equals `DBConnection` (it does by design), so it needs nothing from B.
- B must not touch service or database function signatures.

### Wave 2: serial, main agent (integration)

- [ ] 11. **Merge** the A, B and C worktrees into `fix/027-security-fixes`, in the order B, then A, then C. Resolve the `routes.py` webhook overlap.
- [ ] 12. **Finish `test_route_scoping.py`.** It needs the final route set from A plus the per-request connection from B. Run it against the merged app.
- [ ] 13. **Docs.** Update `AGENTS.md` (request-connection model, fail-closed scoping, new env var), the README env table, and `research/security-review.md` (mark findings fixed).
- [ ] 14. `make check` from the root, all green. Manual checks are listed in Testing.

## Testing

Commands:

```bash
make check                                   # root: lint + typecheck + test, backend + frontend
cd backend && uv run pytest tests/integration/test_route_scoping.py -v
cd backend && uv run pytest -k "autocommit or request_connection" -v
cd frontend && npm run test -- safeUrl ExternalLink
```

New and changed tests:

- **Route-wide scoping test** (`test_route_scoping.py`):
  - Enumerate every `APIRoute` in the app router except `/health` and the webhook.
  - For each, call it as bob using alice's resource ids (path params filled from the `two_users` fixture).
  - Assert: GET-by-id/PATCH/DELETE return 404; list/tags/search/export return none of alice's ids or tags; alice's rows are unchanged afterwards.
  - Fail the test when a new route has no path-param mapping, so new routes can't skip the check.
- **Autocommit parity:** run the resume-service delete/promote tests on both `db_conn` and `autocommit_conn`.
- **Bad input** (REST + service), one test each:
  - tags `null` / `"backend"` / `[1]` / 51 tags / a 51-char tag
  - `url="javascript:alert(1)"`, `"data:..."`, `"ftp://x"`
  - `update_entry` wrong types / unknown fields
  - oversized fields
  - body > 1 MB
- **Auth:**
  - unknown-`kid` storm → one JWKS fetch (mock `httpx.get`, count calls)
  - `azp` mismatch / missing → 401
  - `PKTX_USER_ID` set + no token → 401 over HTTP
  - stdio sets the user
  - 401 detail does not echo the exception
  - MCP upsert called once per sub
- **Webhook:** bad signature → 400; `user.deleted` cascades all of that user's rows and leaves the others.
- **Search escaping:** `q="100%"` does not match `"1000"`.
- **Frontend:**
  - `safeHref` table test (http, https, javascript, JaVaScRiPt, data, relative, garbage)
  - `ExternalLink` renders a span for unsafe values
  - the zod schemas reject `javascript:`

Manual:

- `make run-local`: create, edit and delete a resume. Delete a non-default and the default resume; confirm promotion.
- Restart Postgres while the app is running; the next request succeeds.
- Connect Claude Desktop to `/mcp`, run `list_resumes` and `link_resources`.

## Out of scope

- Full Pydantic request-body models for every REST route. Validation here is targeted: tags, URLs, lengths, entries. Revisit as its own refactor.
- A rate limiter or WAF for the API in general (beyond the JWKS refetch throttle).
- CSP headers / security headers on the SPA. Worth a follow-up item: a CSP would be defense-in-depth for C4.
- Changing the OAuth proxy, CIMD/DCR or the redirect allowlist. Reviewed and judged sound.
- Error tracking (021).
