# Continuous deployment

## Current state (2026-10-04)

- CI (`.github/workflows/ci.yml`): `make check` on `pull_request` only.
- Deploy: manual `make deploy ENV=dev|prod` from laptop — targeted TF apply (ECR + SSM),
  docker build + push `:latest`, full TF apply, `update-function-code` to digest.
- Lambda container + Function URL; Neon Postgres; migrations run in app.
- Repo is **public** → GitHub Environments with required reviewers are free.

## Target

```
PR ──► CI (make check, terraform plan dev+prod as PR comment)
merge to main ──► CI again ──► build image ONCE, tag :sha, push ECR
                └─► deploy dev (TF apply + update-function-code @digest) ──► smoke test /health + /mcp 401
release (manual) ──► environment "production" (required reviewer) ──► deploy SAME digest to prod ──► smoke
```

## Best practice: triggering prod

Recommended: **GitHub Release / tag `v*` triggers prod, gated by a `production`
Environment with a required reviewer (you).**

- **Build once, promote the artifact.** Prod deploys the exact image digest already
  running and smoke-tested in dev — never rebuild for prod. Resolve tag → commit sha →
  ECR digest; fail if no dev-verified image exists.
- **Human gate = Environment protection rule**, not "remember to run a command".
  Required reviewer, `main`/`v*` deployment branch policy, optional wait timer.
  Approval UI + audit log free on public repos.
- **Release as trigger** gives a changelog + version for free. Optionally
  release-please to draft releases from conventional commits (already used).
  `workflow_dispatch` with a `ref`/`digest` input kept as escape hatch + rollback path.
- **Rollback** = re-run prod deploy with previous release's digest (one click).
  Lambda alias / weighted traffic shifting is overkill for now.
- **AWS auth via GitHub OIDC**, no long-lived keys. Separate IAM roles per env; prod role
  trust policy restricted to `repo:elnaterator/pktx:environment:production`. Roles
  defined in Terraform (bootstrap stack).
- **Concurrency group per env** (`cancel-in-progress: false`) so deploys never overlap.
- **TF plan on PR**, apply only in deploy job; state lock already in DynamoDB.
- **Migrations forward-compatible** (expand → contract): dev runs ahead of prod, and a
  rollback must not hit a schema it can't read.
- **Smoke test** after each deploy; failure marks deployment failed + notifies.
- Secrets stay in SSM; workflow only needs role ARN + region (Environment variables).

## Open questions

- Who/what creates OIDC provider + deploy roles first time (manual bootstrap vs
  `infra/bootstrap.sh`).
- Overlap: 022 stands up prod environment. CD item builds the pipeline; first prod
  release via it can be 022's kickoff. Keep 022 for the soak/beta-readiness part.
- `make deploy` kept for local break-glass, refactored to share steps with CI.

## Follow-up: runtime secrets out of Terraform (2026-11-17, from 031)

031 kept the existing secret flow: SSM SecureString → `data "aws_ssm_parameter"` →
Lambda env vars. Consequences:

- Every secret value sits in Terraform state (S3, encrypted, private) and in the Lambda
  config (KMS-encrypted env vars).
- Both the read-only PR plan role and each deploy role need `kms:Decrypt` via SSM on
  `/pktx/<env>/*`, so a compromised CI job can read that env's secrets.
- Rotating a secret needs a Terraform apply.

Target: Lambda env carries **parameter names** only (e.g. `PKTX_SSM_PREFIX=/pktx/<env>`);
the app fetches SecureStrings at cold start (one `GetParametersByPath`, cached for the
instance lifetime) using the exec role it already has (`ssm_read` policy). Terraform keeps
creating placeholder parameters (`ignore_changes = [value]`) but drops the secret data
sources. Then:

- Deploy + plan roles lose `/pktx/<env>/*` decrypt (keep `ssm:DescribeParameters` /
  metadata reads so Terraform can manage the placeholders; check whether the provider's
  `aws_ssm_parameter` refresh still decrypts and, if so, whether `insecure_value` or
  managing placeholders outside TF is cleaner).
- Rotation = `put-parameter` + recycle instances (`update-function-configuration` no-op
  or publish), no apply.
- Local / docker-compose keep plain env vars: SSM lookup only when the prefix env is set.

Cost: ~50–150 ms extra cold start for one SSM call (keep-warm hides most of it); a
startup failure mode if SSM is unreachable (fail fast with a clear log line).
`CLERK_PUBLISHABLE_KEY` is not secret and can stay a plain env var.

**Done in 038 (2026-11-23).** As above, with two changes: Terraform no longer manages the
secret parameters at all (the provider's `aws_ssm_parameter` refresh always decrypts, so
keeping placeholders would keep CI's decrypt grant; `removed` blocks forget them, the owner
sets them, `scripts/deploy/check-secrets.sh` checks them), and the app uses
`GetParameters` on an explicit name list instead of `GetParametersByPath`, so the exec role
reads exactly four parameters. Non-secret config moved to tfvars. Measured locally:
~0.5 s for boto3 import + one call from a laptop; in-region cold start is less.
