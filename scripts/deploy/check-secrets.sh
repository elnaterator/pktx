#!/usr/bin/env bash
# Owner check: every secret the app reads at cold start exists in SSM as a set
# SecureString. Prints parameter names only, never values. Needs owner creds:
# CI roles cannot read SSM by design (038), so this is not a CI step.
# Usage: check-secrets.sh <dev|prod>
# shellcheck source=lib.sh source-path=SCRIPTDIR
source "$(dirname "$0")/lib.sh"

env="${1:-}"; require_env_name "$env"

# Single source of truth: secret_names in infra/<env>/main.tf.
names=()
while IFS= read -r n; do names+=("$n"); done < <(
  sed -n '/secret_names = \[/,/\]/p' "${REPO_ROOT}/infra/${env}/main.tf" | grep -oE '"[a-z_]+"' | tr -d '"')
(( ${#names[@]} > 0 )) || die "no secret_names found in infra/${env}/main.tf"

bad=0
for n in "${names[@]}"; do
  p="/pktx/${env}/${n}"
  type="$(aws ssm describe-parameters --parameter-filters "Key=Name,Values=${p}" \
    --query 'Parameters[0].Type' --output text 2>/dev/null || true)"
  if [[ "$type" != "SecureString" ]]; then
    log "MISSING  ${p} (expected SecureString, got ${type:-none})"; bad=1; continue
  fi
  # Compare in-process; the value is never printed.
  if [[ "$(aws ssm get-parameter --name "$p" --with-decryption \
      --query Parameter.Value --output text)" == "TO_BE_SET" ]]; then
    log "UNSET    ${p}"; bad=1; continue
  fi
  log "ok       ${p}"
done
(( bad == 0 )) || die "set the parameters above: aws ssm put-parameter --type SecureString --overwrite --name <name> --value <value>"
