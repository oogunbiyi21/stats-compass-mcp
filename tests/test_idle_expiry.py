"""Idle sessions are removed after a time, never in the middle of a call (22 Oct 2026).

The commerce privacy policy says an AI-assistant session's data "is removed
after 24 hours of inactivity". Until 0.3.35 the SessionManager had no idle
expiry: a session's dataframes (on hosted, load_orders frames with order rows
and Shopify customer ids) stayed in memory until capacity eviction,
delete_session or a restart. hosted's sweeper now calls evict_idle(24 hours);
`serve` runs its own sweep.
"""

import asyncio
import threading
import time
from datetime import datetime, timedelta
from types import SimpleNamespace

import pandas as pd
import pytest
from fastmcp import FastMCP

from stats_compass_mcp import exports, safety
from stats_compass_mcp.session import (
    SessionActivityMiddleware,
    SessionManager,
    get_session,
    idle_expiry_from_env,
    start_idle_sweeper,
)

DAY = timedelta(hours=24)


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(exports, "EXPORTS_BASE_DIR", tmp_path / "exports")
    monkeypatch.setattr(exports, "UPLOADS_BASE_DIR", tmp_path / "uploads")
    yield tmp_path
    safety.set_session_folder_namer(None)


def _aged(manager: SessionManager, session_id: str, idle: timedelta):
    session = manager.get_or_create(session_id)
    session.last_active = datetime.now() - idle
    return session


class TestEvictIdle:
    def test_idle_sessions_go_and_active_ones_stay(self, dirs):
        manager = SessionManager()
        _aged(manager, "idle", DAY + timedelta(minutes=1))
        _aged(manager, "active", timedelta(minutes=5))
        assert manager.evict_idle(DAY) == 1
        assert manager.get("idle") is None
        assert manager.get("active") is not None

    def test_seconds_work_as_well_as_a_timedelta(self, dirs):
        manager = SessionManager()
        _aged(manager, "idle", timedelta(seconds=120))
        assert manager.evict_idle(60.0) == 1

    def test_its_data_and_exported_files_go_with_it(self, dirs):
        manager = SessionManager()
        session = _aged(manager, "idle", DAY * 2)
        session.state.set_dataframe(pd.DataFrame({"customer_id": [1, 2]}), "orders", "test")
        export = exports.EXPORTS_BASE_DIR / safety.session_folder("idle") / "data" / "orders.csv"
        export.parent.mkdir(parents=True)
        export.write_text("customer_id\n1\n2\n")
        assert manager.evict_idle(DAY) == 1
        assert not export.exists()
        assert manager.get_stats()["active_sessions"] == 0

    @pytest.mark.parametrize("max_idle", [0, -1, timedelta(0), timedelta(hours=-1)])
    def test_a_non_positive_limit_is_refused_not_taken_as_evict_everything(self, dirs, max_idle):
        manager = SessionManager()
        _aged(manager, "idle", DAY)
        with pytest.raises(ValueError, match="positive"):
            manager.evict_idle(max_idle)
        assert manager.get("idle") is not None

    def test_now_can_be_given(self, dirs):
        manager = SessionManager()
        manager.get_or_create("s")
        assert manager.evict_idle(DAY, now=datetime.now() + DAY + timedelta(seconds=1)) == 1


class TestInUse:
    def test_a_session_in_a_call_is_never_evicted(self, dirs):
        manager = SessionManager()
        session = _aged(manager, "busy", DAY * 3)
        with manager.in_use("busy"):
            session.last_active = datetime.now() - DAY * 3
            assert manager.evict_idle(DAY) == 0
        # Touched on the way out: idle time runs from the end of the call.
        assert manager.evict_idle(DAY) == 0
        assert manager.get("busy") is not None

    def test_overlapping_calls_nest(self, dirs):
        manager = SessionManager()
        session = _aged(manager, "busy", DAY * 3)
        with manager.in_use("busy"):
            with manager.in_use("busy"):
                pass
            session.last_active = datetime.now() - DAY * 3
            assert manager.evict_idle(DAY) == 0  # still one call under way
        session.last_active = datetime.now() - DAY * 3
        assert manager.evict_idle(DAY) == 1

    def test_capacity_eviction_skips_a_session_in_a_call(self, dirs):
        manager = SessionManager(max_sessions=2)
        _aged(manager, "oldest-but-busy", DAY)
        _aged(manager, "older", timedelta(hours=1))
        with manager.in_use("oldest-but-busy"):
            manager.get_or_create("new")
        assert manager.get("oldest-but-busy") is not None
        assert manager.get("older") is None

    def test_with_every_session_in_a_call_a_new_one_is_admitted_over_capacity(self, dirs):
        manager = SessionManager(max_sessions=1)
        manager.get_or_create("busy")
        with manager.in_use("busy"):
            manager.get_or_create("new")
        assert manager.get("busy") is not None and manager.get("new") is not None


def _through_middleware(manager: SessionManager, call_next, fastmcp_context=object()):
    """Run a tool call through SessionActivityMiddleware, as FastMCP would.

    Called directly, without a FastMCP server: on the locked fastmcp 2.14.2 an
    in-memory client leaves its task worker on a closed event loop, which broke
    later tests that start the HTTP app.
    """
    middleware = SessionActivityMiddleware(manager)
    return asyncio.run(middleware.on_call_tool(SimpleNamespace(fastmcp_context=fastmcp_context), call_next))


