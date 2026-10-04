---
roadmap_id: 028
issue: n/a
---

# Plan: 028 Security scanning and automated patching

## Overview

Nothing scans dependencies, the image, IaC or secrets today, no bot opens update PRs, and
the Dockerfile ships an EOL `node:18-slim` plus an unpinned `uv:latest`. Add **free,
low-tool-count** coverage before beta. Rationale and tool choices:
`research/security-scanning.md`.

In scope:

- Base image fixes: `node:18-slim` → `node:22-slim` (CI `setup-node` 20 → 22 to match),
  pin `uv`, `python:3.11-slim` and `aws-lambda-adapter` by version + digest.
- Every GitHub Action pinned to a full SHA with a `# vX.Y.Z` comment.
- Renovate (`renovate.json`) for automated patching, plus Dependabot alerts as a backstop.
- `pip-audit` + `npm audit` in `make check`.
- ruff bandit (`S`) rules.
- Trivy: `config` replaces Checkov in `tf-check`; `image` + `fs --scanners secret` in CI;
  SARIF uploaded to the Security tab.
- CodeQL default setup (settings toggle, no workflow file), secret scanning, push protection.
- New `security.yml` workflow: on PRs + weekly cron, so new CVEs in unchanged code surface.
- Workflow hygiene in place of zizmor: least-privilege `permissions`,
  `persist-credentials: false`.

## Acceptance criteria

- [x] `Dockerfile` has no `:latest`, no EOL base; every `FROM` / `COPY --from` image is
      pinned `name:version@sha256:…`.
- [x] Every `uses:` in `.github/workflows/*.yml` is pinned to a 40-char SHA with a version
      comment.
- [x] Both workflows have top-level `permissions: contents: read`; only the SARIF job adds
      `security-events: write`; every checkout sets `persist-credentials: false`.
- [x] `make check` runs `pip-audit` (backend) and `npm audit --audit-level=high --omit=dev`
      (frontend) and fails on a known vuln.
- [x] ruff `select` includes `"S"`; `make lint` passes; each `# noqa: S…` carries a
      reason; tests ignore `S101`.
- [x] `make tf-check` runs `trivy config infra/` (HIGH/CRITICAL); Checkov is gone from the
      Makefile, CI and docs.
- [x] `security.yml` runs on `pull_request` and weekly `schedule` and on
      `workflow_dispatch`. It builds the image, runs Trivy `image` (HIGH/CRITICAL,
      `--ignore-unfixed`), Trivy `config` and Trivy `fs --scanners secret`, and uploads
      SARIF.
- [x] `renovate.json` validates (`npx --package renovate renovate-config-validator`).
- [x] `docs/deployment.md` or `CONTRIBUTING.md` documents the manual GitHub settings
      steps, local install for Trivy, and the `.trivyignore` waiver convention.
- [x] `AGENTS.md` Active Technologies / Recent Changes updated; Checkov reference removed.

## Open questions

Resolved 2026-10-03:

- [x] Local Trivy: `trivy` from PATH (developer has it installed); `make tf-check` errors
      with an install hint if missing. No docker fallback.
- [x] Image scan blocks PRs on HIGH/CRITICAL with a fix available; unfixed findings are
      reported only; waivers in `.trivyignore` with a reason and an expiry.
- [x] Renovate automerge: patch + devDependencies + Action digests; minor grouped weekly,
      merged by hand; major merged by hand.

## Design

**Tool roster (final):** Renovate, pip-audit, npm audit, ruff `S`, Trivy, CodeQL (default
setup), GitHub secret scanning + push protection, Dependabot alerts. No gitleaks: push
protection plus Trivy's secret scanner cover it. No zizmor: CodeQL's `actions` language
plus the hygiene rules cover it. No Checkov: Trivy `config` replaces it.

**Where each check runs:**

| Check | `make check` (local + CI) | `security.yml` (PR + weekly) |
|---|---|---|
| pip-audit | ✓ | ✓ (weekly catches new CVEs) |
| npm audit | ✓ | ✓ |
| ruff `S` | ✓ (lint) | — |
| Trivy config (infra/) | ✓ (tf-check) | ✓ SARIF |
| Trivy image | — (needs docker build) | ✓ SARIF |
| Trivy fs secrets | — | ✓ SARIF |
| CodeQL | — | GitHub-managed default setup |

**pip-audit invocation** (runs against the lock, adds no dependency):

```make
audit:
	uv export --frozen --no-dev --no-emit-project --format requirements-txt > .audit-reqs.txt
	uvx pip-audit --strict --disable-pip --no-deps -r .audit-reqs.txt
	rm -f .audit-reqs.txt
```

Dev deps excluded: they never ship. Wire into `check: lint audit test`.

**npm audit:** `audit: node_modules` → `npm audit --audit-level=high --omit=dev`; wire
into `check`.

