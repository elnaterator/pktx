#!/usr/bin/env bash
# Tag a dev image verified-<sha> after it passed the dev smoke test. Prod only
# promotes verified images. Adds a tag to the same manifest (digest unchanged).
# Usage: mark-verified.sh <git sha>
# shellcheck source=lib.sh source-path=SCRIPTDIR
source "$(dirname "$0")/lib.sh"

sha="${1:-}"; require_sha "$sha"
repo="$(repo_name dev)"

if [[ "$(image_digest "$repo" "verified-${sha}")" == sha256:* ]]; then
  log "${repo}:verified-${sha} already exists"
  exit 0
fi

manifest="$(aws ecr batch-get-image --repository-name "$repo" --image-ids "imageTag=sha-${sha}" \
  --query 'images[0].imageManifest' --output text)"
media_type="$(aws ecr batch-get-image --repository-name "$repo" --image-ids "imageTag=sha-${sha}" \
  --query 'images[0].imageManifestMediaType' --output text)"
[[ -n "$manifest" && "$manifest" != "None" ]] || die "${repo}:sha-${sha} not found"

aws ecr put-image --repository-name "$repo" --image-tag "verified-${sha}" \
  --image-manifest "$manifest" --image-manifest-media-type "$media_type" >/dev/null
log "tagged ${repo}:verified-${sha}"
