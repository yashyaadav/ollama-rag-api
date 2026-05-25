#!/usr/bin/env bash
# Ask a question via curl.
# Usage:  ./examples/curl.sh "your question here"
set -euo pipefail
API_URL="${API_URL:-http://localhost:5000}"
QUERY="${1:-What is this document about?}"

curl -sS -X POST "$API_URL/ask" \
  -H 'Content-Type: application/json' \
  -d "$(printf '{"query": %s}' "$(printf %s "$QUERY" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')")" \
  | (command -v jq >/dev/null && jq . || cat)
