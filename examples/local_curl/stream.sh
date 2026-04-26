#!/usr/bin/env bash
# POST /api/graphs/{name}/stream — buffered SSE; chunks arrive after run completes
set -euo pipefail
BASE="${BASE:-http://localhost:7071/api}"
GRAPH="${GRAPH:-simple_agent}"
CODE_PARAM="${FUNCTION_KEY:+?code=$FUNCTION_KEY}"
PAYLOAD="${PAYLOAD:-{\"input\":{\"messages\":[{\"role\":\"human\",\"content\":\"World\"}]}}}"
curl -fsSN -X POST "$BASE/graphs/$GRAPH/stream$CODE_PARAM" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d "$PAYLOAD"
