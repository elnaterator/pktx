#!/usr/bin/env bash
# Post-deploy smoke test. Fails (non-zero) on the first broken check.
#   1. GET  /health  -> 200 (retried: cold start / new image pull)
#   2. POST /mcp     -> 401 + Bearer resource_metadata challenge (OAuth-protected)
#   3. GET  /.well-known/oauth-protected-resource/mcp -> 200 RFC 9728 metadata
#   4. GET  /        -> 200 + server-injected Clerk publishable key
# Lambda Function URLs reserve WWW-Authenticate and rename it to
# x-amzn-Remapped-www-authenticate, so check 2 accepts either name. MCP clients
# that miss the header fall back to the well-known metadata, which check 3 covers.
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
grep -qiE '^(x-amzn-remapped-)?www-authenticate: *Bearer .*resource_metadata=' <<<"$headers" \
  || fail "POST /mcp 401 lacks a Bearer resource_metadata challenge"
echo "ok  POST /mcp 401 (OAuth challenge)"

meta="$(curl -sf --max-time 15 "${base}/.well-known/oauth-protected-resource/mcp")" \
  || fail "GET /.well-known/oauth-protected-resource/mcp failed"
grep -q '"authorization_servers"' <<<"$meta" \
  || fail "protected-resource metadata lacks authorization_servers"
echo "ok  GET /.well-known/oauth-protected-resource/mcp 200"

body="$(curl -sf --max-time 15 "${base}/")" || fail "GET / failed"
grep -q 'name="pktx-clerk-publishable-key" content="pk_' <<<"$body" \
  || fail "GET / lacks the injected Clerk publishable key"
echo "ok  GET / serves SPA with runtime config"
