#!/usr/bin/env bash
# Publish a GitHub Release for <git sha> (default: origin/main), which triggers
# deploy-prod.yml. Tags are CalVer: vYYYY.MM.DD (UTC date), then
# vYYYY.MM.DD.1, .2, ... for further releases the same day.
# Refuses a commit whose Deploy dev run did not succeed (deploy-prod would
# refuse it anyway, since dev never marked its image verified).
# Usage: release.sh [git sha or ref]    DRY_RUN=1 prints the tag and stops.
# shellcheck source=lib.sh source-path=SCRIPTDIR
source "$(dirname "$0")/lib.sh"

command -v gh >/dev/null || die "gh not found (brew install gh)"

git fetch --quiet --tags origin main
sha="$(git rev-parse --verify "${1:-origin/main}^{commit}")"
require_sha "$sha"

ok="$(gh run list --workflow deploy-dev.yml --commit "$sha" --status success \
  --json databaseId --jq length)"
[[ "$ok" -gt 0 ]] \
  || die "no successful Deploy dev run for ${sha}; merge it to main or re-run Deploy dev first"

base="v$(date -u +%Y.%m.%d)"
tag="$base"
n=0
while git rev-parse --quiet --verify "refs/tags/${tag}" >/dev/null; do
  n=$((n + 1))
  tag="${base}.${n}"
done

log "release ${tag} -> ${sha} ($(git log -1 --format=%s "$sha"))"
if [[ "${DRY_RUN:-}" == "1" ]]; then
  log "DRY_RUN=1: not creating the release"
  exit 0
fi

read -r -p "Publish ${tag}? This starts the prod deploy. [y/N] " answer
[[ "$answer" == "y" || "$answer" == "Y" ]] || die "aborted"

gh release create "$tag" --target "$sha" --generate-notes
log "published ${tag}; approve the production deployment in Actions"
