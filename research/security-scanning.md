# Security scanning + automated patching (2026-10-03)

Feeds roadmap item 028. Constraint: **free only, low tool count.** Repo is public, so
GitHub's code scanning, secret scanning and push protection cost nothing.

## Current state

- `.github/workflows/ci.yml`: one `make check` job, `pull_request` only, no schedule.
- `make tf-check` runs `uvx checkov -d infra/`. No `checkov:skip` annotations exist.
- No dependency audit, no image scan, no secret scan, no update bot.
- Dockerfile: `node:18-slim` (EOL April 2025, no patches), `ghcr.io/astral-sh/uv:latest`
  (unpinned), `python:3.11-slim` and `aws-lambda-adapter:0.8.4` (tag-pinned, no digest).
- Actions pinned by mutable tag (`@v4`), not by SHA.
- Deploy is manual (`make deploy`); CI never touches AWS. Item 028 keeps it that way.

## Decisions

| Concern | Choice | Why |
|---|---|---|
| Update bot | Renovate (Mend-hosted GitHub App, free) | handles `uv.lock`, npm, Dockerfile digests, Action SHAs and Terraform providers in one config; Dependabot's uv + SHA support is weaker |
| Advisory alerts | Dependabot alerts on, Dependabot PRs off | free backstop if Renovate config breaks; Renovate opens the PRs |
| Python dependency CVEs | `pip-audit` (via `uvx`, OSV database) | audits the locked env with no new project dependency |
| npm dependency CVEs | `npm audit --audit-level=high --omit=dev` | built into npm |
| Python SAST | ruff `S` (bandit) rules | already-installed linter |
| Image + IaC + secrets | Trivy (`image`, `config`, `fs --scanners secret`) | one binary covers three jobs; **replaces Checkov** |
| Taint / JS-TS / workflow SAST | CodeQL **default setup** (repo settings toggle) | no file or tool in the repo; see below |
| Secret blocking | GitHub secret scanning + push protection | free on public repos, stops the push before the leak |
| gitleaks | **skip** | duplicates push protection + Trivy secret scanner |
| zizmor | **skip** | CodeQL `actions` language covers workflow injection; hygiene rules applied by hand |
| AWS Inspector (ECR enhanced scanning) | **deferred** | small per-image cost; revisit after prod (022). Rescans the deployed image as new CVEs land, which is the one gap CI can't close |
| Checkov, Snyk, Socket, DAST (ZAP) | out | Trivy replaces Checkov; the others are paid or overkill |

### CodeQL vs ruff `S`: overlap or needed?

Some overlap: both flag simple Python patterns (`eval`, `subprocess(shell=True)`, weak
hashes). They differ in three ways:

- **ruff `S` only matches patterns** in one expression. CodeQL follows **dataflow**:
  request input → SQL string / file path / redirect / outbound URL. That's the class of
  bug 027 fixed by hand.
- **JS/TS**: nothing else in the stack scans the frontend. ESLint has no security plugin
  configured.
- **GitHub Actions**: CodeQL's `actions` language catches `${{ github.event.* }}`
  injection and unsafe `pull_request_target`, which is zizmor's core.

Default setup costs nothing in the repo (no workflow file, no local tool) and runs on PRs
and weekly. Keep it, and drop zizmor and gitleaks instead.

### Renovate setup (free)

1. Install https://github.com/apps/renovate on `elnaterator/pktx` only.
2. Renovate opens an onboarding PR. Commit `renovate.json` on the branch first so
   onboarding picks it up.
3. Repo settings: enable **Allow auto-merge**. Branch protection on `main` must require
   the CI `check` and `security` jobs, otherwise automerge merges untested.
4. Repo settings → Code security: enable Dependabot alerts, secret scanning, push
   protection, CodeQL default setup.

Config intent: weekly schedule (`before 6am on monday`), group non-major updates per
ecosystem, automerge patch + devDependencies + Action digests after CI, majors open
separately with no automerge, `vulnerabilityAlerts` skip the schedule, dependency
dashboard on, `pinDigests` for Docker, `helpers:pinGitHubActionDigests`,
`lockFileMaintenance` monthly.

## Workflow hygiene (in place of zizmor)

- Top-level `permissions: contents: read`; widen per job only (`security-events: write`
  for SARIF upload).
- `actions/checkout` with `persist-credentials: false`.
- No `pull_request_target`. No `${{ github.event.* }}` inside `run:`.
- Every `uses:` pinned to a full SHA with a `# vX.Y.Z` comment so Renovate can bump it.

## Scheduled scans

A weekly cron re-runs pip-audit, npm audit and Trivy against a freshly built image. New
CVEs show up in code that hasn't changed, mostly in the base image's OS packages. CI only
builds and scans; deploying a rebuilt image stays manual (`make deploy`). Trivy goes red
on HIGH/CRITICAL with a fix available (`--ignore-unfixed`); waivers live in
`.trivyignore` with a reason and an expiry date.