**ruff:** `select = ["E", "F", "I", "W", "S"]`, `per-file-ignores = { "tests/**" =
["S101", "S105", "S106"] }`. Expect hits on SQL built from fragments in `database.py`
(S608). Fix the real ones; `# noqa: S608 — <why safe>` for the rest (for example, column
names drawn from a fixed allowlist).

**Renovate config sketch:**

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:recommended", "helpers:pinGitHubActionDigests", ":dependencyDashboard", "docker:pinDigests"],
  "schedule": ["before 6am on monday"],
  "timezone": "America/Los_Angeles",
  "lockFileMaintenance": { "enabled": true, "schedule": ["before 6am on the first day of the month"] },
  "vulnerabilityAlerts": { "enabled": true, "schedule": ["at any time"], "labels": ["security"] },
  "packageRules": [
    { "matchUpdateTypes": ["minor", "patch"], "groupName": "{{manager}} non-major" },
    { "matchUpdateTypes": ["patch", "digest", "pin", "pinDigest"], "automerge": true },
    { "matchDepTypes": ["devDependencies", "dev"], "matchUpdateTypes": ["minor", "patch"], "automerge": true },
    { "matchUpdateTypes": ["major"], "automerge": false, "dependencyDashboardApproval": false }
  ]
}
```

Managers detected automatically: `pep621`/uv (`backend/uv.lock`), `npm`, `dockerfile`,
`docker-compose`, `github-actions`, `terraform`. Python base image: keep
`python:3.11-slim` (the project minimum); add a rule capping Python at `3.11` so Renovate
only bumps the digest, and leave version moves to an explicit item.

**security.yml shape:** three jobs. `deps` runs `make -C backend audit` and
`make -C frontend audit`. `image` runs `docker build` then Trivy `image` and uploads
SARIF. `iac-secrets` runs Trivy `config infra/` and `fs --scanners secret .` and uploads
SARIF. Triggers: `pull_request`, `schedule: '0 13 * * 1'`, `workflow_dispatch`. Install
Trivy through `aquasecurity/setup-trivy`, or use `trivy-action`, SHA-pinned either way.
Pin the Trivy version too.

**Weekly rebuild:** the scheduled `image` job builds a fresh image from pinned digests
and scans it. Renovate's digest bumps are what pull in base-image patches. Redeploying
stays manual (`make deploy`); CI gets no AWS credentials.

**Touches:**

- `Dockerfile` (mod): node 22, digest pins.
- `.github/workflows/ci.yml` (mod): SHA pins, permissions, node 22.
- `.github/workflows/security.yml` (new)
- `renovate.json` (new)
- `.trivyignore` (new, header comment only)
- `Makefile` (mod): `tf-check` → Trivy; drop Checkov.
- `backend/Makefile` (mod): `audit` target, wired into `check`.
- `frontend/Makefile` (mod): `audit` target, wired into `check`.
- `backend/pyproject.toml` (mod): ruff `S` + per-file-ignores.
- `backend/src/pktx/**` (mod): ruff `S` fixes / reasoned `noqa`.
- `.gitignore` (mod): `.audit-reqs.txt`.
- `docs/deployment.md` and `CONTRIBUTING.md` (mod): settings steps, Trivy install, waivers.
- `AGENTS.md` (mod): tech list, recent changes, drop Checkov mention.
- `specs/lite/roadmap.md` (mod): status.

## Steps

- [x] 1. Dockerfile: `node:22-slim`; resolve the current digest for every base image
      (`docker buildx imagetools inspect <img>`) and pin `name:ver@sha256`. Pin `uv` to the
      current release. `docker build .` succeeds.
- [x] 2. CI: `setup-node` 22; pin every Action to a SHA (`gh api
      repos/<o>/<r>/commits/<tag> --jq .sha`); add `permissions` and
      `persist-credentials: false`.
- [x] 3. ruff `S`: enable it, run `uv run ruff check .`, triage every hit (fix it, or
      `noqa` with a reason). `make -C backend lint` is green.
- [x] 4. `audit` targets in the backend and frontend Makefiles, wired into `check`. Fix or
      waive any current findings (bump in the lock; record a waiver only when no fix
      exists).
- [x] 5. Replace Checkov with Trivy `config` in `tf-check` (PATH binary, install hint if missing).
      Triage findings; waive in `.trivyignore` with a reason and an expiry.
- [x] 6. Write `security.yml` (three jobs, SARIF upload, PR + weekly + dispatch).
- [x] 7. Write `renovate.json`; validate with `renovate-config-validator`.
- [x] 8. Docs: manual settings checklist (below), Trivy local install, waiver convention.
      Update AGENTS.md.
- [x] 9. `make check` green locally; push the branch; both workflows green on the PR.

**Manual steps for the user** (documented, not automated — settings are theirs):

1. Install the Renovate GitHub App (https://github.com/apps/renovate) on this repo only.
2. Settings → General: enable **Allow auto-merge**.
3. Rules for `main`: require the status checks `check`, `image` and `iac-secrets`
   (without this, automerge merges untested code).
4. Settings → Code security: Dependabot alerts **on** (Dependabot security updates
   **off**, so Renovate owns PRs), secret scanning + push protection **on**, CodeQL
   **default setup** (Python, JS/TS, Actions).

## Build notes (where the build differed from the plan)

- **Audits found real CVEs.** Bumped 13 Python packages in `uv.lock` (pyjwt 2.11→2.15.1,
  mcp 1.26→1.30, urllib3, requests, anyio, idna, pyasn1, …) and ran `npm audit fix`
  (react-router 7.18.4, @clerk/clerk-react 5.61.10, js-cookie 3.0.7).
- **Removed the unused `clerk-backend-api`.** Nothing imported it, and it capped
  `cryptography` below 47, blocking the fix (46.0.4 → 50.0.2).
- **One pip-audit waiver:** `PYSEC-2026-1325` (ecdsa, no upstream fix; python-jose uses
  the cryptography backend). Expires 2027-01-01. Real fix: replace python-jose with
  pyjwt (follow-up).
- **Dev-only:** vitest 2.x had a critical advisory. Upgraded to vitest 4 (drop-in, all
  tests green), so `npm audit` is 0 across all deps.
- **python-jose → PyJWT** (removes the ecdsa waiver) split out as roadmap item 029.
- **docs/deployment.md cleanup:** removed the nonexistent `terraform-ci.yml` / OIDC
  section; documented all 9 SSM parameters; fixed the claim that Lambda reads SSM at
  cold start (Terraform bakes the values into env vars at apply); arm64 + Clerk
  build-arg in the manual build; five-step `make deploy`. Fixed `make deploy` step 2,
  which skipped 3 SSM placeholders (`pktx_public_url`, `clerk_oauth_client_id`/`_secret`).
- **Dockerfile runtime stage** now runs `apt-get upgrade` (Debian had fixed libpcre2 but
  the pinned base didn't include it yet) and removes the system pip/setuptools (their
  vendored jaraco.context/wheel CVEs; the app runs from `/app/.venv`).
- **Non-root image (review fix):** the repo-wide Trivy misconfig SARIF flagged DS-0002
  (container runs as root). Added `USER pktx` (uid 10001). Verified with `docker compose
  up`: `/health` ok, SPA 200.
- **server.py:** the `_get_*_service` asserts became a `_require()` helper that raises,
  so `python -O` can't remove them. All S608 sites checked: every interpolated
  identifier comes from a fixed tuple/dict, so each got a reasoned `noqa`.
- **Trivy IaC:** the only HIGH was AWS-0031 (mutable ECR tags), waived inline.
  Existing `#checkov:skip` comments are left as documented rationale; Trivy ignores them.
- **`security.yml` `deps` job** runs on schedule/dispatch only, because PRs already audit
  through `make check`. The required checks are `check`, `image` and `iac-secrets`.
- **Actions** pinned to the SHAs of their current majors (checkout v4.4.0, …).
  Renovate will propose the majors.
- **zizmor one-off** (`uvx zizmor --offline`): 0 high; the 2 medium are a false
  positive (Trivy version pinned via `env`).

## Testing

```bash
make check
docker build -t pktx-scan .
trivy image --severity HIGH,CRITICAL --ignore-unfixed pktx-scan
trivy config --severity HIGH,CRITICAL infra/
trivy fs --scanners secret .
npx --yes --package renovate -- renovate-config-validator
```

Negative checks (run locally, don't commit): pin a known-vulnerable package (for example
`urllib3==1.26.0`) in a scratch export and confirm `pip-audit` fails; add a fake
`AKIA…` key to a scratch file and confirm Trivy's secret scan flags it. After merge,
confirm the Security tab shows Trivy and CodeQL results and Renovate opens its onboarding
PR / dependency dashboard issue.

## Out of scope

- **AWS Inspector / ECR enhanced scanning: deferred.** It rescans the deployed image
  continuously as new CVEs land, which is the one gap CI scans can't close. It has a small
  per-image cost. Revisit after prod is live (022) via
  `aws_ecr_registry_scanning_configuration` (`scan_type = "ENHANCED"`, rule
  `CONTINUOUS_SCAN` on `pktx-*`).
- gitleaks, zizmor, Checkov, Snyk/Socket, DAST (ZAP): see the research file.
- Automated deploys or giving CI AWS credentials.
- Python version upgrade beyond 3.11.
- CSP/security headers, rate limiting (open from 027 review, separate item).
