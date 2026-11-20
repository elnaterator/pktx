#!/usr/bin/env bash
# Post-deploy smoke test. Fails (non-zero) on the first broken check.
#   1. GET  /health  -> 200 (retried: cold start / new image pull)
#   2. POST /mcp     -> 401 + WWW-Authenticate (OAuth-protected, app wired)
#   3. GET  /        -> 200 + server-injected Clerk publishable key
# Usage: smoke.sh <base url>
set -euo pipefail

base="${1:-}"
[[ "$base" =~ ^https?:// ]] || { echo "usage: $0 <base url>" >&2; exit 2; }
base="${base%/}"
fail() { echo "smoke FAIL: $*" >&2; exit 1; }

for attempt in $(seq 1 12); do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "${base}/health" || true)"
  [[ "$code" == "200" ]] && break
  echo "  /health -> ${code:-none} (attempt ${attempt}/12)" >&2
  sleep 5
done
[[ "$code" == "200" ]] || fail "/health returned ${code:-none}"
echo "ok  GET /health 200"

headers="$(curl -s -D - -o /dev/null --max-time 15 -X POST "${base}/mcp" \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}')"
status="$(head -n1 <<<"$headers" | awk '{print $2}')"
[[ "$status" == "401" ]] || fail "POST /mcp returned ${status:-none}, want 401"
grep -qi '^www-authenticate:.*resource_metadata' <<<"$headers" \
  || fail "POST /mcp 401 lacks WWW-Authenticate resource_metadata"
echo "ok  POST /mcp 401 (OAuth challenge)"

body="$(curl -sf --max-time 15 "${base}/")" || fail "GET / failed"
grep -q 'name="pktx-clerk-publishable-key" content="pk_' <<<"$body" \
  || fail "GET / lacks the injected Clerk publishable key"
echo "ok  GET / serves SPA with runtime config"
