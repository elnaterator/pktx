# Deploying to AWS

pktx runs on **AWS Lambda** (arm64) as a container image stored in **ECR**. All AWS resources are defined in Terraform under `infra/`. There are two environments: `dev` and `prod`, each with isolated state.

**CI never touches AWS.** It has no AWS credentials; deploys are always performed manually by the developer with `make deploy`.

---

## Prerequisites

### Tools

| Tool | Version | Install |
|------|---------|---------|
| [Terraform](https://developer.hashicorp.com/terraform/install) | 1.7+ | `brew install terraform` |
| [AWS CLI](https://aws.amazon.com/cli/) | 2.x | `brew install awscli` |
| [Docker](https://docs.docker.com/get-docker/) with `buildx` | Any | Docker Desktop |
| [jq](https://jqlang.org/) | Any | `brew install jq` (used by `make deploy`) |

### AWS credentials

Configure the AWS CLI before running any commands:

```bash
aws configure
# or set AWS_PROFILE if using named profiles
```

### Values to collect

Each environment needs these values in SSM Parameter Store (Phase 2). Collect them first:

| SSM parameter (`/pktx/{env}/…`) | Where it comes from |
|---|---|
| `database_url` | Neon console → connection string (`?sslmode=require`) |
| `clerk_secret_key` | Clerk → API Keys (`sk_test_…` dev, `sk_live_…` prod) |
| `clerk_publishable_key` | Clerk → API Keys (`pk_test_…` / `pk_live_…`); baked into the frontend at build time |
| `clerk_issuer` | Clerk → API Keys → Frontend API URL (`https://<your-app>.clerk.accounts.dev`) |
| `clerk_jwks_url` | `<clerk_issuer>/.well-known/jwks.json` |
| `clerk_webhook_secret` | Clerk → Webhooks → endpoint `<pktx_public_url>/api/webhooks/clerk` → signing secret (`whsec_…`) |
| `pktx_public_url` | The app's public origin: the Lambda function URL (known after Phase 4) or your custom domain |
| `clerk_oauth_client_id` | Clerk → OAuth applications → app with redirect URI `<pktx_public_url>/auth/callback` |
| `clerk_oauth_client_secret` | Same OAuth application |

Non-secret configuration (`extra_client_redirect_uris`, `authorized_parties`, `image_tag`, sizing) lives in `infra/{env}/terraform.tfvars`.

---

## One-Time Bootstrap

Run these steps once per environment before the first `terraform init`. These resources are not managed by Terraform (bootstrapping them with Terraform would be circular).

### Create remote state infrastructure

Replace `dev` with `prod` and repeat for the prod environment.

```bash
# S3 bucket for Terraform state
aws s3api create-bucket \
  --region us-west-2 \
  --bucket pktx-terraform-state-dev \
  --create-bucket-configuration LocationConstraint=us-west-2

aws s3api put-bucket-versioning \
  --bucket pktx-terraform-state-dev \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket pktx-terraform-state-dev \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# DynamoDB table for state locking
aws dynamodb create-table \
  --region us-west-2 \
  --table-name pktx-terraform-locks-dev \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

---

## First-Time Provisioning

The first deploy of an environment needs several phases: Lambda can't be created until an image exists in ECR, and the image build needs the Clerk publishable key from SSM. After that, `make deploy` does everything; Phase 2 (real secret values) is always manual.

### Phase 1 — Create ECR and the SSM placeholders

Don't run `make deploy` yet: its image build would bake in the `TO_BE_SET` publishable key.

```bash
terraform -chdir=infra/dev init
terraform -chdir=infra/dev apply \
  -target=module.lambda.aws_ecr_repository.app \
  $(for p in database_url clerk_secret_key clerk_publishable_key clerk_issuer clerk_jwks_url \
      clerk_webhook_secret pktx_public_url clerk_oauth_client_id clerk_oauth_client_secret; \
    do printf -- '-target=aws_ssm_parameter.%s ' $p; done)
```

This creates the ECR repository and every SSM parameter with the placeholder value `TO_BE_SET`. Terraform ignores later value changes (`lifecycle.ignore_changes = [value]`), so it never reverts what you set next.

### Phase 2 — Set secrets in SSM Parameter Store

Overwrite each placeholder with the values collected above:

```bash
# Repeat for every parameter in the table above
aws ssm put-parameter \
  --region us-west-2 \
  --name /pktx/{env}/database_url \
  --value "postgresql://user:pass@ep-xxx.us-west-2.aws.neon.tech/neondb?sslmode=require" \
  --type SecureString \
  --overwrite
```

`pktx_public_url` (and the Clerk webhook and OAuth redirect URIs that depend on it) can only be filled in once the function URL exists. Leave it for the first pass, finish Phase 4, then set it and run `make deploy` again.

Check that nothing is still a placeholder:

```bash
aws ssm get-parameters-by-path \
  --region us-west-2 \
  --path /pktx/{env}/ \
  --with-decryption \
  --query "Parameters[?Value=='TO_BE_SET'].Name"
# Expected: []
```

### Phase 3 + 4 — Build, push, full apply

```bash
make deploy ENV=dev
```

Review the full apply plan carefully. Expected new resources include:

- `module.lambda.aws_iam_role.lambda_exec` and its policies (`ecr_pull`, `ssm_read`, `lambda_env_kms`, `cw_logs` attachment)
- `module.lambda.aws_kms_key.lambda_env` (encrypts the Lambda environment variables)
- `module.lambda.aws_lambda_function.app`, `aws_lambda_function_url.app`, and the URL permissions
- `module.lambda.aws_cloudwatch_event_rule.keep_warm` + target + permission (when `keep_warm_enabled`)
- `module.observability.aws_cloudwatch_log_group.lambda` and `aws_cloudwatch_metric_alarm.errors`

Test it:

```bash
curl "$(terraform -chdir=infra/dev output -raw lambda_function_url)health"   # URL ends in /
# Expected: {"status":"ok"}
```

---

## Subsequent Deploys

```bash
make deploy ENV=dev
# or
make deploy ENV=prod
```

This runs five steps:

1. `terraform init` (idempotent)
2. Targeted apply: ensures ECR and the SSM parameters exist (no-op after the first deploy)
3. `docker buildx build --platform linux/arm64` with `VITE_CLERK_PUBLISHABLE_KEY` read from SSM, then push `:latest` to ECR
4. Full `terraform apply` (prompts for confirmation); this also refreshes the Lambda env vars from SSM
5. `aws lambda update-function-code` pinned to the pushed image's digest, so Lambda runs the new image even when Terraform saw no change

The function URL is printed at the end.

> **Note**: `make deploy` always pushes `:latest`. To pin a prod tag, push it manually and set `image_tag` in `infra/prod/terraform.tfvars` before applying.

---

## Updating Secrets

SSM parameter *values* are managed outside Terraform. Lambda does **not** read SSM at runtime: Terraform reads each parameter during `apply` and writes it into the function's environment variables. Rotating a secret is therefore two steps:

```bash
aws ssm put-parameter \
  --region us-west-2 \
  --name /pktx/prod/database_url \
  --value "postgresql://..." \
  --type SecureString \
  --overwrite

terraform -chdir=infra/prod apply   # or: make deploy ENV=prod
```

The apply updates the function configuration, which also recycles warm instances.

---

## Updating Infrastructure Only (No New Image)

If you changed Terraform files but not application code:

```bash
cd infra/{env}
terraform plan   # review changes
terraform apply
```

---

## Pushing a New Image Without Terraform Changes

`make deploy` is the supported path. If you need to do it by hand, mirror its steps 3 and 5:

```bash
ECR_URL=$(terraform -chdir=infra/{env} output -raw ecr_repository_url)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
CLERK_PK=$(aws ssm get-parameter --region us-west-2 --name /pktx/{env}/clerk_publishable_key \
  --with-decryption --query Parameter.Value --output text)

aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin \
  ${ACCOUNT_ID}.dkr.ecr.us-west-2.amazonaws.com

docker buildx build --platform linux/arm64 --provenance=false \
  --build-arg VITE_CLERK_PUBLISHABLE_KEY=${CLERK_PK} \
  --load -t ${ECR_URL}:latest .
docker push ${ECR_URL}:latest

DIGEST=$(aws ecr describe-images --region us-west-2 --repository-name pktx-{env} \
  --image-ids imageTag=latest --query 'imageDetails[0].imageDigest' --output text)
aws lambda update-function-code \
  --region us-west-2 \
  --function-name pktx-{env} \
  --image-uri ${ECR_URL}@${DIGEST}
```

---

## Security Scanning and Updates (one-time GitHub settings)

CI is two workflows, neither with AWS access: `ci.yml` runs `make check` on PRs, and `security.yml` scans the built image and the repo with Trivy on every PR and every Monday. `renovate.json` drives dependency updates. Turn these repo settings on (all free on a public repo):

1. **Install Renovate.** Add https://github.com/apps/renovate to this repo only. It
   opens an onboarding PR that picks up `renovate.json`, then a "Dependency Dashboard"
   issue.
2. **Settings → General → Pull Requests → Allow auto-merge**: on, so Renovate can merge
   patch updates.
3. **Settings → Rules → Rulesets →** the ruleset that targets `main` → **Require status
   checks to pass** → add `check`, `image` and `iac-secrets`. Without them, auto-merge
   would merge untested updates. A check only shows in the picker after it has run once,
   for example on the PR that added `security.yml`.
4. **Settings → Advanced Security** (older UI: *Code security*):
   - Dependabot **alerts**: on. Dependabot **security updates**: off, because Renovate
     opens the PRs.
   - **Secret Protection** → on, then **Push protection** → on.
   - **CodeQL analysis** → Set up → **Default** (Python, JavaScript/TypeScript, Actions).

Findings land in **Security → Code scanning**. The weekly run only rebuilds and scans;
ship a patched image with `make deploy` as usual.

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

```bash
cd infra/{env}
terraform destroy
```

The S3 state bucket and DynamoDB locks table are not destroyed by `terraform destroy` (they are not Terraform-managed). Delete them manually if needed:

```bash
aws s3 rb s3://pktx-terraform-state-{env} --force
aws dynamodb delete-table --region us-west-2 --table-name pktx-terraform-locks-{env}
```

---

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---------|-------------|------------|
| Lambda returns 502 | App failed to start; Web Adapter never received a readiness response | Check logs: `aws logs tail /aws/lambda/pktx-{env} --follow` |
| Lambda returns 500 | App started but errored on a request | Check logs for Python traceback |
| App errors on a missing/odd config value | An SSM parameter is still `TO_BE_SET`, or was changed without a re-apply | Run the placeholder check in Phase 2, then `terraform apply` |
| `exec format error` in Lambda logs | Image built for the wrong architecture | Build with `--platform linux/arm64` (use `make deploy`) |
| Sign-in fails in the deployed SPA | Image built without `VITE_CLERK_PUBLISHABLE_KEY` | Rebuild via `make deploy` (reads it from SSM) |
| `docker push` fails with "denied" | ECR auth token expired (valid 12h) | Re-run `aws ecr get-login-password \| docker login ...` |
| `terraform plan` fails "image not found" | ECR image not yet pushed | Run `make deploy` (it pushes before the full apply) |
| `terraform init` fails "bucket not found" | S3 state bucket not bootstrapped | Complete One-Time Bootstrap above |
| MCP sign-in fails at `/authorize` with a redirect URI error | Hosted client callback not allowlisted | Add it to `extra_client_redirect_uris` in `terraform.tfvars`, then apply |
