---
roadmap_id: 021
issue: n/a
---

# Plan: 021 Error tracking and feedback loop

## Overview

Today: errors go to CloudWatch logs only. `observability` alarm on Lambda `Errors` has no
`alarm_actions` → notifies nobody. Frontend has no error boundary: render crash = white
screen, nobody knows. No way for a user to say "this is broken / I want X". Beta (022)
needs both before invites.

In scope:
- Sentry (free Developer plan: 5k errors/mo, email alert on new issue) for backend + frontend.
  Off unless DSN configured → local dev, tests, stdio/uvx users send nothing.
- Backend: unhandled exceptions on REST (5xx) and MCP (non-`ToolError`) captured with
  release + environment + Clerk user id. No request bodies, no locals, no PII.
- Frontend: app-level error boundary (friendly fallback, reload) + uncaught errors /
  unhandled rejections captured. SDK lazy-loaded only when DSN present.
- One feedback channel: "Send feedback" item in user menu → our `Modal` + `EditForm`
  → Sentry User Feedback (`captureFeedback`) → same email alert. Also offered from the
  error fallback, linked to the crash event.
- Same-origin tunnel `POST /api/monitoring` so ad blockers don't eat events/feedback.
- Release = git sha baked into image; DSN + environment injected at serve time (image
  stays env-agnostic, like the Clerk key).
- Lambda-level failures (timeout, OOM, init crash) Sentry can't see: wire existing
  CloudWatch alarm to SNS email.

## Acceptance criteria

- [ ] No `SENTRY_DSN` → `sentry_sdk` not initialised, frontend SDK chunk never fetched,
      feedback menu item hidden; `make check` passes with no DSN anywhere.
- [ ] Dev: REST route raising unexpected exception → one Sentry issue tagged
      `environment=dev`, `release=<sha>`, `user.id=<clerk sub>`; no request body, cookies,
      `Authorization`, email or local variables in the event.
- [ ] `HTTPException` 4xx, auth 401/403/404, `ToolError`, `RequestValidationError` → not captured.
- [ ] MCP tool raising non-`ToolError` → captured once; tool still returns `isError`, txn rolls back.
- [ ] Event emitted during a Lambda invocation reaches Sentry (flushed before response),
      not lost on freeze.
