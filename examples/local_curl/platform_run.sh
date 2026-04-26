#!/usr/bin/env bash
# Drive the platform-compatible surface end-to-end: create thread, run, get state
set -euo pipefail
BASE="${BASE:-http://localhost:7071/api}"
ASSISTANT="${ASSISTANT:-echo_agent}"
CODE_PARAM="${FUNCTION_KEY:+?code=$FUNCTION_KEY}"

echo "== assistants/search =="
curl -fsS -X POST "$BASE/assistants/search$CODE_PARAM" \
  -H "Content-Type: application/json" -d '{}'
echo

echo "== POST /threads =="
THREAD=$(curl -fsS -X POST "$BASE/threads$CODE_PARAM" \
  -H "Content-Type: application/json" -d '{}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["thread_id"])')
echo "thread_id=$THREAD"

echo "== POST /threads/{id}/runs/wait =="
curl -fsS -X POST "$BASE/threads/$THREAD/runs/wait$CODE_PARAM" \
  -H "Content-Type: application/json" \
  -d "{\"assistant_id\":\"$ASSISTANT\",\"input\":{\"messages\":[{\"role\":\"human\",\"content\":\"hello\"}]}}"
echo

echo "== GET /threads/{id}/state =="
curl -fsS "$BASE/threads/$THREAD/state$CODE_PARAM"
echo
