#!/usr/bin/env bash
# Build the app image once (linux/arm64) and push it to pktx-dev as sha-<git sha>.
# The image carries no per-env config, so the same digest is later promoted to prod.
# Idempotent: tags are immutable, so an existing sha-<sha> is reused, not rebuilt.
# Prints the image digest on stdout.
# Usage: build-push.sh <git sha>
# shellcheck source=lib.sh source-path=SCRIPTDIR
source "$(dirname "$0")/lib.sh"

sha="${1:-}"; require_sha "$sha"
repo="$(repo_name dev)"
tag="sha-${sha}"

existing="$(image_digest "$repo" "$tag")"
if [[ "$existing" == sha256:* ]]; then
  log "${repo}:${tag} already exists (${existing}); not rebuilding"
  echo "$existing"
  exit 0
fi

reg="$(registry)"
aws ecr get-login-password | docker login --username AWS --password-stdin "$reg" >/dev/null

log "build + push ${repo}:${tag}"
# ECR Public rate-limits anonymous base-image pulls per IP (shared by hosted
# runners), so retry with backoff.
for attempt in 1 2 3; do
  if docker buildx build --platform linux/arm64 --provenance=false --sbom=false \
    --label "org.opencontainers.image.revision=${sha}" --build-arg "GIT_SHA=${sha}" \
    --tag "${reg}/${repo}:${tag}" --push "$REPO_ROOT" >&2; then
    break
  fi
  (( attempt < 3 )) || die "docker build failed ${attempt} times"
  log "build failed (attempt ${attempt}); retrying in $((attempt * 30))s"
  sleep $((attempt * 30))
done

digest="$(image_digest "$repo" "$tag")"
require_digest "$digest"
echo "$digest"
