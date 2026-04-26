#!/usr/bin/env bash
# POST /api/graphs/{name}/invoke for the named graph (default: simple_agent)
set -euo pipefail
BASE="${BASE:-http://localhost:7071/api}"
GRAPH="${GRAPH:-simple_agent}"
CODE_PARAM="${FUNCTION_KEY:+?code=$FUNCTION_KEY}"
PAYLOAD="${PAYLOAD:-{\"input\":{\"messages\":[{\"role\":\"human\",\"content\":\"World\"}]}}}"
curl -fsS -X POST "$BASE/graphs/$GRAPH/invoke$CODE_PARAM" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"
