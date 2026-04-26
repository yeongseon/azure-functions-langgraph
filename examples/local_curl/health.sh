#!/usr/bin/env bash
# Hit GET /api/health
set -euo pipefail
BASE="${BASE:-http://localhost:7071/api}"
CODE_PARAM="${FUNCTION_KEY:+?code=$FUNCTION_KEY}"
curl -fsS "$BASE/health$CODE_PARAM"
