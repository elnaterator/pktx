#!/usr/bin/env bash
# Digest the env's Lambda runs now, so `terraform plan` shows infra drift only.
# Prints an all-zero digest (with a warning) if the function does not exist yet.
# Usage: current-digest.sh <dev|prod>
# shellcheck source=lib.sh source-path=SCRIPTDIR
source "$(dirname "$0")/lib.sh"

env="${1:-}"; require_env_name "$env"
uri="$(aws lambda get-function --function-name "pktx-${env}" \
  --query 'Code.ImageUri' --output text 2>/dev/null || true)"
if [[ "$uri" == *@sha256:* ]]; then
  echo "${uri##*@}"
else
  log "warning: pktx-${env} not deployed (or not pinned by digest); planning with a placeholder"
  echo "sha256:$(printf '0%.0s' {1..64})"
fi
