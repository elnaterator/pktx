---
roadmap_id: 038
issue: n/a
---

# Plan: 038 Runtime secrets out of Terraform state and Lambda env

Branch: `chore/038-runtime-secrets`

## Overview

Today secrets flow SSM SecureString → `data "aws_ssm_parameter"` (`with_decryption`) →
Lambda env vars. So every value sits in Terraform state, in the Lambda config, and the CI
plan role + both deploy roles hold `kms:Decrypt` via SSM on `/pktx/*`. A compromised CI
job can read prod secrets; rotation needs an apply. Follow-up from 031
(`research/continuous-deployment.md` § Follow-up).

In scope:

- App fetches its secrets from SSM at cold start; Lambda env carries the parameter prefix
  only.
- Non-secret config (public URL, Clerk publishable key / issuer / JWKS URL / OAuth client
  id) becomes plain tfvars → env vars, no SSM.
- Terraform no longer reads *or manages* secret parameters → nothing secret in state, and
  CI roles lose SSM read + SSM-path decrypt entirely.
- Rotation = `put-parameter` + recycle instances, no apply.
- Local / docker-compose / tests unchanged: plain env vars, SSM only when the prefix is set.

## Acceptance criteria

- [ ] `terraform state pull` for dev contains none of the 4 secret values and no
      `aws_ssm_parameter` resource or data source.
- [ ] Lambda env (`get-function-configuration`) has no secret values — only
      `PKTX_SSM_PREFIX` plus non-secret config.
- [x] `pktx-gha-plan` and `pktx-gha-deploy-<env>` policies have no `ssm:GetParameter*` and
      no `kms:Decrypt` scoped to SSM parameters; `terraform plan` of dev/prod/shared still
      succeeds under the plan role.
- [x] Exec role can `ssm:GetParameters` on exactly the 4 secret names and decrypt via SSM
      (`kms:ViaService` condition), and the env boundary still permits it.
- [x] App with `PKTX_SSM_PREFIX` set loads secrets into config before any resolver runs;
      an explicitly set env var wins over SSM; missing/unreachable SSM fails start with one
      clear log line naming the missing parameter(s) (never the value).
- [x] App without `PKTX_SSM_PREFIX` makes no AWS call (unit test asserts no client built).
- [ ] Dev deploy through CI goes green (smoke test passes) after the change.
- [ ] Rotation documented and verified on dev: `put-parameter` + recycle, no apply.
- [x] `docs/deployment.md`, `AGENTS.md` (CD section), research note updated.
- [x] `make check` green.

## Open questions

- [x] **SSM client** — _proposed: add `boto3` as a direct dep, imported lazily only when
      `PKTX_SSM_PREFIX` is set._ Standard, signed, retries. Cost: ~+20 MB image, ~100–200 ms
      import on cold start (keep-warm hides most). Alternatives: hand-rolled SigV4 over
      `urllib` (no dep, ~60 lines to own and get right), or the AWS Parameters and Secrets
      Lambda Extension (ships as a layer zip, awkward for a container image build).
- [x] **Who creates secret parameters** — _proposed: owner only, out of Terraform._
      Terraform's `aws_ssm_parameter` resource always reads with decryption on refresh, so
      keeping placeholders in TF keeps the CI decrypt grant. Drop the 4 secret resources via
      `removed { lifecycle { destroy = false } }` (parameters stay in AWS), drop SSM from
      `ensure-base.sh`, and add a `scripts/deploy/check-secrets.sh` (owner creds, names +
      `DescribeParameters` only, no values) used by the runbook. CI deploy role keeps no
      `ssm:PutParameter` either.
- [x] **Non-secret params in SSM** (`pktx_public_url`, `clerk_publishable_key`,
      `clerk_issuer`, `clerk_jwks_url`, `clerk_oauth_client_id`) — _proposed: move to
      per-env `terraform.tfvars` as plain values; delete those SSM parameters after the
      cutover deploy (contract step)._ They are public or near-public and some feed TF
      logic (`authorized_parties` regex), so runtime fetch would be needless.
