# Maintenance Timer (stale run-lock recovery)

A Timer-triggered Azure Functions app that periodically calls
`AzureTableThreadStore.reset_stale_locks()` to recover threads stuck in `busy`
status after a Function host termination during graph execution.

## Why this is needed

`AzureTableThreadStore.try_acquire_run_lock()` is atomic (ETag CAS), but
`release_run_lock()` is intentionally best-effort — failing to release a lock
is operationally worse than racing one. As a result, a Function instance killed
mid-execution can leave a thread permanently `busy` and unrunnable. Run this
maintenance Function alongside your main app to reclaim those threads.

## Files

- `function_app.py` — Timer Trigger that calls `reset_stale_locks` every 5 minutes
- `host.json`, `local.settings.json.example`, `requirements.txt`

## Configuration

| Setting | Default | Description |
| --- | --- | --- |
| `AZURE_STORAGE_CONNECTION_STRING` | (required) | Connection string for the storage account hosting the threads table. |
| `LANGGRAPH_THREADS_TABLE` | `langgraphthreads` | Table name (must match the main app). |
| `LANGGRAPH_STALE_LOCK_SECONDS` | `900` | Reset locks held longer than this. Pick a value comfortably larger than your worst-case graph execution time. |

The CRON expression `0 */5 * * * *` (every 5 minutes) is set in
`function_app.py`; tune it together with `LANGGRAPH_STALE_LOCK_SECONDS` to match
your reliability target.

## Run locally

```bash
cd examples/maintenance_timer
cp local.settings.json.example local.settings.json
pip install -r requirements.txt
func start
```

You can deploy this side-by-side with the main app (same storage account, same
table name). The helper only resets threads whose lock has been held longer than
`LANGGRAPH_STALE_LOCK_SECONDS` and uses ETag CAS to skip threads that another
worker has just re-acquired. Set the threshold comfortably above your worst-case
graph execution time so a legitimately long-running run is not reset out from
under itself.

## Recovery status

By default stale locks are reset to `error` so an operator can audit them.
Pass `status="idle"` if you want the affected threads to be immediately
re-runnable instead.
