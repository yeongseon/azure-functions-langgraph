from __future__ import annotations

import logging
import os

import azure.functions as func

from azure_functions_langgraph.stores.azure_table import AzureTableThreadStore

_CONN = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
_THREADS_TABLE = os.environ.get("LANGGRAPH_THREADS_TABLE", "langgraphthreads")
_STALE_LOCK_SECONDS = int(os.environ.get("LANGGRAPH_STALE_LOCK_SECONDS", "900"))

thread_store = AzureTableThreadStore.from_connection_string(
    connection_string=_CONN,
    table_name=_THREADS_TABLE,
)

app = func.FunctionApp()


@app.timer_trigger(schedule="0 */5 * * * *", arg_name="timer", run_on_startup=False)
def reset_stale_run_locks(timer: func.TimerRequest) -> None:
    del timer
    reset = thread_store.reset_stale_locks(older_than_seconds=_STALE_LOCK_SECONDS)
    if reset:
        logging.warning(
            "reset %d stale run lock(s) older than %ds (status=error)",
            reset,
            _STALE_LOCK_SECONDS,
        )