- [x] **Old state versions still hold secrets** (S3 versioning) — _proposed: after cutover,
      rotate the 4 secrets (Neon password, Clerk secret key, webhook secret, OAuth client
      secret) and prune pre-cutover state object versions; documented as a one-time runbook
      step, done by owner, not automated._

_All four accepted as proposed (2026-11-23)._

## Design

**Secrets (SSM SecureString, `/pktx/<env>/<name>`)** → env var they fill:

| Parameter | Env var |
|-----------|---------|
| `database_url` | `PKTX_DB_URL` |
| `clerk_secret_key` | `CLERK_SECRET_KEY` |
| `clerk_webhook_secret` | `CLERK_WEBHOOK_SECRET` |
| `clerk_oauth_client_secret` | `CLERK_OAUTH_CLIENT_SECRET` |

**App:** new `pktx/secrets.py` with `load_ssm_secrets()` — no-op unless `PKTX_SSM_PREFIX`;
else one `GetParameters(Names=[4 names], WithDecryption=True)`, `InvalidParameters`
non-empty → raise with the names; for each hit `os.environ.setdefault(env_var, value)`
(explicit env wins, handy for break-glass overrides). Called first thing in
`server.main()` (before any `resolve_*`). Filling `os.environ` keeps every existing
resolver and `routes.py`'s webhook lookup untouched — one seam, no config refactor. Values
never logged. Mapping is a module constant; a unit test asserts it matches the Terraform
`secret_names` list (cheap drift guard).

**Terraform (`infra/dev`, `infra/prod`, identical):**

- `variables.tf` + `terraform.tfvars`: `public_url`, `clerk_publishable_key`,
  `clerk_issuer`, `clerk_jwks_url`, `clerk_oauth_client_id`.
- Env vars: those five plain + `PKTX_SSM_PREFIX = "/pktx/${var.environment}"`.
  `authorized_parties` regex reads `var.public_url`.
- Delete all `data "aws_ssm_parameter"`; `removed {}` blocks (destroy = false) for all 9
  `aws_ssm_parameter` resources.
- Lambda module `ssm_read` policy: `ssm:GetParameters` on the 4 secret ARNs (new var
  `secret_names`); `kms:Decrypt` on `key/*` with `kms:ViaService = ssm.<region>` +
  `kms:EncryptionContext:PARAMETER_ARN` like `/pktx/<env>/*` (current
  `key/alias/aws/ssm` resource is not a valid key ARN match — fix it).

**Shared (`infra/shared`, owner-applied):**

