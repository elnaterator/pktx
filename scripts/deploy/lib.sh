#!/usr/bin/env bash
# Shared helpers for scripts/deploy/*. Sourced, not executed.
# Used by both GitHub Actions (deploy-*.yml) and `make deploy` (break-glass),
# so CI and a laptop run the same steps.

set -euo pipefail

AWS_REGION="${AWS_REGION:-us-west-2}"
export AWS_REGION AWS_DEFAULT_REGION="$AWS_REGION"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

log() { printf '==> %s\n' "$*" >&2; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

require_env_name() {
  [[ "${1:-}" == "dev" || "${1:-}" == "prod" ]] || die "env must be 'dev' or 'prod', got '${1:-}'"
}

require_sha() {
  [[ "${1:-}" =~ ^[0-9a-f]{40}$ ]] || die "expected a full 40-char git sha, got '${1:-}'"
}

# Release tag (vYYYY.MM.DD[.N]), dev-<short sha> or prod-<short sha> (break-glass).
require_version() {
  [[ "${1:-}" =~ ^(v[0-9]+(\.[0-9]+)*|(dev|prod)-[0-9a-f]{7,40})$ ]] \
    || die "expected a version like v2026.11.24 or dev-<sha>, got '${1:-}'"
}

require_digest() {
  [[ "${1:-}" =~ ^sha256:[0-9a-f]{64}$ ]] || die "expected sha256:<64 hex>, got '${1:-}'"
}

account_id() { aws sts get-caller-identity --query Account --output text; }
registry() { echo "$(account_id).dkr.ecr.${AWS_REGION}.amazonaws.com"; }
repo_name() { echo "pktx-$1"; }

# Digest of <repo>:<tag>, or empty if the tag does not exist.
image_digest() {
  aws ecr describe-images --repository-name "$1" --image-ids "imageTag=$2" \
    --query 'imageDetails[0].imageDigest' --output text 2>/dev/null || true
}

tf() { terraform -chdir="${REPO_ROOT}/infra/$1" "${@:2}"; }

tf_init() { tf "$1" init -input=false >/dev/null; }

# Interactive applies on a laptop; auto-approve only in CI.
approve_flag() { [[ "${CI:-}" == "true" ]] && echo "-auto-approve" || true; }
