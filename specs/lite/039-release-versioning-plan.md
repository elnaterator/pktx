---
roadmap_id: 039
issue: n/a
---

# Plan: 039 Release versioning: CalVer tags and visible app version

Branch: `chore/calver-releases` — PR https://github.com/elnaterator/pktx/pull/77 (both parts
on the same branch/PR).

## Overview

Prod deploys when a GitHub Release `v*` is published (031). There was no version scheme:
first release was a hand-pushed `v0.1.0` tag plus a separate `gh release create`, and
nothing shows which build a given environment runs.

Why CalVer, not SemVer: SemVer promises compatibility to a consumer who chooses which
version to run. pktx has none — UI users get the deployed SPA, the REST API's only client
ships in the same image, hosted MCP clients get whatever `/mcp` serves. A major bump
protects nobody; compatibility comes from expand → contract migrations and additive MCP
tool changes. The version just answers "what is prod running, since when" (rollback by
date). Revisit only if a pinned `uvx` stdio package is published to PyPI (CalVer is valid
PEP 440, so even then not required).

In scope:

- **Part 1 — release scheme**
  - Tags `vYYYY.MM.DD` (UTC date), `vYYYY.MM.DD.1`, `.2`, … for more releases the same day.
  - `make release [SHA=<sha>] [DRY_RUN=1]` → `scripts/deploy/release.sh`: default
    `origin/main`; refuses a commit without a successful **Deploy dev** run; picks next
    free tag; confirms; `gh release create <tag> --target <sha> --generate-notes` (the
    release creates the tag — no separate tag push).
  - `backend/pyproject.toml` + `frontend/package.json` at `0.0.0` (lockfiles refreshed);
    they no longer carry a release version.
  - `deploy-prod.yml` tag-validation error names the CalVer format (regex already accepts
    both `vYYYY.MM.DD` and `.N`, and old `v0.1.0`).
- **Part 2 — show the running version**
  - UI: small, faint version footer at the bottom of every page.
  - API: `version` + `sha` on `GET /health`.
  - MCP: `serverInfo.version` in the `initialize` result.

## Acceptance criteria

Part 1:

- [x] `make release DRY_RUN=1` prints `v<today UTC>` and the `origin/main` commit, publishes nothing.
- [x] With `v<today>` and `v<today>.1` already tagged, next tag is `v<today>.2`.
- [x] A commit with no successful Deploy dev run is refused with a clear error.
- [x] Package versions are `0.0.0`; `uv.lock` / `package-lock.json` consistent.
- [x] `make ci-lint` passes (shellcheck covers `release.sh`).
- [ ] First CalVer release via `make release` reaches prod (approve gate, smoke green). _(after merge)_

Part 2:

- [x] Image built with git sha baked in (`PKTX_GIT_SHA`, last layer); dev and prod still
      run the identical digest (`deploy-prod` digest-equality check unchanged).
- [x] `GET /health` → `{"status":"ok","version":...,"sha":...}`: release tag in prod,
      `dev-<7 hex>` in dev, `local` / `""` when unset (contract tests).
- [x] `smoke.sh <url> <version>` retries until `/health` reports the expected version,
      fails otherwise; dev, prod and `make deploy` pass it.
- [x] MCP `initialize` → `serverInfo.version` equals the same string (unit test).
- [x] `index.html` carries `pktx-version` / `pktx-git-sha` meta filled (html-escaped) at
      serve time; the SPA shows the version as an in-flow page footer (signed-in shell
      and landing page, desktop and phones), seen only when scrolled to the bottom;
      left-aligned with the content column; clears the phone tab bar.
- [x] Label links to the GitHub release page for release versions (no link for
      `dev-*` / `local`); tooltip shows the full sha (component test).
- [x] `terraform plan` (PR comment) passes the running version back, so no version drift.
- [x] Tokens only (`--text-muted`, `--font-mono`, `--font-size-1`, `--space-*`, `--z-raised`).
- [ ] Deployed dev shows `dev-<sha>` in the page footer, `/health`, MCP. _(after merge)_
- [ ] Prod shows the release tag; rollback (`workflow_dispatch tag=<older>`) shows the
      older version. _(after first release; pre-039 tags report `local`)_

## Decisions

- Signed-out visitors see the label too: repo is public, version/sha not sensitive.
- Release date in UTC: matches GitHub timestamps, deterministic across machines/CI.
- In-flow footer, not a fixed/floating label: floating over content felt intrusive (a
  first pass was fixed bottom-left; on phones it sat over scrolling content). Seen only
  at the bottom of the page, on every width.
- Left-aligned with the content column: bottom-right is where Clerk's dev-mode badge
  floats (test keys, so the dev env).
- `--font-size-2` (12px) mono, `--text-muted` at 0.35 opacity (0.8 on hover): larger
  than the smallest size, but fainter, so it reads as background.

## Design

**Build once constraint.** The image is built on merge (dev) and promoted byte-for-byte to
prod; the release tag does not exist at build time. So:

| Value | Set when | Mechanism |
|---|---|---|
| `PKTX_GIT_SHA` | build | `Dockerfile` `ARG GIT_SHA` → `ENV PKTX_GIT_SHA` (last layer, keeps cache); `build-push.sh` passes `--build-arg GIT_SHA=<sha>` (sha is 1:1 with the image, so promotion is unaffected) |
| `PKTX_VERSION` | deploy | Terraform var `app_version` (no default, like `image_digest`) → Lambda env; `apply.sh <env> <digest> <version>` (validated by `lib.sh require_version`); `deploy-prod` passes `$TAG`; `deploy-dev` passes `dev-${GITHUB_SHA:0:7}`; `make deploy` passes `dev-<sha7>` or the `v*` tag on HEAD (else `prod-<sha7>`); unset → `local` |