- [ ] Frontend render crash → fallback page (pktx styled, "Reload" + "Tell us what
      happened") instead of white screen; event captured with release + user id.
- [ ] Navigating away from crashed route resets the boundary.
- [ ] "Send feedback" in user menu → modal (message required, ≤ 2000 chars, optional
      "you may contact me" checkbox) → success toast → Sentry feedback with url,
      release, user id; email arrives. ⌘/Ctrl+Enter submits, Esc closes.
- [ ] Events + feedback go via `/api/monitoring`; tunnel rejects envelopes whose DSN
      isn't ours (400), forwards ours to Sentry ingest; registered in route-scoping test as public.
- [ ] Lambda `Errors` alarm → SNS topic → email subscription (confirmed) in dev + prod.
- [ ] `docs/deployment.md` documents Sentry project setup, alert rule, tfvars, SNS confirm.

## Open questions

- [ ] Vendor — _proposed: Sentry SaaS free tier. Best Python/React SDKs, built-in
      feedback API, new-issue email alert by default. GlitchTip self-host = ops burden;
      CloudWatch-only = no frontend, no grouping._
- [ ] Feedback destination — _proposed: Sentry User Feedback via our own modal (no new
      table, no 3rd-party form, alerts already wired, crash ↔ feedback linked). Not a
      Google/Tally form (context switch, no user/url context), not GitHub issues (beta
      users lack accounts, repo exposure). Downside: feedback lives in Sentry, 1 seat._
- [ ] Contact consent — _proposed: checkbox "OK to email me about this", default off;
      email attached only when ticked (from Clerk). Otherwise only user id._
- [ ] Tunnel endpoint (public, unauthenticated relay to our Sentry project only) —
      _proposed: yes. Ad blockers drop `*.ingest.sentry.io` for a big share of
      technical users = our audience. Body cap 1 MB exists; DSN pinned server-side._
- [ ] Performance tracing / session replay — _proposed: no. `traces_sample_rate=0`,
      no Replay (would record resume/notes screens). Errors only._
- [ ] Frontend source maps — _proposed: defer. `build.sourcemap: 'hidden'` +
      `sentry-cli` upload in `deploy-dev.yml` needs `SENTRY_AUTH_TOKEN` + org/project
      config; follow-up item. Minified stacks + component name are enough to start._
- [ ] SNS email alarm — _proposed: yes, in this item. Needs `sns:*Topic*` /
      `sns:Subscribe` in deploy roles + boundary (`infra/shared`, owner-applied first).
      Alert email in tfvars (`alert_email`), not SSM._

## Design

**Config (no secrets).** DSN is public by design (ships to browser) → tfvars, not SSM
(fits 038 direction). Env vars on Lambda:

| var | source | use |
|---|---|---|
| `SENTRY_DSN` | tfvars `sentry_dsn` (default `""`) | backend init + injected to SPA |
| `PKTX_ENVIRONMENT` | `var.environment` (`dev`/`prod`) | Sentry `environment` |
| `PKTX_RELEASE` | image `ENV`, from build arg `PKTX_RELEASE=<sha>` | Sentry `release`, `/health` body |

`config.py` gains resolvers `resolve_sentry_dsn()`, `resolve_environment()`
(default `"local"`), `resolve_release()` (default `"dev"`).

**Backend — `pktx/error_tracking.py` (new).**
```python
def init_error_tracking() -> bool  # no DSN → False, no import side effects
    sentry_sdk.init(
        dsn, environment, release,
        send_default_pii=False, include_local_variables=False,
        max_request_body_size="never", traces_sample_rate=0,
        integrations=[FastApiIntegration(failed_request_status_codes={*range(500, 600)}),
                      LoggingIntegration(event_level=None)],  # logs → breadcrumbs only
        ignore_errors=[ToolError], before_send=scrub,
    )
def set_user(user_id: str) -> None          # sentry_sdk.set_user({"id": user_id})
def scrub(event, hint) -> event | None      # drop request.data/cookies/headers except
                                            # UA; strip query strings; drop user.email/ip
```
- Called from `server.main()` HTTP path only (not stdio, not `create_app` → tests stay clean).
- `set_user` called where user is resolved: `build_get_current_user` (REST) and the MCP
  DB-session/tool middleware (where `user_id` is known).
- MCP: FastMCP turns tool exceptions into `isError` results, so the SDK never sees
  them. In `DBSessionToolMiddleware` (`server.py`), on non-`ToolError` exception:
  `sentry_sdk.capture_exception(exc)` then re-raise (rollback path unchanged).
- Lambda freeze: LWA keeps process, freezes between invocations → background transport
  may not send. `FlushOnErrorMiddleware` (pure ASGI, in `error_tracking.py`): if an
  event was captured during this request (`sentry_sdk.last_event_id()` changed) →
  `await run_in_threadpool(sentry_sdk.flush, 2.0)` before finishing. Cost only on errors.
- Tunnel `POST /api/monitoring` (`api/routes.py` or `error_tracking.py` router): parse
  envelope header line (JSON), require `dsn` == configured DSN, forward body to
  `https://<host>/api/<project_id>/envelope/` via `httpx` (already transitive via
  fastmcp — make it a direct dep), return upstream status. No auth, no DB. 404 when
  Sentry disabled. Excluded from `DBSessionMiddleware` connection checkout (lazy anyway).

**SPA injection.** `SPAStaticFiles` already replaces `%PKTX_CLERK_PUBLISHABLE_KEY%`.
Generalise to a small placeholder map: add
`<meta name="pktx-sentry" content='%PKTX_SENTRY_CONFIG%'>` → JSON
`{"dsn","environment","release"}` (HTML-attribute escaped), or `""` when disabled.
`vite dev` falls back to `VITE_SENTRY_DSN` (usually unset).

**Frontend — `services/errorTracking.ts` (new).**
- `initErrorTracking()` in `main.tsx`: read meta; empty → no-op. Else
  `await import('@sentry/react')` (separate chunk) → `init({ dsn, environment, release,
  tunnel: '/api/monitoring', sendDefaultPii: false, integrations: [] defaults minus
  replay/tracing, beforeSend: scrub, beforeBreadcrumb: drop fetch bodies / console args })`.
- `reportError(err, ctx?)` / `sendFeedback({message, email?, eventId?})` queue until SDK
  loaded; no-op when disabled. `isErrorTrackingEnabled()` drives feedback menu visibility.
- User id: small `ErrorTrackingUser` effect under `ClerkProvider` → `setUser({id})` on
  sign-in, `setUser(null)` on sign-out.
- Ignore: `ApiError` (4xx user error; 5xx already captured server-side), `AbortError`,
  `ResizeObserver loop` noise, chunk-load errors after deploy (show reload instead).

**Error boundary — `components/ErrorBoundary` (new).** Class component around
`<AppRoutes/>` in `App.tsx`, `key={location.pathname}` so nav resets it. `componentDidCatch`
→ `reportError` (keeps event id). Fallback: `EmptyState`-style panel, "Something broke
on this page", `Button` "Reload", `Button variant="link"` "Tell us what happened" →
`FeedbackDialog` with `eventId`. Chunk-load error → "pktx was updated — reload".

**Feedback — `components/FeedbackDialog` (new).** `Modal` + `EditForm` (heading "Send
feedback", `FormField` textarea, checkbox "OK to email me about this"), submit →
`sendFeedback` → `toast.success('Thanks — feedback sent')`. Opened from `UserMenu`
(`UserButton.Action` "Send feedback", `MessageSquare` icon) and `ErrorBoundary`.
UserMenu is in header on all breakpoints → no tab-bar change.

**Infra.**
- `Dockerfile`: `ARG PKTX_RELEASE=dev` → `ENV PKTX_RELEASE`; `scripts/deploy/build-push.sh`
  passes `--build-arg PKTX_RELEASE=$GITHUB_SHA`. Digest changes per sha
  anyway → no cache cost.
- `infra/{dev,prod}`: vars `sentry_dsn`, `alert_email`; env `SENTRY_DSN`,
  `PKTX_ENVIRONMENT`.
- `modules/observability`: `aws_sns_topic` `pktx-<env>-alerts` + email subscription
  (when `alert_email != ""`), alarm `alarm_actions`/`ok_actions` → topic. Topic
  encrypted with AWS-managed key (`alias/aws/sns`) for Trivy.
- `infra/shared`: deploy role + boundary gain SNS actions scoped to
  `arn:aws:sns:*:*:pktx-<env>*`; plan role read (`sns:Get*`, `sns:List*`).

**Touches:**
- `backend/pyproject.toml`, `backend/uv.lock` (mod) — `sentry-sdk[fastapi]`, `httpx`
- `backend/src/pktx/error_tracking.py` (new)
- `backend/src/pktx/config.py` (mod) — resolvers
- `backend/src/pktx/server.py` (mod) — init in `main()` HTTP path, MCP tool capture, flush middleware,
  tunnel route, SPA placeholder map, release in `/health`
- `backend/src/pktx/auth.py` (mod) — `set_user`
- `backend/tests/unit/test_error_tracking.py` (new)
- `backend/tests/integration/test_error_tracking_http.py` (new) — 5xx captured, 4xx not,
  MCP crash captured + rolled back, tunnel accept/reject, SPA meta injection
- `backend/tests/integration/test_route_scoping.py` (mod) — register `/api/monitoring` public
- `frontend/package.json`, `package-lock.json` (mod) — `@sentry/react`
- `frontend/index.html` (mod) — sentry meta
- `frontend/src/services/errorTracking.ts` (new)
- `frontend/src/main.tsx` (mod), `frontend/src/App.tsx` (mod)
- `frontend/src/components/ErrorBoundary/` (new), `frontend/src/components/FeedbackDialog/` (new)
- `frontend/src/components/UserMenu/index.tsx` (mod)
- `frontend/src/__tests__/{ErrorBoundary,FeedbackDialog,errorTracking}.test.tsx` (new),
  `UserMenu.test.tsx` (mod)
- `Dockerfile` (mod), `scripts/deploy/build-push.sh` (mod) — release build arg
- `infra/dev/*`, `infra/prod/*` (mod), `infra/modules/observability/*` (mod),
  `infra/modules/lambda/*` (mod if env plumbing needs it), `infra/shared/main.tf` (mod)
- `docs/deployment.md` (mod), `AGENTS.md` (mod), `specs/lite/roadmap.md` (mod)

## Steps

- [ ] Owner: create Sentry org + projects `pktx-backend`, `pktx-frontend` (or one
      project, two platforms — one is enough on free tier), confirm "new issue → email"
      alert rule; note DSN(s).
- [ ] Backend config resolvers + `error_tracking.py` (`init`, `scrub`, `set_user`) +
      unit tests (scrub drops body/cookies/auth/query/email; disabled = no init).
- [ ] Wire init in `main()`, `set_user` in REST auth + MCP middleware, MCP capture in
      `DBSessionToolMiddleware`, flush middleware. Integration tests with a fake transport
      (`sentry_sdk.init(transport=...)` capturing envelopes).
- [ ] Tunnel route + tests (bad DSN 400, disabled 404, forward mocked); route-scoping registry.
- [ ] SPA placeholder map + `/health` release; tests.
- [ ] Frontend `errorTracking.ts` (lazy import, queue, scrub, ignore list) + tests
      (no DSN → `import` never called).
- [ ] `ErrorBoundary` + reset-on-nav + chunk-load variant + tests.
- [ ] `FeedbackDialog` + UserMenu item (hidden when disabled) + tests.
- [ ] Dockerfile release arg + deploy script; check image `/health` shows sha.
- [ ] Infra: `infra/shared` SNS perms (owner applies first), observability SNS + alarm
      actions, env vars, tfvars; `make check` (Trivy, tf validate).
- [ ] Docs: `docs/deployment.md` (Sentry setup, DSN tfvars, SNS confirm click, how to
      test), AGENTS.md section, roadmap status.
- [ ] Deploy dev; manual verification below.

## Testing

```bash
make check
cd backend && uv run pytest tests/unit/test_error_tracking.py tests/integration/test_error_tracking_http.py
cd frontend && npx vitest run src/__tests__/ErrorBoundary.test.tsx src/__tests__/FeedbackDialog.test.tsx
```

Manual (dev, DSN set):
- Local: `SENTRY_DSN=<dev dsn> make run-local`, stop postgres, hit `/api/notes` → 500 →
  issue appears, event JSON has no body/cookies/auth/email/locals.
- Browser console on dev: `setTimeout(() => { throw new Error('sentry probe') })` → issue.
- uBlock Origin on → events still arrive (tunnel).
- Send feedback (with and without contact checkbox) → email; email only on tick.
- Force render crash (devtools: break a component prop) → fallback, nav away recovers.
- `aws lambda` timeout simulation not needed: `aws cloudwatch set-alarm-state
  --alarm-name pktx-dev-errors --state-value ALARM --state-reason test` → email.

## Out of scope

- Performance monitoring / tracing, session replay, profiling.
- Source-map upload (follow-up item).
- Uptime monitoring (keep-warm + smoke test cover basics).
- MCP `send_feedback` tool (nice follow-up: "tell Claude to report a bug").
- Feedback inbox inside pktx / DB table; public roadmap / voting.
- Slack/PagerDuty routing; email is enough pre-beta.
