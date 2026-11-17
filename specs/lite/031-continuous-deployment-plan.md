---
roadmap_id: 031
issue: n/a
---

# Plan: 031 Continuous deployment: auto dev, gated prod

## Overview

Deploys today = manual `make deploy ENV=…` from laptop with long-lived AWS creds; CI
(`ci.yml`) runs `make check` on PRs only and never touches AWS. Image is rebuilt per env
because the Clerk publishable key is baked in at Vite build time. Target (see
`research/continuous-deployment.md`):

- **PR:** `make check` + `terraform plan` for `shared`, `dev`, `prod` posted as one sticky PR comment.
- **Merge to main:** `make check` → build image **once** (`linux/arm64`) → push `pktx-dev:sha-<sha>` →
  TF apply dev pinned to that digest → smoke test → tag `verified-<sha>`.
- **GitHub Release `v*` published:** `production` Environment (required reviewer) → copy the
  **same digest** dev verified into `pktx-prod` → TF apply prod → smoke test.
- **Rollback:** `workflow_dispatch` on the prod workflow with a previous release tag (one click).
- **AWS via GitHub OIDC**, no stored keys; separate least-privilege roles per env + read-only plan role.
- **Forward-compatible migrations** documented as a rule (expand → contract).
- `make deploy` kept as break-glass, rewritten to share the same scripts as CI.

## Acceptance criteria

