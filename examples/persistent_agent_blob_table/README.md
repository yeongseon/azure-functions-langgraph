# Persistent agent (Azure Blob + Azure Table)

End-to-end example using `AzureBlobCheckpointSaver` for checkpoint state and `AzureTableThreadStore` for thread metadata. Runs locally against [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite) (Azure Storage emulator) and unchanged against real Azure Storage in production.

## Files

- `function_app.py` — wires both backends, registers `persistent_agent` with `platform_compat=True`
- `graph.py` — turn-counting echo agent (state survives across requests)
- `host.json`, `local.settings.json.example`, `requirements.txt`

## Run locally with Azurite

Start Azurite (Docker):

```bash
docker run -d --name azurite \
  -p 10000:10000 -p 10001:10001 -p 10002:10002 \
  mcr.microsoft.com/azure-storage/azurite
```

Or via npm: `npm install -g azurite && azurite`.

Then:

```bash
cd examples/persistent_agent_blob_table
cp local.settings.json.example local.settings.json
pip install -r requirements.txt
func start
```

`local.settings.json.example` ships with `UseDevelopmentStorage=true`, which Azurite recognizes. The Functions host auto-loads it; the example also creates the Blob container on startup if it does not exist. The Table is created lazily by the store on first write.

## Verify persistence

Send the same `thread_id` twice and observe the turn counter increment:

```bash
THREAD=$(curl -s -X POST http://localhost:7071/api/threads -H "Content-Type: application/json" -d '{}' | python -c 'import json,sys; print(json.load(sys.stdin)["thread_id"])')

curl -s -X POST "http://localhost:7071/api/threads/$THREAD/runs/wait" \
  -H "Content-Type: application/json" \
  -d '{"assistant_id":"persistent_agent","input":{"messages":[{"role":"human","content":"first"}]}}'

curl -s -X POST "http://localhost:7071/api/threads/$THREAD/runs/wait" \
  -H "Content-Type: application/json" \
  -d '{"assistant_id":"persistent_agent","input":{"messages":[{"role":"human","content":"second"}]}}'
```

The second response shows `[turn 2]` — restart `func start` and the counter still increments because state lives in Azurite, not memory.

## Production switch

Replace `UseDevelopmentStorage=true` with a real connection string in your Azure Functions App Settings (or use a Key Vault reference / Managed Identity per `docs/production-guide.md`). No code changes needed.

## Scale envelope

This example uses the bundled SDK-only backends. They are sized for development and small-to-medium production loads — see [scale envelope in the README](../../README.md#scale-envelope) and [docs/production-guide.md](../../docs/production-guide.md) for limits and the Timer-triggered retention recipe.