def _probe(manager: SessionManager):
    """A tool that, mid-call, ages its own session and runs the sweep."""

    async def call_next(context):
        session = get_session(object(), manager)  # the resolver names the session
        session.last_active = datetime.now() - DAY * 2
        removed = manager.evict_idle(DAY)
        return {"removed": removed, "still_there": manager.get("user-1") is not None}

    return call_next


class TestMiddleware:
    def test_a_tool_call_holds_its_session_until_it_ends(self, dirs):
        manager = SessionManager(session_id_resolver=lambda ctx: "user-1")
        assert _through_middleware(manager, _probe(manager)) == {"removed": 0, "still_there": True}
        # Touched as the call ended, so it is not idle now either.
        assert manager.evict_idle(DAY) == 0

    def test_without_it_the_same_call_loses_its_session(self, dirs):
        """The control: the probe really does age its session past the limit."""
        manager = SessionManager(session_id_resolver=lambda ctx: "user-1")
        assert asyncio.run(_probe(manager)(None)) == {"removed": 1, "still_there": False}

    def test_a_call_running_in_a_worker_thread_is_held_against_a_sweep_from_another(self, dirs):
        manager = SessionManager(session_id_resolver=lambda ctx: "user-1")
        swept = threading.Event()
        removed: list[int] = []

        def sweeper() -> None:
            removed.append(manager.evict_idle(DAY))
            swept.set()

        async def call_next(context):
            def tool() -> bool:
                session = get_session(object(), manager)
                session.last_active = datetime.now() - DAY * 2
                threading.Thread(target=sweeper).start()
                assert swept.wait(5)
                return manager.get("user-1") is not None

            return await asyncio.to_thread(tool)

        assert _through_middleware(manager, call_next) is True
        assert removed == [0]

    def test_a_resolver_that_fails_lets_the_call_run(self, dirs):
        def resolver(ctx):
            raise RuntimeError("no token")

        manager = SessionManager(session_id_resolver=resolver)

        async def call_next(context):
            return "pong"

        assert _through_middleware(manager, call_next) == "pong"
        assert manager._in_use == {}

    def test_no_context_lets_the_call_run(self, dirs):
        manager = SessionManager()

        async def call_next(context):
            return "pong"

        assert _through_middleware(manager, call_next, fastmcp_context=None) == "pong"

    def test_register_all_tools_adds_it(self, dirs):
        from stats_compass_mcp.tools import register_all_tools

        manager = SessionManager()
        mcp = FastMCP("test")
        register_all_tools(mcp, manager)
        assert any(isinstance(m, SessionActivityMiddleware) for m in mcp.middleware)


class TestThreads:
    def test_sweeps_and_calls_together(self, dirs):
        manager = SessionManager(max_sessions=20)
        errors: list[BaseException] = []
        stop = time.monotonic() + 0.5

        def calls(n: int) -> None:
            try:
                i = 0
                while time.monotonic() < stop:
                    sid = f"s{n}-{i % 30}"
                    with manager.in_use(sid):
                        manager.get_or_create(sid)
                    i += 1
            except BaseException as e:  # noqa: BLE001
                errors.append(e)

        def sweeps() -> None:
            try:
                while time.monotonic() < stop:
                    manager.evict_idle(1e-6)
                    manager.get_stats()
            except BaseException as e:  # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=calls, args=(n,)) for n in range(4)] + [threading.Thread(target=sweeps)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert manager._in_use == {}


class TestServedSweep:
    @pytest.mark.parametrize(
        "value, expected",
        [(None, DAY), ("", DAY), ("1.5", timedelta(hours=1.5)), ("0", None), ("-2", None), ("soon", DAY)],
    )
    def test_the_setting(self, monkeypatch, value, expected):
        if value is None:
            monkeypatch.delenv("STATS_COMPASS_SESSION_IDLE_HOURS", raising=False)
        else:
            monkeypatch.setenv("STATS_COMPASS_SESSION_IDLE_HOURS", value)
        assert idle_expiry_from_env() == expected

    def test_the_sweeper_removes_idle_sessions_and_stops(self, dirs):
        manager = SessionManager()
        _aged(manager, "idle", timedelta(hours=1))
        manager.get_or_create("active")
        stop = start_idle_sweeper(manager, timedelta(minutes=30), every=0.02)
        try:
            deadline = time.monotonic() + 2
            while manager.get_stats()["active_sessions"] > 1 and time.monotonic() < deadline:
                time.sleep(0.02)
        finally:
            stop.set()
        assert manager.get_stats()["active_sessions"] == 1
        assert manager._sessions.get("active") is not None

    def test_serve_turns_it_on_and_stdio_does_not(self, monkeypatch, dirs):
        from stats_compass_mcp import server

        started: list[timedelta] = []
        monkeypatch.setattr(server, "start_idle_sweeper", lambda manager, max_idle: started.append(max_idle))
        monkeypatch.delenv("STATS_COMPASS_SESSION_IDLE_HOURS", raising=False)
        server.create_mcp_server(local=True)
        assert started == []
        server.create_mcp_server(with_storage=False, idle_sweep=True)
        assert started == [DAY]
        monkeypatch.setenv("STATS_COMPASS_SESSION_IDLE_HOURS", "0")
        server.create_mcp_server(idle_sweep=True)
        assert started == [DAY]