- Plan role: drop `ssm:GetParameter(s)` from `AppRead`, drop `SsmDecrypt`; keep
  `ssm:DescribeParameters` only if still needed (it isn't once TF manages no params → drop).
- Deploy roles: drop the `Ssm` statement and `KmsViaSsm`.
- Boundary: keep `SsmRead` + SSM `kms:Decrypt` (the exec role needs them).

**Rollout (expand → contract):**

1. `infra/shared` narrows last, never first. Order: (a) merge app + env TF change;
   CI deploys dev with the old (wider) CI roles; the `removed` blocks drop SSM from state.
   (b) Verify dev, release to prod. (c) Owner applies `infra/shared` to narrow CI roles.
   (d) Owner deletes the 5 now-unused non-secret parameters, rotates secrets, prunes state
   versions.
2. Old image + new env (rollback): old image expects secrets in env → rollback across the
   cutover breaks. Mitigation: documented — rollback to a pre-038 release requires a
   break-glass apply of the pre-038 Terraform. Acceptable for a one-time cutover; call it
   out in the release notes.

**Touches:**

- `backend/src/pktx/secrets.py` (new), `backend/src/pktx/server.py` (mod),
  `backend/pyproject.toml` + `uv.lock` (mod, boto3)
- `backend/tests/unit/test_secrets.py` (new)
- `infra/modules/lambda/main.tf`, `variables.tf` (mod)
- `infra/dev/main.tf`, `variables.tf`, `terraform.tfvars` (mod); same for `infra/prod`
- `infra/shared/main.tf` (mod)
- `scripts/deploy/ensure-base.sh` (mod), `scripts/deploy/check-secrets.sh` (new)
- `.github/workflows/deploy-dev.yml`, `deploy-prod.yml` (mod: step name "Ensure ECR repo")
- `docs/deployment.md`, `research/continuous-deployment.md`, `AGENTS.md` (mod)

## Steps

- [x] `secrets.py` + unit tests (stubbed client: no prefix → no call; fills unset vars;
      env wins; invalid params → error naming them; value never in log/exception text).
- [x] Wire `load_ssm_secrets()` at top of `server.main()`; add `boto3` (lazy import).
- [x] Lambda module: `secret_names` var, tightened exec `ssm_read` policy.
- [x] dev/prod: tfvars for non-secret config, plain env vars + `PKTX_SSM_PREFIX`, delete
      data sources, `removed` blocks for the 9 parameter resources.
- [x] `ensure-base.sh` → ECR only; new `check-secrets.sh` (names exist + not
      `TO_BE_SET` check via owner creds); workflow step rename.
- [x] `infra/shared`: strip SSM read/decrypt from plan + deploy roles (applied last, by
      owner).
- [x] Docs: runbook bootstrap (owner creates 4 SecureStrings), rotation (put-parameter +
      `aws lambda update-function-configuration --description "rotate <date>"` to recycle),
      cutover/rollback note, one-time rotate + state-version prune; AGENTS.md CD section;
      research note "done".
- [x] `make check`; `terraform plan` dev/prod locally shows only expected changes
      (env vars, policy, `removed` forgets, no destroys).

## Build notes (deviations from design)

- `CLERK_JWKS_URL` is derived from `clerk_issuer` (`<issuer>/.well-known/jwks.json`) instead of its own tfvar; matches both envs' current values.
- Lambda module keeps `environment_variables` `sensitive = true`: no secrets go in any more, but older state versions carry them and the flag keeps plans from echoing them.
- Exec-role KMS grant fixed: was `key/alias/aws/ssm` (never matches a key ARN); now `key/*` with `kms:ViaService` + `PARAMETER_ARN` condition.
- Rollback across 038 is **not supported** (old Terraform would re-create forgotten parameters; old image expects env secrets) — documented, fix forward.
- `check-secrets.sh` reads names from `secret_names` in `infra/<env>/main.tf` (bash 3.2-safe for macOS).

## Verified locally

- `make check` green (backend 939 tests incl. `test_secrets.py`, frontend 614, ruff, pyright, pip-audit, Trivy IaC, actionlint, shellcheck).
- `terraform plan` dev: 9 `aws_ssm_parameter` forgotten (not destroyed), only `ssm_read` policy + Lambda env change. Prod: same plus pre-existing 031 drift (ECR lifecycle policy, repo, exec role) not from this change. Shared: deploy roles lose `Ssm` + `KmsViaSsm`, plan role loses SSM read + `SsmDecrypt`.
- Loader against real dev SSM (owner creds): all 4 env vars filled, ~0.5 s incl. boto3 import from a laptop.
- `scripts/deploy/check-secrets.sh dev`: all 4 ok.

Pending until after merge/deploy: dev CI deploy + smoke, state/env inspection, rotation drill, then shared apply + cutover steps (`docs/deployment.md` § One-time cutover).

## Testing

- `cd backend && make check` (unit tests for `secrets.py`, pyright, ruff).
- `make check` at root (Trivy IaC, actionlint, shellcheck).
- `terraform -chdir=infra/dev plan` (owner creds): no `aws_ssm_parameter` destroy, data
  sources gone, env vars changed as expected.
- After dev deploy: `terraform state pull | grep -c -E 'postgres|sk_|whsec_'` → 0;
  `aws lambda get-function-configuration` shows no secret values; smoke green.
- Rotation drill on dev: put a new `clerk_webhook_secret`, recycle, confirm new instance
  uses it (webhook signature test or log of parameter version, not value).
- After shared apply: re-run a PR plan job + a dev deploy → both green without SSM perms.

## Out of scope

- Secrets Manager / automatic rotation.
- Customer-managed KMS key for SSM parameters (stay on `alias/aws/ssm`).
- Refreshing secrets without a recycle (TTL cache) — cold-start fetch only.
- Moving other non-AWS secrets (GitHub, Clerk dashboard) anywhere.
