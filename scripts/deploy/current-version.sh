#!/usr/bin/env bash
# PKTX_VERSION the env's Lambda runs now, so `terraform plan` shows infra drift only.
# Prints `local` (with a warning) if the function or the variable does not exist yet.
# Usage: current-version.sh <dev|prod>
# shellcheck source=lib.sh source-path=SCRIPTDIR
source "$(dirname "$0")/lib.sh"

env="${1:-}"; require_env_name "$env"
version="$(aws lambda get-function-configuration --function-name "pktx-${env}" \
  --query 'Environment.Variables.PKTX_VERSION' --output text 2>/dev/null || true)"
if [[ -n "$version" && "$version" != "None" ]]; then
  echo "$version"
else
  log "warning: pktx-${env} reports no PKTX_VERSION; planning with 'local'"
  echo "local"
fi
