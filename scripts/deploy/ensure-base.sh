#!/usr/bin/env bash
# Create the ECR repo an image push needs before the first full apply of an env.
# No-op once it exists. App secrets are not created here: they live only in SSM,
# set by the owner (see check-secrets.sh and docs/deployment.md).
# Usage: ensure-base.sh <dev|prod>
# shellcheck source=lib.sh source-path=SCRIPTDIR
source "$(dirname "$0")/lib.sh"

env="${1:-}"; require_env_name "$env"

tf_init "$env"
log "ensure ECR repository exists (infra/${env})"
# Targeted apply never touches the Lambda, so any well-formed digest will do.
tf "$env" apply -input=false -auto-approve -target=module.lambda.aws_ecr_repository.app \
  -var "image_digest=sha256:$(printf '0%.0s' {1..64})"
