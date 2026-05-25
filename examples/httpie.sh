#!/usr/bin/env bash
# Ask a question via HTTPie.
# Usage:  ./examples/httpie.sh "your question here"
set -euo pipefail
API_URL="${API_URL:-http://localhost:5000}"
QUERY="${1:-What is this document about?}"

http POST "$API_URL/ask" query="$QUERY"