- [x] No AWS access keys anywhere in GitHub (secrets or vars); workflows auth only via OIDC `aws-actions/configure-aws-credentials` with role ARNs from Environment variables.
- [x] `infra/shared` Terraform stack defines the GitHub OIDC provider and roles `pktx-gha-plan`, `pktx-gha-deploy-dev`, `pktx-gha-deploy-prod`; trust policies pin `aud=sts.amazonaws.com` and exact `sub`: plan → `repo:elnaterator/pktx:pull_request`, dev → `repo:elnaterator/pktx:environment:dev`, prod → `repo:elnaterator/pktx:environment:production`.
- [x] Deploy role policies are resource-scoped to their env (`pktx-<env>*` ECR/Lambda/IAM/logs/events/KMS-alias, `/pktx/<env>/*` SSM, that env's state bucket + lock table); no `*:*`, no `AdministratorAccess`; IAM writes limited to `role/pktx-<env>-*` and `iam:PassRole` only to the Lambda exec role with `iam:PassedToService=lambda.amazonaws.com`. Dev role cannot touch prod resources and vice versa.
- [x] Plan role is read-only (no write actions) and plan job never runs for fork PRs.
- [x] Image built exactly once per commit; the image contains no environment-specific values (no Clerk key baked in). Frontend reads the publishable key at runtime from `index.html` injected by the backend; `vite dev` still works via `VITE_CLERK_PUBLISHABLE_KEY`.
- [x] ECR repos are `IMMUTABLE`; `.trivyignore`/inline waiver `AWS-0031` removed.
- [x] Lambda is pinned by digest through Terraform (`image_uri = repo@sha256:…`), so TF apply and the running code never drift; `update-function-code` step removed.
- [x] Prod deploy refuses to run unless the release's commit has a `verified-<sha>` image in `pktx-dev`; prod image digest == dev-verified digest (asserted in workflow).
- [x] Smoke test script (`scripts/smoke.sh <url>`) checks `GET /health` 200, unauthenticated `POST /mcp` 401 with `WWW-Authenticate`, `GET /` 200 with injected publishable key; failing smoke fails the job.
- [x] One `concurrency` group per env, `cancel-in-progress: false`.
- [x] All new actions SHA-pinned, top-level `permissions: contents: read`, `id-token: write` only on jobs that assume a role; `persist-credentials: false` on checkout.
- [x] `make check` passes (incl. Trivy IaC on `infra/shared`); `actionlint` clean on all workflows.
- [x] `docs/deployment.md` describes bootstrap (one-time manual `infra/shared` apply), Environments setup, release/rollback flow, break-glass `make deploy`; AGENTS.md + constitution note the expand→contract migration rule.

## Open questions

- [x] Promotion: copy digest between per-env ECR repos vs one shared repo — _proposed: keep per-env repos, promote with `crane copy` (manifest bytes preserved → identical digest). Avoids destroying existing repos; prod Lambda never pulls from a dev-writable repo._
- [x] Runtime secrets still flow SSM → TF data source → Lambda env vars (so they sit in TF state and deploy roles need `/pktx/<env>/*` decrypt) — _proposed: keep for 031 (state bucket encrypted, private, per-env role); moving secret fetch into the app at cold start is a follow-up roadmap item._
- [x] Prod trigger — _proposed: `release: published` with tag `v*`, plus `workflow_dispatch(tag)` for rollback; both go through the `production` Environment reviewer gate._

## Design

**Runtime config instead of build-time Clerk key.** `SPAStaticFiles` serves `index.html` with
`<meta name="pktx-clerk-publishable-key" content="…">` filled from env `CLERK_PUBLISHABLE_KEY`
(HTML-escaped; cached rendered bytes; `Cache-Control: no-cache` on index.html). `main.tsx`
reads meta first, falls back to `import.meta.env.VITE_CLERK_PUBLISHABLE_KEY` (dev). Lambda gets
`CLERK_PUBLISHABLE_KEY` from the existing SSM param. Dockerfile drops the build arg.

**Image identity.** Tag `sha-<git sha>` (immutable). After dev smoke passes, add
`verified-<sha>` via `aws ecr put-image` with the same manifest. Prod: resolve release tag →
commit sha → `pktx-dev:verified-<sha>` digest → `crane copy` to `pktx-prod:sha-<sha>` →
assert digest equal → `terraform apply -var image_digest=…`.

**Terraform.** Lambda module: replace `image_tag` with `image_digest` (validated
`^sha256:[0-9a-f]{64}$`); `image_uri = "${repo_url}@${var.image_digest}"`. First-time env
bootstrap (repo empty) handled by the script: targeted apply of ECR + SSM, then push, then full
apply — same order `make deploy` uses today. New stack `infra/shared` (own state
`pktx-terraform-state-shared`, via `bootstrap.sh shared`) holds OIDC provider + 3 roles; applied
manually by the owner only (CI plans it, never applies it — a role can't safely grant itself
power).

**Scripts** (`scripts/deploy/`, bash, `set -euo pipefail`, shellcheck-clean), used by both
Make and workflows: `ensure-base.sh <env>` (targeted ECR + SSM apply), `build-push.sh <sha>`
(idempotent, 3× retry for ECR Public 429s), `apply.sh <env> <digest>`, `mark-verified.sh <sha>`,
`promote.sh <sha>`, `smoke.sh <url>`, `current-digest.sh <env>` and `plan.sh <stack>...` (PR plan).

**Permissions boundary (added during build).** Deploy roles manage the Lambda exec role, so
unscoped `iam:CreateRole`/`PutRolePolicy` would be an escalation path. `infra/shared` defines
`pktx-<env>-lambda-boundary`; deploy roles may only create/modify `pktx-<env>-*` roles carrying
it (`iam:PermissionsBoundary` condition), `DeleteRolePermissionsBoundary` is denied, and the
Lambda module sets `permissions_boundary` on the exec role.

**Workflows.**
- `ci.yml` (mod): adds `workflow_call` so deploy-dev reuses it; installs actionlint.
- `plan.yml` (new — split from ci.yml because a called workflow may not request more
  permissions than its caller): every same-repo PR (no paths filter, so it can be a required check), skipped until
  `vars.AWS_PLAN_ROLE_ARN` exists; `plan.sh` (`-lock=false`, account id masked) → sticky comment.
- `deploy-dev.yml` (new): `on: push main` → `uses: ./.github/workflows/ci.yml` check → `deploy`
  job on native `ubuntu-24.04-arm` (no QEMU), `environment: dev`, concurrency `deploy-dev`.
- `deploy-prod.yml` (new): `on: release published` + `workflow_dispatch(tag)`; `environment:
  production` (required reviewer, deployment tags `v*`), concurrency `deploy-prod`.

**Touches:**
- `infra/shared/{backend,provider,main,variables,outputs}.tf` (new), `infra/bootstrap.sh` (mod: `shared`)
- `infra/modules/lambda/{main,variables}.tf` (mod: digest, IMMUTABLE), `infra/{dev,prod}/{main,variables}.tf`, `terraform.tfvars` (mod: `image_digest`, `CLERK_PUBLISHABLE_KEY` env)
- `.trivyignore` / inline waiver (mod: drop AWS-0031)
- `scripts/deploy/{lib,ensure-base,build-push,apply,mark-verified,promote,smoke,current-digest,plan}.sh` (new)
- `Makefile` (mod: `deploy` → scripts; add `actionlint`, `shellcheck` to `check`)
- `.github/workflows/ci.yml` (mod), `plan.yml` (new), `deploy-dev.yml` (new), `deploy-prod.yml` (new), `security.yml` (mod: comment)
- `docker-compose.yml`, `.env.example`, `README.md` (mod: runtime `CLERK_PUBLISHABLE_KEY`)
- `Dockerfile` (mod: drop Clerk build arg)
- `backend/src/pktx/server.py` (mod: index.html injection), `backend/src/pktx/config.py` (mod)
- `frontend/src/main.tsx` (mod), `frontend/index.html` (mod: meta placeholder)
- tests: `backend/tests/unit/test_spa_index_config.py` (new), `frontend/src/__tests__/utils/clerkPublishableKey.test.ts` (new); `frontend/src/utils/clerkPublishableKey.ts` (new)
- `docs/deployment.md`, `AGENTS.md`, `.specify/memory/constitution.md` (mod)

## Steps

- [x] Runtime publishable key: meta placeholder in `index.html`, backend injection + escaping + tests, `main.tsx` resolver + test, Dockerfile drops build arg.
- [x] Lambda module: `image_digest` var, `image_uri` by digest, ECR `IMMUTABLE`, pass `CLERK_PUBLISHABLE_KEY`; update dev/prod stacks; drop AWS-0031 waiver.
- [x] `infra/shared` stack: OIDC provider, plan role, per-env deploy roles with scoped policies; `bootstrap.sh shared`.
- [x] `scripts/deploy/*.sh`; rewrite `make deploy` onto them (still `ENV=dev|prod`, builds from local HEAD as `sha-<sha>[-dirty refused]`).
- [x] Workflows: `ci.yml` (`workflow_call` + PR plan comment), `deploy-dev.yml`, `deploy-prod.yml`.
- [x] Add `actionlint` + `shellcheck` to `make check`.
- [x] Docs: deployment runbook (bootstrap, GitHub Environments `dev`/`production` + vars `AWS_ROLE_ARN`, `AWS_REGION`, release + rollback, break-glass), migration rule in AGENTS.md + constitution.
- [x] `make check`.

## Testing

Results (2026-11-17): `make check` green — frontend 614 tests, backend 931 tests, ruff/pyright
clean, Trivy IaC 0 findings (incl. `infra/shared`), actionlint + shellcheck clean;
`terraform validate` ok for shared/dev/prod. Built the image with no build args, confirmed no
key baked in, ran it with `CLERK_PUBLISHABLE_KEY` against local Postgres: `smoke.sh` passed all
three checks, `index.html` served `no-cache` with the injected key on SPA routes. Not exercised:
real AWS (OIDC roles, ECR promotion, apply) — needs the owner bootstrap in `docs/deployment.md`.

```bash
make check                                  # lint/type/test/audit + Trivy IaC + actionlint + shellcheck
cd backend && uv run pytest tests/integration/test_static_serving.py
cd frontend && npm run test
terraform -chdir=infra/shared init -backend=false && terraform -chdir=infra/shared validate
terraform -chdir=infra/dev init -backend=false && terraform -chdir=infra/dev validate
docker buildx build --platform linux/arm64 . && docker run … -e CLERK_PUBLISHABLE_KEY=pk_test_x  # meta injected
scripts/deploy/smoke.sh http://localhost:8000
```

Manual (post-merge, owner): apply `infra/shared`, create Environments, merge → watch dev deploy
+ smoke; prod first run belongs to 022.

## Out of scope

- Standing up / first deploy of prod (022).
- Moving runtime secrets out of TF state / Lambda env (follow-up item).
- Lambda aliases / weighted traffic shifting, release-please automation.
- Error tracking / alerting on failed deploys beyond GitHub's own notifications (021).
