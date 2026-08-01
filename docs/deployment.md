# Deploying to AWS

pktx runs on **AWS Lambda** as a container image stored in **ECR**. All AWS resources are defined in Terraform under `infra/`. There are two environments: `dev` and `prod`, each with isolated state.

**CI never runs `terraform apply`.** Deploys are always performed manually by the developer.

---

## Prerequisites

### Tools

| Tool | Version | Install |
|------|---------|---------|
| [Terraform](https://developer.hashicorp.com/terraform/install) | 1.7+ | `brew install terraform` |
| [AWS CLI](https://aws.amazon.com/cli/) | 2.x | `brew install awscli` |
| [Docker](https://docs.docker.com/get-docker/) | Any | Docker Desktop |

### AWS credentials

Configure the AWS CLI before running any commands:

```bash
aws configure
# or set AWS_PROFILE if using named profiles
```

### Clerk keys

You need Clerk API keys for each environment before you can set SSM secrets. Get them from the [Clerk dashboard](https://dashboard.clerk.com):

- **Secret key** — starts with `sk_test_` (dev) or `sk_live_` (prod)
- **Publishable key** — starts with `pk_test_` (dev) or `pk_live_` (prod)

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

The first deploy of an environment requires two phases because Lambda cannot be created until a container image exists in ECR. `make deploy` handles this automatically, but the steps are documented here for clarity.

### Phase 1 — Initialize Terraform and create ECR

```bash
cd infra/dev   # or infra/prod
terraform init
terraform apply -target=module.lambda.aws_ecr_repository.app -auto-approve
```

This creates only the ECR repository. All other resources follow in Phase 4.

### Phase 2 — Set secrets in SSM Parameter Store

Terraform creates placeholder SSM parameters (`value = "TO_BE_SET"`) during apply. Set the real values before Phase 4 or the Lambda function will start but fail to read its configuration.

```bash
# Replace {env} with dev or prod
# Replace values with real credentials from Neon and Clerk dashboards

aws ssm put-parameter \
  --region us-west-2 \
  --name /pktx/{env}/database_url \
  --value "postgresql://user:pass@ep-xxx.us-west-2.aws.neon.tech/neondb?sslmode=require" \
  --type SecureString \
  --overwrite

aws ssm put-parameter \
  --region us-west-2 \
  --name /pktx/{env}/clerk_secret_key \
  --value "sk_test_..." \
  --type SecureString \
  --overwrite

aws ssm put-parameter \
  --region us-west-2 \
  --name /pktx/{env}/clerk_publishable_key \
  --value "pk_test_..." \
  --type SecureString \
  --overwrite
```

Verify all three are set:

```bash
aws ssm get-parameters-by-path \
  --region us-west-2 \
  --path /pktx/{env}/ \
  --query "Parameters[*].{Name:Name,Type:Type}"
```

### Phase 3 — Build and push the Docker image

```bash
# From repo root
ECR_URL=$(terraform -chdir=infra/{env} output -raw ecr_repository_url)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Authenticate Docker to ECR
aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin \
  ${ACCOUNT_ID}.dkr.ecr.us-west-2.amazonaws.com

# Build, tag, push
docker build -t pktx-{env}:latest .
docker tag pktx-{env}:latest ${ECR_URL}:latest
docker push ${ECR_URL}:latest
```

### Phase 4 — Full apply

```bash
cd infra/{env}
terraform apply
```

Review the plan output carefully. Expected new resources:

- `aws_iam_role.lambda_exec`
- `aws_iam_role_policy.ecr_pull` and `ssm_read`
- `aws_iam_role_policy_attachment.cw_logs`
- `aws_ssm_parameter.database_url`, `clerk_secret_key`, `clerk_publishable_key`
- `module.observability.aws_cloudwatch_log_group.lambda`
- `module.observability.aws_cloudwatch_metric_alarm.errors`
- `module.lambda.aws_lambda_function.app`
- `module.lambda.aws_lambda_function_url.app`

After apply completes, get the public URL:

```bash
terraform output lambda_function_url
```

Test it:

```bash
curl $(terraform output -raw lambda_function_url)/health
# Expected: {"status": "ok", ...}
```

---

## Subsequent Deploys

For all deploys after the first, use:

```bash
make deploy ENV=dev
# or
make deploy ENV=prod
```

This runs four steps automatically:

1. `terraform init` — re-initializes the backend (idempotent)
2. Targeted apply — ensures ECR exists (no-op after first deploy)
3. Docker build + ECR push — builds the image from the repo root and pushes `latest`
4. `terraform apply` — applies any infrastructure changes; prompts for confirmation

The function URL is printed at the end of a successful deploy.

> **Note**: `make deploy` always tags the image as `latest`. For prod deployments where you want a pinned tag, push manually and set `image_tag` in `infra/prod/terraform.tfvars` before applying.

---

## Updating Secrets

SSM parameter *values* are managed outside Terraform. Use `put-parameter --overwrite` to rotate a secret:

```bash
aws ssm put-parameter \
  --region us-west-2 \
  --name /pktx/prod/database_url \
  --value "postgresql://..." \
  --type SecureString \
  --overwrite
```

Lambda reads SSM parameters at cold-start only. Force a cold start after rotating a secret by updating the function:

```bash
aws lambda update-function-configuration \
  --region us-west-2 \
  --function-name pktx-prod \
  --description "force cold start $(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

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

If you only changed application code and the infrastructure is unchanged:

```bash
ECR_URL=$(terraform -chdir=infra/{env} output -raw ecr_repository_url)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin \
  ${ACCOUNT_ID}.dkr.ecr.us-west-2.amazonaws.com

docker build -t pktx-{env}:latest .
docker tag pktx-{env}:latest ${ECR_URL}:latest
docker push ${ECR_URL}:latest

# Force Lambda to pull the new image
aws lambda update-function-code \
  --region us-west-2 \
  --function-name pktx-{env} \
  --image-uri ${ECR_URL}:latest
```

---

## Setting Up CI (GitHub Actions)

The CI workflow (`.github/workflows/terraform-ci.yml`) runs `terraform plan` on pull requests via OIDC — no long-lived AWS credentials stored in GitHub.

### Create the OIDC provider (one-time)

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

### Create an IAM role per environment

Create a role named `github-actions-terraform-dev` (and `...-prod`) with:

- **Trust policy**: allows `token.actions.githubusercontent.com` to assume the role, scoped to your repo
- **Permissions**: read-only on Lambda, ECR, SSM (describe only, no `GetParameter`), S3 state bucket, DynamoDB locks table

### Set GitHub repository secrets

| Secret | Value |
|--------|-------|
| `TF_PLAN_ROLE_DEV` | ARN of `github-actions-terraform-dev` |
| `TF_PLAN_ROLE_PROD` | ARN of `github-actions-terraform-prod` |

Once set, `terraform plan` runs automatically on any PR that touches `infra/**`.

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
| Cold start > 15s | SSM reads timing out | Verify IAM role has `ssm:GetParameter` on `/pktx/{env}/*` |
| `docker push` fails with "denied" | ECR auth token expired (valid 12h) | Re-run `aws ecr get-login-password \| docker login ...` |
| `terraform plan` fails "image not found" | ECR image not yet pushed | Complete Phase 3 (build and push) before full apply |
| `terraform init` fails "bucket not found" | S3 state bucket not bootstrapped | Complete One-Time Bootstrap above |
| CI plan fails "no identity" | OIDC role not set up or secret not set | Complete CI setup section above |
| SSM value still `TO_BE_SET` after `put-parameter` | Wrong path or region | Verify with `aws ssm get-parameter --name /pktx/{env}/database_url --with-decryption` |
