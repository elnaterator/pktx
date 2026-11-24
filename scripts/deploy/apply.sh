#!/usr/bin/env bash
# Full terraform apply of an env with Lambda pinned to an image digest that is
# already in that env's ECR repo, reporting <version> (PKTX_VERSION: release tag
# in prod, dev-<short sha> in dev). Prints the Function URL on stdout.
# Usage: apply.sh <dev|prod> <sha256:digest> <version>
# shellcheck source=lib.sh source-path=SCRIPTDIR
source "$(dirname "$0")/lib.sh"

env="${1:-}"; require_env_name "$env"
digest="${2:-}"; require_digest "$digest"
version="${3:-}"; require_version "$version"

aws ecr describe-images --repository-name "$(repo_name "$env")" \
  --image-ids "imageDigest=${digest}" >/dev/null \
  || die "${digest} is not in $(repo_name "$env")"

tf_init "$env"
log "terraform apply infra/${env} @ ${digest} (${version})"
# shellcheck disable=SC2046 # approve_flag is empty or one word
tf "$env" apply -input=false $(approve_flag) \
  -var "image_digest=${digest}" -var "app_version=${version}" >&2
tf "$env" output -raw lambda_function_url
