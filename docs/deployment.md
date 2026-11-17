# Deploying to AWS

pktx runs on **AWS Lambda** (arm64) as a container image stored in **ECR**. All AWS resources are defined in Terraform under `infra/`:

| Stack | What | Applied by |
|---|---|---|
| `infra/shared` | GitHub OIDC provider, CI roles, Lambda permissions boundaries | The owner, by hand (CI only plans it) |
| `infra/dev`, `infra/prod` | ECR repo, Lambda + Function URL, IAM exec role, KMS key, SSM parameters, logs, alarm, keep-warm | CI (`deploy-dev.yml`, `deploy-prod.yml`); `make deploy` as break-glass |

Each stack has its own state bucket and lock table.

## How a change ships

```
PR ──► ci.yml: make check                          plan.yml: terraform plan (shared, dev, prod) → sticky PR comment
merge to main ──► deploy-dev.yml: make check ──► build image ONCE → pktx-dev:sha-<sha>
                  └─► terraform apply dev @digest ──► smoke test ──► tag pktx-dev:verified-<sha>
publish release v* ──► deploy-prod.yml ──► [production Environment: you approve]
                  └─► copy the verified digest → pktx-prod:sha-<sha> ──► terraform apply prod @digest ──► smoke test
```

- **Build once, promote the artifact.** The image has no per-environment config: the server injects the Clerk publishable key into `index.html` at serve time (`CLERK_PUBLISHABLE_KEY`). Prod runs the byte-identical image dev ran and smoke-tested. `deploy-prod` refuses a commit with no `verified-<sha>` image and checks the prod digest equals the dev digest.
- **Lambda is pinned by digest through Terraform** (`image_uri = repo@sha256:…`). ECR tags are immutable. Terraform state and what's running never drift.
- **No AWS keys in GitHub.** Workflows log in through GitHub OIDC. Each role trusts exactly one subject:

  | Role | Trusted subject | Can |
  |---|---|---|
  | `pktx-gha-plan` | `repo:elnaterator/pktx:pull_request` | Read only (no state lock, no writes) |
  | `pktx-gha-deploy-dev` | `repo:elnaterator/pktx:environment:dev` | Manage `pktx-dev*` resources and `/pktx/dev/*` only |
  | `pktx-gha-deploy-prod` | `repo:elnaterator/pktx:environment:production` | Manage `pktx-prod*` resources and `/pktx/prod/*` only, plus read `pktx-dev` images to promote |

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
| [Terraform](https://developer.hashicorp.com/terraform/install) 1.7+ | `brew install terraform` | everything |
| [AWS CLI](https://aws.amazon.com/cli/) 2.x | `brew install awscli` | bootstrap, secrets |
| Docker with `buildx` | Docker Desktop | break-glass `make deploy ENV=dev` |
| [crane](https://github.com/google/go-containerregistry) | `brew install crane` | break-glass `make deploy ENV=prod` |
| actionlint, shellcheck | `brew install actionlint shellcheck` | `make check` |

Owner AWS credentials (`aws configure` / `AWS_PROFILE`) are needed only for the one-time bootstrap, setting secrets and break-glass deploys.

### Values to collect

Each environment needs these values in SSM Parameter Store. Collect them first:

| SSM parameter (`/pktx/{env}/…`) | Where it comes from |
|---|---|
| `database_url` | Neon console → connection string (`?sslmode=require`) |
| `clerk_secret_key` | Clerk → API Keys (`sk_test_…` dev, `sk_live_…` prod) |
| `clerk_publishable_key` | Clerk → API Keys (`pk_test_…` / `pk_live_…`); injected into `index.html` at serve time |
| `clerk_issuer` | Clerk → API Keys → Frontend API URL (`https://<your-app>.clerk.accounts.dev`) |
| `clerk_jwks_url` | `<clerk_issuer>/.well-known/jwks.json` |
| `clerk_webhook_secret` | Clerk → Webhooks → endpoint `<pktx_public_url>/api/webhooks/clerk` → signing secret (`whsec_…`) |
| `pktx_public_url` | The app's public origin: the Lambda function URL (known after the first deploy) or your custom domain |
| `clerk_oauth_client_id` | Clerk → OAuth applications → app with redirect URI `<pktx_public_url>/auth/callback` |
| `clerk_oauth_client_secret` | Same OAuth application |

Non-secret configuration (`extra_client_redirect_uris`, `authorized_parties`, sizing) lives in `infra/{env}/terraform.tfvars`. The image digest is never in tfvars; the deploy scripts pass it.

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

Each creates a versioned, encrypted, private S3 bucket `pktx-terraform-state-<stack>` and a DynamoDB lock table `pktx-terraform-locks-<stack>`. These are not Terraform-managed (that would be circular).

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

The first deploy of an env needs real secret values before the app can start.

1. Create the ECR repo and the SSM placeholders. With owner creds, run the first command below. Or merge to `main`: the first CI step does the same thing, and later steps fail until secrets are set.
2. Overwrite every placeholder with the real values (next command).
3. Check that nothing is still a placeholder (the `get-parameters-by-path` command below should print `[]`).
4. Deploy. For dev: merge to `main`, re-run the failed **Deploy dev** run, or run `make deploy ENV=dev`. For prod: publish a release (see below).

```bash
scripts/deploy/ensure-base.sh dev
```

```bash
aws ssm put-parameter --region us-west-2 --name /pktx/dev/database_url \
  --value "postgresql://..." --type SecureString --overwrite
```

```bash
aws ssm get-parameters-by-path --region us-west-2 --path /pktx/dev/ --with-decryption \
  --query "Parameters[?Value=='TO_BE_SET'].Name"
```

`pktx_public_url` (and the Clerk webhook and OAuth redirect URIs that depend on it) can only be set once the function URL exists. Deploy once, set it, then deploy again.

Terraform creates each SSM parameter with `TO_BE_SET` and ignores later value changes (`lifecycle.ignore_changes = [value]`), so it never reverts what you set.

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

Rollback is safe only if the older code can read the current schema; see the next section.

---

## Database migrations: expand → contract

Dev runs ahead of prod, and a rollback runs old code against a schema that has already migrated. Every migration in `backend/src/pktx/migrations.py` must therefore be **forward-compatible**: the previous release must keep working against the new schema.

- **Expand first:** add nullable columns or tables, and backfill. Never rename or drop a column that released code still reads or writes.
- **Contract later:** drop or rename only in a later release, once no deployed release (including the rollback target) uses the old shape.
- A change that can't be split this way needs an explicit plan in its roadmap item, covering downtime, a feature flag, or giving up rollback for that release.

---

## Updating secrets

SSM parameter *values* live outside Terraform. Lambda does **not** read SSM at runtime: Terraform reads each parameter during `apply` and writes it into the function's environment variables (encrypted with the env's KMS key). Rotating a secret is two steps:

1. Write the new value to SSM (first command below).
2. Re-apply that env. For dev, re-run the latest **Deploy dev** run (Actions → Re-run all jobs). For prod, run **Deploy prod** with the release that is currently live (second command below).

```bash
aws ssm put-parameter --region us-west-2 --name /pktx/prod/database_url \
  --value "postgresql://..." --type SecureString --overwrite
```

```bash
gh workflow run deploy-prod.yml -f tag=<current release>
```

The apply updates the function configuration, which also recycles warm instances. Secrets are therefore also present in Terraform state. Each state bucket is private and encrypted, and only that env's deploy role and the read-only plan role can read it.

---

## Break-glass: `make deploy`

Use this when GitHub Actions is down. It needs owner AWS credentials and a clean working tree. It runs the same `scripts/deploy/*` steps as CI:

```bash
make deploy ENV=dev    # ensure-base → build-push sha-<HEAD> → apply (prompts) → smoke → mark verified
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

> **Warning**: This is irreversible. All AWS resources (Lambda, ECR images, IAM roles, SSM parameters, CloudWatch data) are deleted.

Run it with owner credentials. Deploy roles cannot delete ECR repos.

```bash
terraform -chdir=infra/{env} destroy -var "image_digest=$(scripts/deploy/current-digest.sh {env})"
```

The S3 state bucket and DynamoDB lock table are not destroyed by `terraform destroy` (they are not Terraform-managed). Delete them manually if needed:

```bash
aws s3 rb s3://pktx-terraform-state-{env} --force
```

```bash
aws dynamodb delete-table --region us-west-2 --table-name pktx-terraform-locks-{env}
```

---

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---------|-------------|------------|
| `configure-aws-credentials`: "Not authorized to perform sts:AssumeRoleWithWebIdentity" | Environment name or repo doesn't match the role's trusted subject, or `infra/shared` not applied | Check the Environment is `dev` / `production` exactly; `terraform -chdir=infra/shared apply` |
| Deploy step `AccessDenied` on a new resource type | A Terraform change added a resource the deploy role can't manage | Extend the env's statement in `infra/shared/main.tf` (resource-scoped), apply it by hand |
| `deploy-prod`: "no pktx-dev:verified-<sha>" | That commit never passed a dev deploy | Merge to main / re-run **Deploy dev** for it, or release a commit that did |
| Smoke: `GET / lacks the injected Clerk publishable key` | `clerk_publishable_key` SSM value still `TO_BE_SET` / empty | Set it, re-run the deploy |
| Lambda returns 502 | App failed to start; Web Adapter never received a readiness response | Check logs: `aws logs tail /aws/lambda/pktx-{env} --follow` |
| Lambda returns 500 | App started but errored on a request | Check logs for Python traceback |
| App errors on a missing/odd config value | An SSM parameter is still `TO_BE_SET`, or was changed without a re-apply | Run the placeholder check, then re-run the deploy |
| `exec format error` in Lambda logs | Image built for the wrong architecture | CI builds on an arm64 runner; locally use `make deploy` (`--platform linux/arm64`) |
| Build fails pulling `public.ecr.aws/...` (429) | ECR Public anonymous rate limit | `build-push.sh` retries 3×; re-run the job |
| `terraform init` fails "bucket not found" | State bucket not bootstrapped | `./infra/bootstrap.sh <stack>` |
| PR plan fails for `prod` | Prod not bootstrapped yet | Set repo variable `TF_PLAN_STACKS=shared dev` until it is |
| MCP sign-in fails at `/authorize` with a redirect URI error | Hosted client callback not allowlisted | Add it to `extra_client_redirect_uris` in `terraform.tfvars`, merge |
