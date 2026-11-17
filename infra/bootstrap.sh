#!/usr/bin/env bash
# Bootstrap Terraform remote state infrastructure for a given environment.
# Creates the S3 bucket and DynamoDB table used by backend.tf.
#
# Usage: ./infra/bootstrap.sh <dev|prod|shared>

set -euo pipefail

ENV="${1:-}"
REGION="us-west-2"

if [[ "$ENV" != "dev" && "$ENV" != "prod" && "$ENV" != "shared" ]]; then
  echo "Usage: $0 <dev|prod|shared>" >&2
  exit 1
fi

BUCKET="pktx-terraform-state-${ENV}"
TABLE="pktx-terraform-locks-${ENV}"

echo "==> Bootstrapping Terraform remote state for environment: ${ENV}"
echo "    Bucket: ${BUCKET}"
echo "    Table:  ${TABLE}"
echo "    Region: ${REGION}"
echo

# --- S3 bucket ---
if aws s3api head-bucket --bucket "$BUCKET" --region "$REGION" 2>/dev/null; then
  echo "[skip] S3 bucket already exists: ${BUCKET}"
else
  echo "[create] S3 bucket: ${BUCKET}"
  aws s3api create-bucket \
    --bucket "$BUCKET" \
    --region "$REGION" \
    --create-bucket-configuration LocationConstraint="$REGION"

  aws s3api put-bucket-versioning \
    --bucket "$BUCKET" \
    --versioning-configuration Status=Enabled

  aws s3api put-bucket-encryption \
    --bucket "$BUCKET" \
    --server-side-encryption-configuration \
      '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

  aws s3api put-public-access-block \
    --bucket "$BUCKET" \
    --public-access-block-configuration \
      "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

  echo "[ok] S3 bucket created: ${BUCKET}"
fi

echo

# --- DynamoDB table ---
if aws dynamodb describe-table --table-name "$TABLE" --region "$REGION" &>/dev/null; then
  echo "[skip] DynamoDB table already exists: ${TABLE}"
else
  echo "[create] DynamoDB table: ${TABLE}"
  aws dynamodb create-table \
    --table-name "$TABLE" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "$REGION"

  aws dynamodb wait table-exists --table-name "$TABLE" --region "$REGION"
  echo "[ok] DynamoDB table created: ${TABLE}"
fi

echo
echo "Bootstrap complete. Run 'terraform init' in infra/${ENV}/ to initialize the backend."
