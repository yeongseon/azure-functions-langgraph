# Local curl scripts

Tiny shell helpers for verifying a `func start` host without leaving the terminal. Each script reads `BASE`, `FUNCTION_KEY`, and other knobs from the environment so the same script works locally (no key) and against a deployed Function App with `?code=`.

| Script | Hits | Notes |
| --- | --- | --- |
| `health.sh` | `GET /api/health` | Smoke-test the host is up |
| `invoke.sh` | `POST /api/graphs/{GRAPH}/invoke` | Defaults to `simple_agent` |
| `stream.sh` | `POST /api/graphs/{GRAPH}/stream` | **Buffered SSE** — chunks arrive after run completes |
| `platform_run.sh` | `/assistants/search`, `/threads`, `/threads/{id}/runs/wait`, `/threads/{id}/state` | Drives the `platform_compat=True` surface |

## Usage

```bash
# Against a local func start (no key needed)
./health.sh

# Override defaults
GRAPH=echo_agent ./invoke.sh
PAYLOAD='{"input":{"messages":[{"role":"human","content":"hi"}]}}' ./invoke.sh

# Against a deployed Function App
BASE=https://my-app.azurewebsites.net/api FUNCTION_KEY=xxxxx ./invoke.sh
```

`platform_run.sh` requires the host to expose the platform-compatible endpoints (`LangGraphApp(platform_compat=True)`). Pair it with the [`platform_compat_sdk`](../platform_compat_sdk/) example.

## Streaming caveat

`/stream` endpoints (both native and platform-compatible) return **buffered SSE**: chunks emitted by the graph are flushed *after* the run completes, not token-by-token. This is documented in detail in [docs/production-guide.md](../../docs/production-guide.md#streaming-behavior).
