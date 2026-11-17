#!/usr/bin/env bash
# Create the pieces an image push needs before the first full apply of an env:
# the ECR repo and the SSM parameters. No-op once they exist.
# Usage: ensure-base.sh <dev|prod>
# shellcheck source=lib.sh source-path=SCRIPTDIR
source "$(dirname "$0")/lib.sh"

env="${1:-}"; require_env_name "$env"

tf_init "$env"
log "ensure ECR repository and SSM parameters exist (infra/${env})"
targets=(-target=module.lambda.aws_ecr_repository.app)
for p in database_url clerk_publishable_key clerk_jwks_url clerk_issuer clerk_webhook_secret \
  clerk_secret_key pktx_public_url clerk_oauth_client_id clerk_oauth_client_secret; do
  targets+=("-target=aws_ssm_parameter.${p}")
done
# Targeted apply never touches the Lambda, so any well-formed digest will do.
tf "$env" apply -input=false -auto-approve "${targets[@]}" \
  -var "image_digest=sha256:$(printf '0%.0s' {1..64})"
