# Production auth example

Demonstrates the per-graph `auth_level` override pattern: a public, anonymous health endpoint and demo agent alongside a private function-key-protected agent — all on the same `LangGraphApp`.

## Auth model

The app uses `auth_level=AuthLevel.ANONYMOUS` (so `GET /api/health` is reachable without a key), and **overrides per registration**:

| Endpoint | Auth | Why |
| --- | --- | --- |
| `GET /api/health` | ANONYMOUS | Liveness probe / public discovery |
| `POST /api/graphs/public_agent/{invoke,stream}` | ANONYMOUS | Demo / public surface |
| `POST /api/graphs/private_agent/{invoke,stream}` | FUNCTION | Requires `?code=<FUNCTION_KEY>` |

> **Production tip:** flip the defaults if your service is mostly private. Set `LangGraphApp(auth_level=FUNCTION)` and register only the explicitly public graphs with `auth_level=ANONYMOUS`. Note that the `/api/health` endpoint inherits the app-level auth — protect or expose it accordingly.

## Files

- `function_app.py` — registers both graphs with explicit per-graph `auth_level`
- `graph.py` — two minimal echo graphs
- `host.json`, `local.settings.json.example`, `requirements.txt`
- `verify.sh` — curl script hitting both protected and unprotected endpoints

## Run locally

```bash
cd examples/production_auth
cp local.settings.json.example local.settings.json
pip install -r requirements.txt
func start
```

`func start` prints a per-function key for `private_agent`; copy that for the curl below. Locally, function-level auth still requires a key — the host generates one and prints it on startup.

## Verify

```bash
# Anonymous: works without a key
curl -s http://localhost:7071/api/health

curl -s -X POST http://localhost:7071/api/graphs/public_agent/invoke \
  -H "Content-Type: application/json" \
  -d '{"input":{"messages":[{"role":"human","content":"hi"}]}}'

# Function-level: 401 without a key
curl -s -o /dev/null -w '%{http_code}\n' \
  -X POST http://localhost:7071/api/graphs/private_agent/invoke \
  -H "Content-Type: application/json" \
  -d '{"input":{"messages":[{"role":"human","content":"hi"}]}}'

# Function-level: 200 with the key
curl -s -X POST "http://localhost:7071/api/graphs/private_agent/invoke?code=$FUNCTION_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input":{"messages":[{"role":"human","content":"hi"}]}}'
```

Or run the bundled script:

```bash
FUNCTION_KEY="<key from func start output>" ./verify.sh
```

## Production deployment notes

- Never commit `local.settings.json` — it is gitignored by Functions Core Tools, but double-check.
- In Azure, function keys live in the Function App's *Functions → App keys / Function keys* blade. Rotate them on a schedule (see [docs/production-guide.md](../../docs/production-guide.md#connection-string-security) for the broader credential hygiene policy).
- For richer auth (Azure AD, custom JWT, IP allowlist), front the Function App with API Management or App Service Authentication ("Easy Auth"); function keys are a coarse-grained primitive.