Changing a Lambda env var is config, not image → digest unchanged. `plan.sh` reads the
live value via `current-version.sh` (`lambda get-function-configuration`; plan role has
`lambda:Get*`) just as it reads the live digest.

Rollback to a pre-039 tag stays safe: that tag's `apply.sh` / `smoke.sh` ignore the extra
argument and its Terraform has no `app_version`, so the app reports `local`.

**Backend.** `config.resolve_app_version()` / `resolve_git_sha()` (env, defaults `local` /
`""`). `/health` returns them. `FastMCP("pktx", version=resolve_app_version(), ...)`.
`SPAStaticFiles(publishable_key=, version=, git_sha=)` fills `%PKTX_CLERK_PUBLISHABLE_KEY%`,
`%PKTX_VERSION%`, `%PKTX_GIT_SHA%` (html-escaped). No extra request.

**Frontend.** `utils/appVersion.ts` `resolveAppVersion()` reads the meta tags (unfilled
placeholder → `local`, as under `vite dev`) and builds the release URL for `v*` versions.
`components/VersionBadge` renders a `<footer>` (reads the version once at module load):
same column as `main` (max-width, padding), `--font-size-2` mono, `--text-muted` at 0.35
opacity (0.8 on hover/focus); release versions link through `ExternalLink`. Rendered
after `<main>` in the signed-in shell (`App.tsx`, class `app-footer`; on phones the
tab-bar clearance moves from `main` to `.app-footer` in `layout.css`) and at the end of
`LandingPage`.

**Touches:**

Part 1: `Makefile` (mod), `scripts/deploy/release.sh` (new), `backend/pyproject.toml`
(mod), `backend/uv.lock` (mod), `frontend/package.json` (mod), `frontend/package-lock.json`
(mod), `.github/workflows/deploy-prod.yml` (mod), `docs/deployment.md` (mod), `AGENTS.md`
(mod), `specs/lite/roadmap.md` (mod), `specs/lite/039-release-versioning-plan.md` (new).

Part 2: `Dockerfile` (mod), `scripts/deploy/{build-push,apply,plan,smoke,lib}.sh` (mod),
`scripts/deploy/current-version.sh` (new), `Makefile` (mod — `deploy`),
`.github/workflows/deploy-{dev,prod}.yml` (mod), `infra/{dev,prod}/{main,variables}.tf`
(mod), `backend/src/pktx/{config,server}.py` (mod), `backend/src/pktx/api/routes.py`
(mod), `backend/tests/unit/test_mcp_server_info.py` (new),
`backend/tests/unit/test_spa_index_config.py` (mod),
`backend/tests/contract/test_rest_api.py` (mod), `frontend/index.html` (mod),
`frontend/src/utils/appVersion.ts` (new), `frontend/src/components/VersionBadge.tsx` +
`.module.css` (new), `frontend/src/App.tsx` (mod),
`frontend/src/components/LandingPage/index.tsx` (mod), `frontend/src/styles/layout.css` (mod), `frontend/src/__tests__/utils/appVersion.test.ts`
(new), `frontend/src/__tests__/components/VersionBadge.test.tsx` (new), `docs/deployment.md` +
`AGENTS.md` (mod).

## Steps

Part 1:

- [x] `scripts/deploy/release.sh` + `make release` (help text, `SHA`, `DRY_RUN`).
- [x] Package versions → `0.0.0`, refresh `uv.lock` + `package-lock.json`.
- [x] `deploy-prod.yml` tag error message → CalVer format.
- [x] Docs: `docs/deployment.md` release section (scheme, `make release`, rollback
      example), `AGENTS.md` CD paragraph.
- [x] Roadmap item 039 + this plan.

Part 2:

- [x] Dockerfile `ARG GIT_SHA` → `ENV PKTX_GIT_SHA`; `build-push.sh` passes it.
- [x] Terraform `app_version` var into Lambda env (dev + prod); `apply.sh` takes the
      version → `-var app_version=...`; `current-version.sh` for plans; wire
      `deploy-dev.yml`, `deploy-prod.yml`, `make deploy`.
- [x] Backend resolvers; `/health` fields; `FastMCP(version=)`; `SPAStaticFiles`
      placeholders.
- [x] Frontend meta tags, `appVersion.ts`, `VersionBadge` footer in the shell + landing page.
- [x] `smoke.sh` version assertion (expected version passed in by the workflow).
- [x] Tests, docs, AGENTS.md (CD paragraph + Recent Changes entry for 039).
- [x] `make check`; browser check under `vite dev` (desktop + phone widths).
- [ ] After merge: dev shows `dev-<sha>`; `make release`; prod shows the tag.

## Testing

```bash
make check
make release DRY_RUN=1
```

- Backend: `/health` default + deployed values; `SPAStaticFiles` fills and escapes the
  version/sha placeholders; MCP `initialize` `serverInfo.version` from env and default.
- Frontend (Vitest): `resolveAppVersion` (release, dev, unfilled placeholder, missing);
  `VersionBadge` links only `v*` versions, sha in tooltip.
- Manual (done under `vite dev`, landing page): footer only visible at the bottom of the
  page, desktop and 375px phone width. Signed-in shell not checked in the browser (needs
  a sign-in). After merge: dev deploy `/health`, page footer, MCP client server info.

## Out of scope

- SemVer / PyPI publishing of the stdio package.
- Changelog file in the repo (GitHub generated release notes are the changelog).
- Version-skew handling (prompting users to reload when a new SPA is deployed).
- Retagging the existing `v0.1.0` release.
