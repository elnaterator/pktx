#!/usr/bin/env bash
# Full terraform apply of an env with Lambda pinned to an image digest that is
# already in that env's ECR repo. Prints the Function URL on stdout.
# Usage: apply.sh <dev|prod> <sha256:digest>
# shellcheck source=lib.sh source-path=SCRIPTDIR
source "$(dirname "$0")/lib.sh"

env="${1:-}"; require_env_name "$env"
digest="${2:-}"; require_digest "$digest"

aws ecr describe-images --repository-name "$(repo_name "$env")" \
  --image-ids "imageDigest=${digest}" >/dev/null \
  || die "${digest} is not in $(repo_name "$env")"

tf_init "$env"
log "terraform apply infra/${env} @ ${digest}"
# shellcheck disable=SC2046 # approve_flag is empty or one word
tf "$env" apply -input=false $(approve_flag) -var "image_digest=${digest}" >&2
tf "$env" output -raw lambda_function_url
