#!/usr/bin/env bash
# Copy the dev-verified image for <git sha> into pktx-prod, byte for byte.
# Refuses unless pktx-dev:verified-<sha> exists, and asserts the prod digest
# equals the dev digest. Prints the digest on stdout.
# Usage: promote.sh <git sha>      (needs crane: https://github.com/google/go-containerregistry)
# shellcheck source=lib.sh source-path=SCRIPTDIR
source "$(dirname "$0")/lib.sh"

sha="${1:-}"; require_sha "$sha"
command -v crane >/dev/null || die "crane not found (brew install crane)"
src_repo="$(repo_name dev)"
dst_repo="$(repo_name prod)"

digest="$(image_digest "$src_repo" "verified-${sha}")"
[[ "$digest" == sha256:* ]] \
  || die "no ${src_repo}:verified-${sha}: ${sha} was never deployed + smoke-tested in dev"

existing="$(image_digest "$dst_repo" "sha-${sha}")"
if [[ "$existing" != sha256:* ]]; then
  reg="$(registry)"
  aws ecr get-login-password | crane auth login "$reg" -u AWS --password-stdin >/dev/null
  log "copy ${src_repo}@${digest} -> ${dst_repo}:sha-${sha}"
  crane copy "${reg}/${src_repo}@${digest}" "${reg}/${dst_repo}:sha-${sha}" >&2
  existing="$(image_digest "$dst_repo" "sha-${sha}")"
fi

[[ "$existing" == "$digest" ]] \
  || die "digest mismatch: ${dst_repo}:sha-${sha}=${existing}, dev verified=${digest}"
echo "$digest"
