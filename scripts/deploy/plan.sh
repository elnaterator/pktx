#!/usr/bin/env bash
# Read-only `terraform plan` of one or more stacks, rendered as Markdown for a PR
# comment. dev/prod plan against the digest + version Lambda runs now, so the plan shows
# infra drift only. Never takes the state lock. The AWS account id is masked.
# Exits non-zero if any stack failed to plan (the report still covers all).
# Usage: plan.sh <stack>...        (stack: shared | dev | prod)
# shellcheck source=lib.sh source-path=SCRIPTDIR
source "$(dirname "$0")/lib.sh"

(( $# > 0 )) || die "usage: $0 <shared|dev|prod>..."
account="$(account_id)"
failed=0

echo "### Terraform plan"
echo
echo "Commit \`${GITHUB_SHA:-$(git -C "$REPO_ROOT" rev-parse HEAD)}\`"
for stack in "$@"; do
  [[ "$stack" == "shared" ]] || require_env_name "$stack"
  vars=()
  [[ "$stack" == "shared" ]] || vars=(
    -var "image_digest=$("$(dirname "$0")/current-digest.sh" "$stack")"
    -var "app_version=$("$(dirname "$0")/current-version.sh" "$stack")"
  )

  out="$(mktemp)"
  if tf_init "$stack" 2>"$out" \
    && tf "$stack" plan -lock=false -input=false -no-color -detailed-exitcode "${vars[@]}" >"$out" 2>&1; then
    summary="no changes"
  else
    code=$?
    if (( code == 2 )); then
      summary="$(grep -E '^Plan: ' "$out" || echo 'changes')"
    else
      summary="**plan failed**"
      failed=1
    fi
  fi

  echo
  echo "<details><summary><code>infra/${stack}</code>: ${summary}</summary>"
  echo
  echo '```'
  # Keep the diff, drop the refresh chatter; cap size for the comment limit.
  sed -En '/^(Terraform used|Terraform will perform|No changes|Error|│)/,$p' "$out" \
    | sed "s/${account}/<account>/g" | head -c 20000
  echo '```'
  echo "</details>"
  rm -f "$out"
done

exit "$failed"
