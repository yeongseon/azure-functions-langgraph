"""Tests for Platform API–compatible route layer (issue #38)."""

from __future__ import annotations

import json
from typing import Any, Iterator

import azure.functions as func
import pytest

from azure_functions_langgraph.app import LangGraphApp
from azure_functions_langgraph.platform.routes import (
    PlatformRouteDeps,
    _platform_error,
)
from azure_functions_langgraph.platform.stores import InMemoryThreadStore
from tests.conftest import (
    FakeCompiledGraph,
    FakeInvokeOnlyGraph,
    FakeStatefulGraph,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def store() -> InMemoryThreadStore:
    """Thread store with deterministic IDs."""
    counter = iter(range(1000))
    return InMemoryThreadStore(id_factory=lambda: f"thread-{next(counter)}")


@pytest.fixture()
def graph() -> FakeCompiledGraph:
    return FakeCompiledGraph()


@pytest.fixture()
def stateful_graph() -> FakeStatefulGraph:
    return FakeStatefulGraph()


def _build_platform_app(
    *,
    graphs: dict[str, Any] | None = None,
    store: InMemoryThreadStore | None = None,
) -> LangGraphApp:
    """Build a LangGraphApp with platform_compat=True and register graphs."""
    app = LangGraphApp(platform_compat=True)
    if store is not None:
        app._thread_store = store
    if graphs:
        for name, g in graphs.items():
            app.register(graph=g, name=name)
    return app


def _get_fn(fa: func.FunctionApp, fn_name: str) -> Any:
    """Get a registered function handler by name from a FunctionApp."""
    fa.functions_bindings = {}
    for fn in fa.get_functions():
        if fn.get_function_name() == fn_name:
            return fn.get_user_function()
    raise AssertionError(f"Function {fn_name!r} not found")


def _post_request(
    url: str,
    body: dict[str, Any] | None = None,
    **route_params: str,
) -> func.HttpRequest:
    """Build a POST request with JSON body."""
    return func.HttpRequest(
        method="POST",
        url=url,
        body=json.dumps(body or {}).encode(),
        headers={"Content-Type": "application/json"},
        route_params=route_params,
    )


def _get_request(url: str, **route_params: str) -> func.HttpRequest:
    """Build a GET request."""
    return func.HttpRequest(
        method="GET",
        url=url,
        body=b"",
        route_params=route_params,
    )


# ---------------------------------------------------------------------------
# LangGraphApp integration — platform_compat flag
# ---------------------------------------------------------------------------


class TestPlatformCompatFlag:
    def test_platform_routes_registered_when_enabled(self, graph: FakeCompiledGraph) -> None:
        app = _build_platform_app(graphs={"agent": graph})
        fa = app.function_app

        fa.functions_bindings = {}
        fn_names = [f.get_function_name() for f in fa.get_functions()]

        # All 7 platform route names must be present
        expected = {
            "aflg_platform_assistants_search",
            "aflg_platform_assistants_get",
            "aflg_platform_threads_create",
            "aflg_platform_threads_get",
            "aflg_platform_threads_state_get",
            "aflg_platform_runs_wait",
            "aflg_platform_runs_stream",
        }
        assert expected.issubset(set(fn_names))

    def test_platform_routes_not_registered_when_disabled(self, graph: FakeCompiledGraph) -> None:
        app = LangGraphApp(platform_compat=False)
        app.register(graph=graph, name="agent")
        fa = app.function_app

        fa.functions_bindings = {}
        fn_names = [f.get_function_name() for f in fa.get_functions()]

        assert "aflg_platform_assistants_search" not in fn_names

    def test_auto_creates_thread_store(self) -> None:
        app = LangGraphApp(platform_compat=True)
        assert app.thread_store is not None
        assert isinstance(app.thread_store, InMemoryThreadStore)

    def test_no_thread_store_when_disabled(self) -> None:
        app = LangGraphApp(platform_compat=False)
        assert app.thread_store is None

    def test_custom_thread_store(self, store: InMemoryThreadStore) -> None:
        app = LangGraphApp(platform_compat=True)
        app.thread_store = store
        assert app.thread_store is store


# ---------------------------------------------------------------------------
# Assistants endpoints
# ---------------------------------------------------------------------------


class TestAssistantsSearch:
    def test_search_returns_all(self, graph: FakeCompiledGraph, store: InMemoryThreadStore) -> None:
        app = _build_platform_app(graphs={"agent": graph}, store=store)
        fa = app.function_app
        fn = _get_fn(fa, "aflg_platform_assistants_search")

        req = _post_request("/api/assistants/search")
        resp = fn(req)
        assert resp.status_code == 200
        data = json.loads(resp.get_body())
        assert len(data) == 1
        assert data[0]["assistant_id"] == "agent"
        assert data[0]["graph_id"] == "agent"

    def test_search_multiple_graphs(self, store: InMemoryThreadStore) -> None:
        g1 = FakeCompiledGraph()
        g2 = FakeCompiledGraph()
        app = _build_platform_app(graphs={"alpha": g1, "beta": g2}, store=store)
        fa = app.function_app
        fn = _get_fn(fa, "aflg_platform_assistants_search")

        req = _post_request("/api/assistants/search")
        resp = fn(req)
        data = json.loads(resp.get_body())
        assert len(data) == 2
        names = {a["assistant_id"] for a in data}
        assert names == {"alpha", "beta"}

    def test_search_filter_by_graph_id(self, store: InMemoryThreadStore) -> None:
        g1 = FakeCompiledGraph()
        g2 = FakeCompiledGraph()
        app = _build_platform_app(graphs={"alpha": g1, "beta": g2}, store=store)
        fa = app.function_app
        fn = _get_fn(fa, "aflg_platform_assistants_search")

        req = _post_request("/api/assistants/search", {"graph_id": "alpha"})
        resp = fn(req)
        data = json.loads(resp.get_body())
        assert len(data) == 1
        assert data[0]["assistant_id"] == "alpha"

    def test_search_with_limit(self, store: InMemoryThreadStore) -> None:
        graphs = {f"g{i}": FakeCompiledGraph() for i in range(5)}
        app = _build_platform_app(graphs=graphs, store=store)
        fa = app.function_app
        fn = _get_fn(fa, "aflg_platform_assistants_search")

        req = _post_request("/api/assistants/search", {"limit": 2})
        resp = fn(req)
        data = json.loads(resp.get_body())
        assert len(data) == 2

    def test_search_with_offset(self, store: InMemoryThreadStore) -> None:
        graphs = {f"g{i}": FakeCompiledGraph() for i in range(5)}
        app = _build_platform_app(graphs=graphs, store=store)
        fa = app.function_app
        fn = _get_fn(fa, "aflg_platform_assistants_search")

        req = _post_request("/api/assistants/search", {"limit": 2, "offset": 3})
        resp = fn(req)
        data = json.loads(resp.get_body())
        assert len(data) == 2

    def test_search_empty_body(self, graph: FakeCompiledGraph, store: InMemoryThreadStore) -> None:
        """POST with no body should still work (defaults)."""
        app = _build_platform_app(graphs={"agent": graph}, store=store)
        fa = app.function_app
        fn = _get_fn(fa, "aflg_platform_assistants_search")

        req = func.HttpRequest(
            method="POST",
            url="/api/assistants/search",
            body=b"",
            headers={},
        )
        resp = fn(req)
        assert resp.status_code == 200


class TestAssistantsGet:
    def test_get_existing(self, graph: FakeCompiledGraph, store: InMemoryThreadStore) -> None:
        app = _build_platform_app(graphs={"agent": graph}, store=store)
        fa = app.function_app
        fn = _get_fn(fa, "aflg_platform_assistants_get")

        req = _get_request("/api/assistants/agent", assistant_id="agent")
        resp = fn(req)
        assert resp.status_code == 200
        data = json.loads(resp.get_body())
        assert data["assistant_id"] == "agent"
        assert data["name"] == "agent"

    def test_get_not_found(self, graph: FakeCompiledGraph, store: InMemoryThreadStore) -> None:
        app = _build_platform_app(graphs={"agent": graph}, store=store)
        fa = app.function_app
        fn = _get_fn(fa, "aflg_platform_assistants_get")

        req = _get_request("/api/assistants/missing", assistant_id="missing")
        resp = fn(req)
        assert resp.status_code == 404
        data = json.loads(resp.get_body())
        assert "not found" in data["detail"]


# ---------------------------------------------------------------------------
# Threads endpoints
# ---------------------------------------------------------------------------


class TestThreadsCreate:
    def test_create_thread(self, graph: FakeCompiledGraph, store: InMemoryThreadStore) -> None:
        app = _build_platform_app(graphs={"agent": graph}, store=store)
        fa = app.function_app
        fn = _get_fn(fa, "aflg_platform_threads_create")

        req = _post_request("/api/threads", {})
        resp = fn(req)
        assert resp.status_code == 200
        data = json.loads(resp.get_body())
        assert data["thread_id"] == "thread-0"
        assert data["status"] == "idle"

    def test_create_thread_with_metadata(
        self, graph: FakeCompiledGraph, store: InMemoryThreadStore,
    ) -> None:
        app = _build_platform_app(graphs={"agent": graph}, store=store)
        fa = app.function_app
        fn = _get_fn(fa, "aflg_platform_threads_create")

        req = _post_request("/api/threads", {"metadata": {"key": "value"}})
        resp = fn(req)
        assert resp.status_code == 200
        data = json.loads(resp.get_body())
        assert data["metadata"]["key"] == "value"

    def test_create_thread_empty_body(
        self, graph: FakeCompiledGraph, store: InMemoryThreadStore,
    ) -> None:
        app = _build_platform_app(graphs={"agent": graph}, store=store)
        fa = app.function_app
        fn = _get_fn(fa, "aflg_platform_threads_create")

        req = func.HttpRequest(
            method="POST",
            url="/api/threads",
            body=b"",
            headers={},
        )
        resp = fn(req)
        assert resp.status_code == 200


class TestThreadsGet:
    def test_get_existing_thread(
        self, graph: FakeCompiledGraph, store: InMemoryThreadStore,
    ) -> None:
        app = _build_platform_app(graphs={"agent": graph}, store=store)
        fa = app.function_app

        # Create thread first
        create_fn = _get_fn(fa, "aflg_platform_threads_create")
        resp = create_fn(_post_request("/api/threads", {}))
        thread_id = json.loads(resp.get_body())["thread_id"]

        # Get thread
        fa.functions_bindings = {}
        get_fn = _get_fn(fa, "aflg_platform_threads_get")
        req = _get_request(f"/api/threads/{thread_id}", thread_id=thread_id)
        resp = get_fn(req)
        assert resp.status_code == 200
        data = json.loads(resp.get_body())
        assert data["thread_id"] == thread_id

    def test_get_not_found(self, graph: FakeCompiledGraph, store: InMemoryThreadStore) -> None:
        app = _build_platform_app(graphs={"agent": graph}, store=store)
        fa = app.function_app
        fn = _get_fn(fa, "aflg_platform_threads_get")

        req = _get_request("/api/threads/missing", thread_id="missing")
        resp = fn(req)
        assert resp.status_code == 404
        data = json.loads(resp.get_body())
        assert "not found" in data["detail"]


# ---------------------------------------------------------------------------
# Thread state endpoint
# ---------------------------------------------------------------------------


class TestThreadsStateGet:
    def test_thread_not_found(self, graph: FakeCompiledGraph, store: InMemoryThreadStore) -> None:
        app = _build_platform_app(graphs={"agent": graph}, store=store)
        fa = app.function_app
        fn = _get_fn(fa, "aflg_platform_threads_state_get")

        req = _get_request("/api/threads/missing/state", thread_id="missing")
        resp = fn(req)
        assert resp.status_code == 404

    def test_thread_not_bound_to_assistant(
        self, graph: FakeCompiledGraph, store: InMemoryThreadStore
    ) -> None:
        app = _build_platform_app(graphs={"agent": graph}, store=store)
        fa = app.function_app

        # Create a thread (not bound)
        create_fn = _get_fn(fa, "aflg_platform_threads_create")
        resp = create_fn(_post_request("/api/threads", {}))
        thread_id = json.loads(resp.get_body())["thread_id"]

        # Get state — should 409 because not bound
        fa.functions_bindings = {}
        state_fn = _get_fn(fa, "aflg_platform_threads_state_get")
        req = _get_request(f"/api/threads/{thread_id}/state", thread_id=thread_id)
        resp = state_fn(req)
        assert resp.status_code == 409
        data = json.loads(resp.get_body())
        assert "not bound" in data["detail"]

    def test_state_with_stateful_graph(
        self, store: InMemoryThreadStore
    ) -> None:
        sg = FakeStatefulGraph()
        app = _build_platform_app(graphs={"agent": sg}, store=store)
        fa = app.function_app

        # Create thread and bind via a run
        create_fn = _get_fn(fa, "aflg_platform_threads_create")
        resp = create_fn(_post_request("/api/threads", {}))
        thread_id = json.loads(resp.get_body())["thread_id"]

        # Run to bind assistant
        fa.functions_bindings = {}
        wait_fn = _get_fn(fa, "aflg_platform_runs_wait")
        req = _post_request(
            f"/api/threads/{thread_id}/runs/wait",
            {"assistant_id": "agent", "input": {"messages": []}},
            thread_id=thread_id,
        )
        wait_fn(req)

        # Now get state
        fa.functions_bindings = {}
        state_fn = _get_fn(fa, "aflg_platform_threads_state_get")
        req = _get_request(f"/api/threads/{thread_id}/state", thread_id=thread_id)
        resp = state_fn(req)
        assert resp.status_code == 200
        data = json.loads(resp.get_body())
        assert "values" in data
        assert "next" in data

    def test_state_assistant_not_found(self, store: InMemoryThreadStore) -> None:
        """If thread's assistant_id references a graph that no longer exists."""
        sg = FakeStatefulGraph()
        app = _build_platform_app(graphs={"agent": sg}, store=store)

        # Create and bind thread manually
        thread = store.create()
        store.update(thread.thread_id, assistant_id="vanished")

        fa = app.function_app
        fn = _get_fn(fa, "aflg_platform_threads_state_get")
        req = _get_request(
            f"/api/threads/{thread.thread_id}/state",
            thread_id=thread.thread_id,
        )
        resp = fn(req)
        assert resp.status_code == 404
        data = json.loads(resp.get_body())
        assert "vanished" in data["detail"]

    def test_state_graph_not_stateful(self, store: InMemoryThreadStore) -> None:
        """Graph bound to thread doesn't support get_state."""
        g = FakeCompiledGraph()  # has invoke/stream but NOT get_state
        app = _build_platform_app(graphs={"agent": g}, store=store)

        thread = store.create()
        store.update(thread.thread_id, assistant_id="agent")

        fa = app.function_app
        fn = _get_fn(fa, "aflg_platform_threads_state_get")
        req = _get_request(
            f"/api/threads/{thread.thread_id}/state",
            thread_id=thread.thread_id,
        )
        resp = fn(req)
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Runs/wait endpoint
# ---------------------------------------------------------------------------


class TestRunsWait:
    def test_invoke_success(self, store: InMemoryThreadStore) -> None:
        g = FakeCompiledGraph()
        app = _build_platform_app(graphs={"agent": g}, store=store)
        fa = app.function_app

        # Create thread
        create_fn = _get_fn(fa, "aflg_platform_threads_create")
        resp = create_fn(_post_request("/api/threads", {}))
        thread_id = json.loads(resp.get_body())["thread_id"]

        # Run
        fa.functions_bindings = {}
        wait_fn = _get_fn(fa, "aflg_platform_runs_wait")
        req = _post_request(
            f"/api/threads/{thread_id}/runs/wait",
            {"assistant_id": "agent", "input": {"messages": [{"role": "human", "content": "hi"}]}},
            thread_id=thread_id,
        )
        resp = wait_fn(req)
        assert resp.status_code == 200
        data = json.loads(resp.get_body())
        # SDK returns final state values (dict)
        assert isinstance(data, dict)
        assert "messages" in data

    def test_thread_becomes_idle_after_run(self, store: InMemoryThreadStore) -> None:
        g = FakeCompiledGraph()
        app = _build_platform_app(graphs={"agent": g}, store=store)
        fa = app.function_app

        create_fn = _get_fn(fa, "aflg_platform_threads_create")
        resp = create_fn(_post_request("/api/threads", {}))
        thread_id = json.loads(resp.get_body())["thread_id"]

        fa.functions_bindings = {}
        wait_fn = _get_fn(fa, "aflg_platform_runs_wait")
        req = _post_request(
            f"/api/threads/{thread_id}/runs/wait",
            {"assistant_id": "agent", "input": {}},
            thread_id=thread_id,
        )
        wait_fn(req)

        thread = store.get(thread_id)
        assert thread is not None
        assert thread.status == "idle"
        assert thread.assistant_id == "agent"

    def test_thread_not_found(self, store: InMemoryThreadStore) -> None:
        g = FakeCompiledGraph()
        app = _build_platform_app(graphs={"agent": g}, store=store)
        fa = app.function_app
        fn = _get_fn(fa, "aflg_platform_runs_wait")

        req = _post_request(
            "/api/threads/missing/runs/wait",
            {"assistant_id": "agent", "input": {}},
            thread_id="missing",
        )
        resp = fn(req)
        assert resp.status_code == 404

    def test_assistant_not_found(self, store: InMemoryThreadStore) -> None:
        g = FakeCompiledGraph()
        app = _build_platform_app(graphs={"agent": g}, store=store)
        fa = app.function_app

        thread = store.create()

        fn = _get_fn(fa, "aflg_platform_runs_wait")
        req = _post_request(
            f"/api/threads/{thread.thread_id}/runs/wait",
            {"assistant_id": "nonexistent", "input": {}},
            thread_id=thread.thread_id,
        )
        resp = fn(req)
        assert resp.status_code == 404
        data = json.loads(resp.get_body())
        assert "nonexistent" in data["detail"]

    def test_thread_assistant_binding_immutable(self, store: InMemoryThreadStore) -> None:
        """Once a thread is bound to an assistant, running with a different one is 409."""
        g1 = FakeCompiledGraph()
        g2 = FakeCompiledGraph()
        app = _build_platform_app(graphs={"alpha": g1, "beta": g2}, store=store)
        fa = app.function_app

        # Create thread and bind to 'alpha'
        thread = store.create()
        store.update(thread.thread_id, assistant_id="alpha")

        fn = _get_fn(fa, "aflg_platform_runs_wait")
        req = _post_request(
            f"/api/threads/{thread.thread_id}/runs/wait",
            {"assistant_id": "beta", "input": {}},
            thread_id=thread.thread_id,
        )
        resp = fn(req)
        assert resp.status_code == 409
        data = json.loads(resp.get_body())
        assert "bound to assistant" in data["detail"]

    def test_invalid_json_body(self, store: InMemoryThreadStore) -> None:
        g = FakeCompiledGraph()
        app = _build_platform_app(graphs={"agent": g}, store=store)
        fa = app.function_app

        thread = store.create()
        fn = _get_fn(fa, "aflg_platform_runs_wait")
        req = func.HttpRequest(
            method="POST",
            url=f"/api/threads/{thread.thread_id}/runs/wait",
            body=b"not json",
            headers={"Content-Type": "application/json"},
            route_params={"thread_id": thread.thread_id},
        )
        resp = fn(req)
        assert resp.status_code == 400

    def test_validation_error(self, store: InMemoryThreadStore) -> None:
        g = FakeCompiledGraph()
        app = _build_platform_app(graphs={"agent": g}, store=store)
        fa = app.function_app

        thread = store.create()
        fn = _get_fn(fa, "aflg_platform_runs_wait")
        # Missing required assistant_id
        req = _post_request(
            f"/api/threads/{thread.thread_id}/runs/wait",
            {"input": {}},
            thread_id=thread.thread_id,
        )
        resp = fn(req)
        assert resp.status_code == 422

    def test_graph_execution_failure(self, store: InMemoryThreadStore) -> None:
        class FailingGraph:
            def invoke(self, input: dict[str, Any], config: dict[str, Any] | None = None) -> Any:
                raise RuntimeError("boom")

            def stream(
                self,
                input: dict[str, Any],
                config: dict[str, Any] | None = None,
                stream_mode: str = "values",
            ) -> Iterator[Any]:
                yield {}

        app = _build_platform_app(graphs={"agent": FailingGraph()}, store=store)
        fa = app.function_app

        thread = store.create()

        fn = _get_fn(fa, "aflg_platform_runs_wait")
        req = _post_request(
            f"/api/threads/{thread.thread_id}/runs/wait",
            {"assistant_id": "agent", "input": {}},
            thread_id=thread.thread_id,
        )
        resp = fn(req)
        assert resp.status_code == 500

        # Thread should be in error state
        updated = store.get(thread.thread_id)
        assert updated is not None
        assert updated.status == "error"

    def test_with_user_config(self, store: InMemoryThreadStore) -> None:
        g = FakeCompiledGraph()
        app = _build_platform_app(graphs={"agent": g}, store=store)
        fa = app.function_app

        thread = store.create()
        fn = _get_fn(fa, "aflg_platform_runs_wait")
        req = _post_request(
            f"/api/threads/{thread.thread_id}/runs/wait",
            {
                "assistant_id": "agent",
                "input": {},
                "config": {"configurable": {"extra_key": "val"}},
            },
            thread_id=thread.thread_id,
        )
        resp = fn(req)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Runs/stream endpoint
# ---------------------------------------------------------------------------


class TestRunsStream:
    def test_stream_success(self, store: InMemoryThreadStore) -> None:
        g = FakeCompiledGraph()
        app = _build_platform_app(graphs={"agent": g}, store=store)
        fa = app.function_app

        thread = store.create()

        fn = _get_fn(fa, "aflg_platform_runs_stream")
        req = _post_request(
            f"/api/threads/{thread.thread_id}/runs/stream",
            {"assistant_id": "agent", "input": {}},
            thread_id=thread.thread_id,
        )
        resp = fn(req)
        assert resp.status_code == 200
        body = resp.get_body().decode()

        # Should have metadata event, data events, and end event
        assert "event: metadata" in body
        assert "run_id" in body
        assert "event: values" in body
        assert "event: end" in body

    def test_stream_thread_not_found(self, store: InMemoryThreadStore) -> None:
        g = FakeCompiledGraph()
        app = _build_platform_app(graphs={"agent": g}, store=store)
        fa = app.function_app
        fn = _get_fn(fa, "aflg_platform_runs_stream")

        req = _post_request(
            "/api/threads/missing/runs/stream",
            {"assistant_id": "agent", "input": {}},
            thread_id="missing",
        )
        resp = fn(req)
        assert resp.status_code == 404

    def test_stream_assistant_not_found(self, store: InMemoryThreadStore) -> None:
        g = FakeCompiledGraph()
        app = _build_platform_app(graphs={"agent": g}, store=store)
        fa = app.function_app

        thread = store.create()

        fn = _get_fn(fa, "aflg_platform_runs_stream")
        req = _post_request(
            f"/api/threads/{thread.thread_id}/runs/stream",
            {"assistant_id": "nonexistent", "input": {}},
            thread_id=thread.thread_id,
        )
        resp = fn(req)
        assert resp.status_code == 404

    def test_stream_not_streamable(self, store: InMemoryThreadStore) -> None:
        """Graph that doesn't support streaming should return 501."""
        g = FakeInvokeOnlyGraph()
        app = _build_platform_app(graphs={"agent": g}, store=store)
        fa = app.function_app

        thread = store.create()

        fn = _get_fn(fa, "aflg_platform_runs_stream")
        req = _post_request(
            f"/api/threads/{thread.thread_id}/runs/stream",
            {"assistant_id": "agent", "input": {}},
            thread_id=thread.thread_id,
        )
        resp = fn(req)
        assert resp.status_code == 501

    def test_stream_thread_binding_mismatch(self, store: InMemoryThreadStore) -> None:
        g1 = FakeCompiledGraph()
        g2 = FakeCompiledGraph()
        app = _build_platform_app(graphs={"alpha": g1, "beta": g2}, store=store)
        fa = app.function_app

        thread = store.create()
        store.update(thread.thread_id, assistant_id="alpha")

        fn = _get_fn(fa, "aflg_platform_runs_stream")
        req = _post_request(
            f"/api/threads/{thread.thread_id}/runs/stream",
            {"assistant_id": "beta", "input": {}},
            thread_id=thread.thread_id,
        )
        resp = fn(req)
        assert resp.status_code == 409

    def test_stream_thread_becomes_idle(self, store: InMemoryThreadStore) -> None:
        g = FakeCompiledGraph()
        app = _build_platform_app(graphs={"agent": g}, store=store)
        fa = app.function_app

        thread = store.create()

        fn = _get_fn(fa, "aflg_platform_runs_stream")
        req = _post_request(
            f"/api/threads/{thread.thread_id}/runs/stream",
            {"assistant_id": "agent", "input": {}},
            thread_id=thread.thread_id,
        )
        fn(req)

        updated = store.get(thread.thread_id)
        assert updated is not None
        assert updated.status == "idle"
        assert updated.assistant_id == "agent"

    def test_stream_failure_sets_error_state(self, store: InMemoryThreadStore) -> None:
        class FailingStreamGraph:
            def invoke(self, input: dict[str, Any], config: dict[str, Any] | None = None) -> Any:
                return {}

            def stream(
                self,
                input: dict[str, Any],
                config: dict[str, Any] | None = None,
                stream_mode: str = "values",
            ) -> Iterator[Any]:
                raise RuntimeError("stream boom")

        app = _build_platform_app(graphs={"agent": FailingStreamGraph()}, store=store)
        fa = app.function_app

        thread = store.create()

        fn = _get_fn(fa, "aflg_platform_runs_stream")
        req = _post_request(
            f"/api/threads/{thread.thread_id}/runs/stream",
            {"assistant_id": "agent", "input": {}},
            thread_id=thread.thread_id,
        )
        resp = fn(req)
        assert resp.status_code == 200  # SSE always 200
        body = resp.get_body().decode()
        assert "event: error" in body
        assert "event: end" in body

        updated = store.get(thread.thread_id)
        assert updated is not None
        assert updated.status == "error"

    def test_stream_invalid_json(self, store: InMemoryThreadStore) -> None:
        g = FakeCompiledGraph()
        app = _build_platform_app(graphs={"agent": g}, store=store)
        fa = app.function_app

        thread = store.create()
        fn = _get_fn(fa, "aflg_platform_runs_stream")
        req = func.HttpRequest(
            method="POST",
            url=f"/api/threads/{thread.thread_id}/runs/stream",
            body=b"not json",
            headers={"Content-Type": "application/json"},
            route_params={"thread_id": thread.thread_id},
        )
        resp = fn(req)
        assert resp.status_code == 400

    def test_stream_max_bytes_exceeded(self, store: InMemoryThreadStore) -> None:
        """Stream should stop when max buffered bytes exceeded."""

        class BigStreamGraph:
            def invoke(self, input: dict[str, Any], config: dict[str, Any] | None = None) -> Any:
                return {}

            def stream(
                self,
                input: dict[str, Any],
                config: dict[str, Any] | None = None,
                stream_mode: str = "values",
            ) -> Iterator[dict[str, Any]]:
                for i in range(1000):
                    yield {"data": "x" * 1000}

        app = LangGraphApp(platform_compat=True, max_stream_response_bytes=500)
        app._thread_store = store
        app.register(graph=BigStreamGraph(), name="agent")
        fa = app.function_app

        thread = store.create()

        fn = _get_fn(fa, "aflg_platform_runs_stream")
        req = _post_request(
            f"/api/threads/{thread.thread_id}/runs/stream",
            {"assistant_id": "agent", "input": {}},
            thread_id=thread.thread_id,
        )
        resp = fn(req)
        body = resp.get_body().decode()
        assert "event: error" in body
        assert "max buffered size" in body


# ---------------------------------------------------------------------------
# Preflight validation (501 for unsupported features)
# ---------------------------------------------------------------------------


class TestPreflightValidation:
    @pytest.mark.parametrize(
        "field,value",
        [
            ("interrupt_before", ["node_a"]),
            ("interrupt_after", ["node_b"]),
            ("webhook", "https://example.com"),
            ("on_completion", "callback"),
            ("after_seconds", 10.0),
            ("if_not_exists", "create"),
            ("checkpoint_id", "cp-123"),
        ],
    )
    def test_unsupported_field_returns_501(
        self, store: InMemoryThreadStore, field: str, value: Any
    ) -> None:
        g = FakeCompiledGraph()
        app = _build_platform_app(graphs={"agent": g}, store=store)
        fa = app.function_app

        thread = store.create()

        fn = _get_fn(fa, "aflg_platform_runs_wait")
        body = {"assistant_id": "agent", "input": {}, field: value}
        req = _post_request(
            f"/api/threads/{thread.thread_id}/runs/wait",
            body,
            thread_id=thread.thread_id,
        )
        resp = fn(req)
        assert resp.status_code == 501

    def test_multitask_reject_allowed(self, store: InMemoryThreadStore) -> None:
        g = FakeCompiledGraph()
        app = _build_platform_app(graphs={"agent": g}, store=store)
        fa = app.function_app

        thread = store.create()
        fn = _get_fn(fa, "aflg_platform_runs_wait")
        req = _post_request(
            f"/api/threads/{thread.thread_id}/runs/wait",
            {"assistant_id": "agent", "input": {}, "multitask_strategy": "reject"},
            thread_id=thread.thread_id,
        )
        resp = fn(req)
        assert resp.status_code == 200

    def test_multitask_non_reject_returns_501(self, store: InMemoryThreadStore) -> None:
        g = FakeCompiledGraph()
        app = _build_platform_app(graphs={"agent": g}, store=store)
        fa = app.function_app

        thread = store.create()
        fn = _get_fn(fa, "aflg_platform_runs_wait")
        req = _post_request(
            f"/api/threads/{thread.thread_id}/runs/wait",
            {"assistant_id": "agent", "input": {}, "multitask_strategy": "enqueue"},
            thread_id=thread.thread_id,
        )
        resp = fn(req)
        assert resp.status_code == 501

    @pytest.mark.parametrize(
        "field,value",
        [
            ("interrupt_before", ["*"]),
            ("webhook", "https://hooks.example.com/callback"),
        ],
    )
    def test_unsupported_field_in_stream_returns_501(
        self, store: InMemoryThreadStore, field: str, value: Any
    ) -> None:
        g = FakeCompiledGraph()
        app = _build_platform_app(graphs={"agent": g}, store=store)
        fa = app.function_app

        thread = store.create()

        fn = _get_fn(fa, "aflg_platform_runs_stream")
        body = {"assistant_id": "agent", "input": {}, field: value}
        req = _post_request(
            f"/api/threads/{thread.thread_id}/runs/stream",
            body,
            thread_id=thread.thread_id,
        )
        resp = fn(req)
        assert resp.status_code == 501


# ---------------------------------------------------------------------------
# Platform error helper
# ---------------------------------------------------------------------------


class TestPlatformError:
    def test_error_format(self) -> None:
        resp = _platform_error(418, "I'm a teapot")
        assert resp.status_code == 418
        data = json.loads(resp.get_body())
        assert data["detail"] == "I'm a teapot"
        assert resp.mimetype == "application/json"


# ---------------------------------------------------------------------------
# PlatformRouteDeps
# ---------------------------------------------------------------------------


class TestPlatformRouteDeps:
    def test_construction(self, store: InMemoryThreadStore) -> None:
        deps = PlatformRouteDeps(
            registrations={},
            thread_store=store,
            auth_level=func.AuthLevel.ANONYMOUS,
            max_stream_response_bytes=1024,
        )
        assert deps.registrations == {}
        assert deps.thread_store is store
        assert deps.auth_level == func.AuthLevel.ANONYMOUS
        assert deps.max_stream_response_bytes == 1024


# ---------------------------------------------------------------------------
# Oracle review fixes — additional tests
# ---------------------------------------------------------------------------


class TestBusyThreadReject:
    """Threads marked 'busy' must return 409 on new run attempts."""

    def test_runs_wait_busy_thread_returns_409(self, store: InMemoryThreadStore) -> None:
        g = FakeCompiledGraph()
        app = _build_platform_app(graphs={"agent": g}, store=store)
        fa = app.function_app

        thread = store.create()
        store.update(thread.thread_id, status="busy", assistant_id="agent")

        fn = _get_fn(fa, "aflg_platform_runs_wait")
        req = _post_request(
            f"/api/threads/{thread.thread_id}/runs/wait",
            {"assistant_id": "agent", "input": {}},
            thread_id=thread.thread_id,
        )
        resp = fn(req)
        assert resp.status_code == 409
        data = json.loads(resp.get_body())
        assert "busy" in data["detail"]

    def test_runs_stream_busy_thread_returns_409(self, store: InMemoryThreadStore) -> None:
        g = FakeCompiledGraph()
        app = _build_platform_app(graphs={"agent": g}, store=store)
        fa = app.function_app

        thread = store.create()
        store.update(thread.thread_id, status="busy", assistant_id="agent")

        fn = _get_fn(fa, "aflg_platform_runs_stream")
        req = _post_request(
            f"/api/threads/{thread.thread_id}/runs/stream",
            {"assistant_id": "agent", "input": {}},
            thread_id=thread.thread_id,
        )
        resp = fn(req)
        assert resp.status_code == 409
        data = json.loads(resp.get_body())
        assert "busy" in data["detail"]

    def test_idle_thread_can_run(self, store: InMemoryThreadStore) -> None:
        g = FakeCompiledGraph()
        app = _build_platform_app(graphs={"agent": g}, store=store)
        fa = app.function_app

        thread = store.create()
        # Thread is idle by default

        fn = _get_fn(fa, "aflg_platform_runs_wait")
        req = _post_request(
            f"/api/threads/{thread.thread_id}/runs/wait",
            {"assistant_id": "agent", "input": {}},
            thread_id=thread.thread_id,
        )
        resp = fn(req)
        assert resp.status_code == 200


class TestAssistantsSearchInvalidJson:
    """Invalid JSON in assistants_search should return 400."""

    def test_invalid_json_returns_400(
        self, graph: FakeCompiledGraph, store: InMemoryThreadStore,
    ) -> None:
        app = _build_platform_app(graphs={"agent": graph}, store=store)
        fa = app.function_app
        fn = _get_fn(fa, "aflg_platform_assistants_search")

        req = func.HttpRequest(
            method="POST",
            url="/api/assistants/search",
            body=b"not valid json",
            headers={"Content-Type": "application/json"},
        )
        resp = fn(req)
        assert resp.status_code == 400
        data = json.loads(resp.get_body())
        assert "Invalid JSON" in data["detail"]


class TestContentLocationHeader:
    """Runs endpoints must include Content-Location header."""

    def test_runs_wait_has_content_location(self, store: InMemoryThreadStore) -> None:
        g = FakeCompiledGraph()
        app = _build_platform_app(graphs={"agent": g}, store=store)
        fa = app.function_app

        thread = store.create()

        fn = _get_fn(fa, "aflg_platform_runs_wait")
        req = _post_request(
            f"/api/threads/{thread.thread_id}/runs/wait",
            {"assistant_id": "agent", "input": {}},
            thread_id=thread.thread_id,
        )
        resp = fn(req)
        assert resp.status_code == 200
        headers = dict(resp.headers)
        assert "Content-Location" in headers
        assert f"/api/threads/{thread.thread_id}/runs/" in headers["Content-Location"]

    def test_runs_stream_has_content_location(self, store: InMemoryThreadStore) -> None:
        g = FakeCompiledGraph()
        app = _build_platform_app(graphs={"agent": g}, store=store)
        fa = app.function_app

        thread = store.create()

        fn = _get_fn(fa, "aflg_platform_runs_stream")
        req = _post_request(
            f"/api/threads/{thread.thread_id}/runs/stream",
            {"assistant_id": "agent", "input": {}},
            thread_id=thread.thread_id,
        )
        resp = fn(req)
        assert resp.status_code == 200
        headers = dict(resp.headers)
        assert "Content-Location" in headers
        assert f"/api/threads/{thread.thread_id}/runs/" in headers["Content-Location"]


class TestAdditionalPreflightFields:
    """command and feedback_keys should return 501."""

    @pytest.mark.parametrize(
        "field,value",
        [
            ("command", {"resume": "value"}),
            ("feedback_keys", ["key1", "key2"]),
        ],
    )
    def test_unsupported_new_fields_return_501(
        self, store: InMemoryThreadStore, field: str, value: Any
    ) -> None:
        g = FakeCompiledGraph()
        app = _build_platform_app(graphs={"agent": g}, store=store)
        fa = app.function_app

        thread = store.create()

        fn = _get_fn(fa, "aflg_platform_runs_wait")
        body = {"assistant_id": "agent", "input": {}, field: value}
        req = _post_request(
            f"/api/threads/{thread.thread_id}/runs/wait",
            body,
            thread_id=thread.thread_id,
        )
        resp = fn(req)
        assert resp.status_code == 501


class TestStableAssistantTimestamps:
    """Assistant timestamps should be stable across calls."""

    def test_timestamps_are_stable(
        self, graph: FakeCompiledGraph, store: InMemoryThreadStore,
    ) -> None:
        app = _build_platform_app(graphs={"agent": graph}, store=store)
        fa = app.function_app
        fn = _get_fn(fa, "aflg_platform_assistants_get")

        req1 = _get_request("/api/assistants/agent", assistant_id="agent")
        resp1 = fn(req1)
        data1 = json.loads(resp1.get_body())

        req2 = _get_request("/api/assistants/agent", assistant_id="agent")
        resp2 = fn(req2)
        data2 = json.loads(resp2.get_body())

        assert data1["created_at"] == data2["created_at"]
        assert data1["updated_at"] == data2["updated_at"]
