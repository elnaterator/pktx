# Deploying to AWS

pktx runs on **AWS Lambda** (arm64) as a container image stored in **ECR**. All AWS resources are defined in Terraform under `infra/`:

| Stack | What | Applied by |
|---|---|---|
| `infra/shared` | GitHub OIDC provider, CI roles, Lambda permissions boundaries | The owner, by hand (CI only plans it) |
| `infra/dev`, `infra/prod` | ECR repo, Lambda + Function URL, IAM exec role, KMS key, logs, alarm, keep-warm | CI (`deploy-dev.yml`, `deploy-prod.yml`); `make deploy` as break-glass |

Each stack has its own state bucket; Terraform locks state with an S3 lock file (`use_lockfile`), so there are no DynamoDB tables. CI runs Terraform 1.17 with the AWS provider 6.x; provider versions and hashes are pinned in each stack's committed `.terraform.lock.hcl`.

## How a change ships

```
PR ──► ci.yml: Frontend | Backend | Infra + CI lint (parallel) ──► check     plan.yml: terraform plan (shared, dev, prod) → sticky PR comment
merge to main ──► deploy-dev.yml (one job each):
                  CI checks ──► Build image (ONCE → pktx-dev:sha-<sha>) ──► Deploy dev (terraform apply @digest)
                  ──► Smoke test dev ──► Mark verified for prod (tag pktx-dev:verified-<sha>)
publish release v* ──► deploy-prod.yml (one job each):
                  Resolve release ──► Deploy prod [production Environment: you approve]
                  (copy the verified digest → pktx-prod:sha-<sha>, terraform apply prod @digest) ──► Smoke test prod
```

Each stage is its own job, so the run graph in the Actions tab reads as the pipeline. Jobs that only need credentials (build, mark verified) use the `dev` environment with `deployment: false`, so the environment's history records one deployment per run. Smoke-test jobs get no AWS credentials. `check` is the ruleset's required status; it passes only when all three CI jobs pass.

- **Build once, promote the artifact.** The image has no per-environment config: the server injects the Clerk publishable key into `index.html` at serve time (`CLERK_PUBLISHABLE_KEY`). Prod runs the byte-identical image dev ran and smoke-tested. `deploy-prod` refuses a commit with no `verified-<sha>` image and checks the prod digest equals the dev digest.
- **Lambda is pinned by digest through Terraform** (`image_uri = repo@sha256:…`). ECR tags are immutable. Terraform state and what's running never drift.
- **No AWS keys in GitHub.** Workflows log in through GitHub OIDC. Each role trusts exactly one subject:

  | Role | Trusted subject | Can |
  |---|---|---|
  | `pktx-gha-plan` | `<prefix>:pull_request` | Read only (no state lock, no writes) |
  | `pktx-gha-deploy-dev` | `<prefix>:environment:dev` | Manage `pktx-dev*` resources only; no SSM access |
  | `pktx-gha-deploy-prod` | `<prefix>:environment:production` | Manage `pktx-prod*` resources only, plus read `pktx-dev` images to promote; no SSM access |

  `<prefix>` is the repo's OIDC subject prefix. This repo uses GitHub's immutable subject claims, so it is `repo:elnaterator@1914672/pktx@1152434568` (owner and repo ids, not just names): a renamed or re-created repo can't assume the roles. It is the `github_sub_prefix` variable in `infra/shared`.

  Deploy roles can only create or modify IAM roles named `pktx-<env>-*` that carry the env's permissions boundary (`pktx-<env>-lambda-boundary`). They cannot remove a boundary, delete ECR repos or images, or touch the other env. Plan runs only on same-repo PRs; fork PRs get no OIDC token.
- **Deploys never overlap.** Each env has one concurrency group and never cancels a run in progress. A newer queued run replaces an older queued one, so the tip of `main` is what lands.
- **Smoke test** (`scripts/deploy/smoke.sh`) after every deploy checks three things. A failure fails the run, and a dev image that fails is never marked verified.
  - `GET /health` returns 200.
  - Unauthenticated `POST /mcp` returns 401 with an OAuth challenge.
  - `GET /` serves the SPA with the injected key.

---

## Prerequisites (owner laptop)

| Tool | Install | Used for |
|------|---------|---------|
| [Terraform](https://developer.hashicorp.com/terraform/install) 1.11+ (CI: 1.17) | `brew install terraform` | everything |
| [AWS CLI](https://aws.amazon.com/cli/) 2.x | `brew install awscli` | bootstrap, secrets |
| Docker with `buildx` | Docker Desktop | break-glass `make deploy ENV=dev` |
| [crane](https://github.com/google/go-containerregistry) | `brew install crane` | break-glass `make deploy ENV=prod` |
| actionlint, shellcheck | `brew install actionlint shellcheck` | `make check` |

Owner AWS credentials (`aws configure` / `AWS_PROFILE`) are needed only for the one-time bootstrap, setting secrets and break-glass deploys.

### Values to collect

**Secrets** live only in SSM Parameter Store as SecureStrings under `/pktx/{env}/`. Terraform and CI never see them: the app reads them at cold start with its execution role (`backend/src/pktx/secrets.py`, triggered by the `PKTX_SSM_PREFIX` env var). The list is `secret_names` in `infra/{env}/main.tf`.

| SSM parameter (`/pktx/{env}/…`) | Where it comes from |
|---|---|
| `database_url` | Neon console → connection string (`?sslmode=require`) |
| `clerk_secret_key` | Clerk → API Keys (`sk_test_…` dev, `sk_live_…` prod) |
| `clerk_webhook_secret` | Clerk → Webhooks → endpoint `<public_url>/api/webhooks/clerk` → signing secret (`whsec_…`) |
| `clerk_oauth_client_secret` | Clerk → OAuth applications → the app below |

**Public configuration** lives in `infra/{env}/terraform.tfvars` (none of it is secret: it is served to browsers or appears in OAuth redirects):

| tfvar | Where it comes from |
|---|---|
| `public_url` | The app's public origin: the Lambda function URL (known after the first deploy) or your custom domain |
| `clerk_publishable_key` | Clerk → API Keys (`pk_test_…` / `pk_live_…`); injected into `index.html` at serve time |
| `clerk_issuer` | Clerk → API Keys → Frontend API URL; the JWKS URL is derived from it |
| `clerk_oauth_client_id` | Clerk → OAuth applications → app with redirect URI `<public_url>/auth/callback` |

`extra_client_redirect_uris`, `authorized_parties` and sizing are tfvars too. The image digest is never in tfvars; the deploy scripts pass it.

---

## One-Time Bootstrap

### 1. Remote state (per stack)

```bash
./infra/bootstrap.sh shared
```

```bash
./infra/bootstrap.sh dev
```

```bash
./infra/bootstrap.sh prod
```

Each creates a versioned, encrypted, private S3 bucket `pktx-terraform-state-<stack>`, which holds the state and its lock file. It is not Terraform-managed (that would be circular).

### 2. CI identity (`infra/shared`)

```bash
terraform -chdir=infra/shared init
```

```bash
terraform -chdir=infra/shared apply
```

```bash
terraform -chdir=infra/shared output
```

If the account already has a GitHub OIDC provider, import it first. The address is `aws_iam_openid_connect_provider.github`, and the ID is `arn:aws:iam::<account>:oidc-provider/token.actions.githubusercontent.com`.

Re-apply this stack by hand whenever a PR changes it. CI never applies it, because a role must not be able to widen its own permissions.

### 3. GitHub settings

All of these are free on a public repo.

1. **Settings → Environments → `dev`**: deployment branches = `main` only. Variable `AWS_ROLE_ARN` = `deploy_role_arns["dev"]`.
2. **Settings → Environments → `production`**:
   - **Required reviewers** = you.
   - Deployment branches and tags = **Selected**, add the tag rule `v*`.
   - Variable `AWS_ROLE_ARN` = `deploy_role_arns["prod"]`.
3. **Settings → Secrets and variables → Actions → Variables (repository)**:
   - `AWS_PLAN_ROLE_ARN` = `plan_role_arn`. Until this is set, `plan.yml` skips.
   - Optional: `AWS_REGION` (default `us-west-2`).
   - Optional: `TF_PLAN_STACKS` (default `shared dev prod`). Drop `prod` until prod's state exists.
4. **Rulesets → `main`**: add `check` and `plan` to the required status checks (alongside `image` and `iac-secrets`).

There are no AWS secrets to add. If you find an `AWS_ACCESS_KEY_ID` in repo secrets, delete it.

### 4. First deploy of an environment

The app refuses to start until its secrets exist. With owner creds:

1. Fill in the env's public config in `infra/{env}/terraform.tfvars`.
2. Create each secret (repeat per name in `secret_names`; first command below).
3. Check them (second command; prints names only, never values).
4. Deploy. For dev: merge to `main`, or run `make deploy ENV=dev`. For prod: publish a release (see below).

```bash
aws ssm put-parameter --region us-west-2 --name /pktx/dev/database_url \
  --value "postgresql://..." --type SecureString --overwrite
```

```bash
scripts/deploy/check-secrets.sh dev
```

`public_url` (and the Clerk webhook and OAuth redirect URIs that depend on it) can only be known once the function URL exists unless you use a custom domain. Deploy once, set it, then deploy again.

---

## Releasing to prod

1. Make sure the commit has deployed to dev: the **Deploy dev** run for it must be green. That run tags the image `verified-<sha>`.
2. Publish a release, either from **GitHub → Releases → Draft a new release** (tag `vX.Y.Z` on that commit, generate notes) or with `gh` (command below).
3. Approve the waiting **production** deployment in the Actions run.
4. The workflow copies the verified image into `pktx-prod`, applies Terraform at the release's commit, and smoke tests.

```bash
gh release create v1.4.0 --target <sha> --generate-notes
```

### Rollback

Re-deploy an earlier release in one step. Infra and image both go back to that release (Terraform runs from the tag's commit), and it still needs approval.

```bash
gh workflow run deploy-prod.yml -f tag=v1.3.2
```

The prod ECR repo keeps the 30 newest release images (`images_to_keep`). Older tags have to be promoted again from dev, and only while dev still has them.

Rollback is safe only if the older code can read the current schema (see the next section), and never to a release older than 038 (see "Updating secrets").

---

## Database migrations: expand → contract

Dev runs ahead of prod, and a rollback runs old code against a schema that has already migrated. Every migration in `backend/src/pktx/migrations.py` must therefore be **forward-compatible**: the previous release must keep working against the new schema.

- **Expand first:** add nullable columns or tables, and backfill. Never rename or drop a column that released code still reads or writes.
- **Contract later:** drop or rename only in a later release, once no deployed release (including the rollback target) uses the old shape.
- A change that can't be split this way needs an explicit plan in its roadmap item, covering downtime, a feature flag, or giving up rollback for that release.

---

## Updating secrets

Secrets live only in SSM; nothing secret is in Terraform state or the Lambda configuration. Each instance reads them once at cold start, so rotating is: write the new value, then recycle instances. No apply, no deploy.

```bash
aws ssm put-parameter --region us-west-2 --name /pktx/prod/database_url \
  --value "postgresql://..." --type SecureString --overwrite
```

```bash
aws lambda update-function-configuration --region us-west-2 --function-name pktx-prod \
  --description "secrets rotated $(date -u +%FT%TZ)"
```

Changing the configuration retires warm instances; the next request cold-starts and reads the new value. The next apply resets the description, which is harmless.

A public config change (tfvars) ships like any infra change: merge, and release for prod.

### One-time cutover from Terraform-held secrets (038)

Before 038, Terraform read every SSM value and wrote it into state and the Lambda env. After the 038 release has reached prod:

1. Apply `infra/shared` by hand: CI roles lose all SSM read and decrypt. Apply only now, not earlier: the cutover deploy itself still runs under the old roles.
2. Delete the now-unused non-secret parameters (`pktx_public_url`, `clerk_publishable_key`, `clerk_issuer`, `clerk_jwks_url`, `clerk_oauth_client_id`) in both envs.
3. Rotate all four secrets (Neon password, Clerk secret key, webhook signing secret, OAuth client secret), then recycle (above).
4. Delete state-bucket object versions written before the cutover: they still hold the old values (`aws s3api list-object-versions --bucket pktx-terraform-state-<env>`, then `delete-object --version-id` for each old version).

**Rollback across 038 is not supported**: a pre-038 tag's Terraform would try to re-create the SSM parameters it no longer manages, and a pre-038 image expects secrets in env vars. Fix forward instead.

---

## Break-glass: `make deploy`

Use this when GitHub Actions is down. It needs owner AWS credentials and a clean working tree. It runs the same `scripts/deploy/*` steps as CI:

```bash
make deploy ENV=dev    # ensure-base (ECR) → build-push sha-<HEAD> → apply (prompts) → smoke → mark verified
```

```bash
make deploy ENV=prod   # ensure-base → promote verified-<HEAD> → apply (prompts) → smoke
```

`ENV=prod` skips the reviewer gate (owner credentials), but it still refuses an image that dev has not verified.

### Infra-only change

Merge it; CI applies dev with the current image. For prod, publish a release. You can plan locally first:

```bash
terraform -chdir=infra/dev plan -var "image_digest=$(scripts/deploy/current-digest.sh dev)"
```

---

## Security Scanning and Updates (one-time GitHub settings)

- `ci.yml` runs `make check` on PRs.
- `security.yml` scans the built image and the repo with Trivy on every PR and every Monday.
- `renovate.json` drives dependency updates, including the SHA-pinned actions in the deploy workflows.

Turn these repo settings on:

1. **Install Renovate.** Add https://github.com/apps/renovate to this repo only. It
   opens an onboarding PR that picks up `renovate.json`, then a "Dependency Dashboard"
   issue.
2. **Settings → General → Pull Requests → Allow auto-merge**: on, so Renovate can merge
   patch updates.
3. **Settings → Rules → Rulesets →** the ruleset that targets `main` → **Require status
   checks to pass** → add `check`, `plan`, `image` and `iac-secrets`. Without them,
   auto-merge would merge untested updates. A check only shows in the picker after it
   has run once.
4. **Settings → Advanced Security** (older UI: *Code security*):
   - Dependabot **alerts**: on. Dependabot **security updates**: off, because Renovate
     opens the PRs.
   - **Secret Protection** → on, then **Push protection** → on.
   - **CodeQL analysis** → Set up → **Default** (Python, JavaScript/TypeScript, Actions).

Findings land in **Security → Code scanning**. The weekly run only rebuilds and scans. To ship a patched base image, merge the Renovate PR; dev deploys on merge, then release to prod.

**Deferred: ECR enhanced scanning (Amazon Inspector).** This rescans the image already
deployed in ECR as new CVEs are published, which CI can't do. It costs a little per
image. Add it when prod is live with `aws_ecr_registry_scanning_configuration`
(`scan_type = "ENHANCED"`, `CONTINUOUS_SCAN` on `pktx-*`).

---

## Backups

Backups are **Neon's**, not this repo's. There is nothing to provision and nothing in Terraform.

- Neon console → project → **Settings → Storage → History retention** — the point-in-time-restore window (free plan caps it at 24 hours)
- Restoring is a Neon-console operation: branch → *Restore*, pick a timestamp

Users can take their own data out at any time via **Export my data** in the account menu (`GET /api/export`), which returns their full dataset as JSON.

---

## Destroying an Environment

> **Warning**: This is irreversible. All AWS resources (Lambda, ECR images, IAM roles, CloudWatch data) are deleted. SSM secrets are not Terraform-managed; delete them by hand with `aws ssm delete-parameters`.

Run it with owner credentials. Deploy roles cannot delete ECR repos.

```bash
terraform -chdir=infra/{env} destroy -var "image_digest=$(scripts/deploy/current-digest.sh {env})"
```

The S3 state bucket is not destroyed by `terraform destroy` (it is not Terraform-managed). Delete it manually if needed:

```bash
aws s3 rb s3://pktx-terraform-state-{env} --force
```

---

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---------|-------------|------------|
| `configure-aws-credentials`: "Not authorized to perform sts:AssumeRoleWithWebIdentity" | Token `sub` doesn't match the role's trusted subject: wrong Environment name, or the repo's OIDC subject prefix changed | Check the Environment is `dev` / `production` exactly; compare `gh api repos/elnaterator/pktx/actions/oidc/customization/sub` with `github_sub_prefix`, then `terraform -chdir=infra/shared apply` |
| Deploy step `AccessDenied` on a new resource type | A Terraform change added a resource the deploy role can't manage | Extend the env's statement in `infra/shared/main.tf` (resource-scoped), apply it by hand |
| `deploy-prod`: "no pktx-dev:verified-<sha>" | That commit never passed a dev deploy | Merge to main / re-run **Deploy dev** for it, or release a commit that did |
| Response has `x-amzn-Remapped-www-authenticate` instead of `WWW-Authenticate` | Lambda Function URLs reserve that header and rename it (Cloudflare passes it through) | Expected; MCP clients fall back to `/.well-known/oauth-protected-resource/mcp`, which the smoke test checks too. To restore the standard header, add a Cloudflare response header transform rule that copies it back |
| Smoke: `GET / lacks the injected Clerk publishable key` | `clerk_publishable_key` tfvar wrong / empty | Fix it in `terraform.tfvars`, merge |
| Lambda returns 502 | App failed to start; Web Adapter never received a readiness response | Check logs: `aws logs tail /aws/lambda/pktx-{env} --follow` |
| Lambda returns 500 | App started but errored on a request | Check logs for Python traceback |
| Lambda logs `SecretsError: SSM secrets not ready: /pktx/<env>/<name> (missing)` | A secret does not exist, or is still `TO_BE_SET` | `scripts/deploy/check-secrets.sh <env>`, set it, recycle |
| Lambda logs `SecretsError: could not read secrets under …: AccessDeniedException` | Exec role can't read the parameter (name not in `secret_names`, or boundary changed) | Add it to `secret_names` in `infra/<env>/main.tf`, merge |
| `exec format error` in Lambda logs | Image built for the wrong architecture | CI builds on an arm64 runner; locally use `make deploy` (`--platform linux/arm64`) |
| Build fails pulling `public.ecr.aws/...` (429) | ECR Public anonymous rate limit | `build-push.sh` retries 3×; re-run the job |
| `terraform init` fails "bucket not found" | State bucket not bootstrapped | `./infra/bootstrap.sh <stack>` |
| PR plan fails for `prod` | Prod not bootstrapped yet | Set repo variable `TF_PLAN_STACKS=shared dev` until it is |
| MCP sign-in fails at `/authorize` with a redirect URI error | Hosted client callback not allowlisted | Add it to `extra_client_redirect_uris` in `terraform.tfvars`, merge |
