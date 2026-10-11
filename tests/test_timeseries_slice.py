"""run_timeseries_workflow fits at most the most recent 500 rows (known issue, 9 October 2026).

The slice was stored with set_dataframe's arguments swapped. The TypeError was
swallowed by a bare except, so every series was fitted whole: on hosted, a long
series held the event loop for the whole fit.
"""

import asyncio
import logging
import warnings
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from fastmcp import FastMCP

from stats_compass_mcp import exports
from stats_compass_mcp.session import SessionManager
from stats_compass_mcp.tools import register_all_tools
from stats_compass_mcp.tools.workflows import most_recent_rows

SID = "a1b2c3d4e5f60718293a4b5c6d7e8f90"


@pytest.fixture
def served(tmp_path, monkeypatch):
    monkeypatch.setattr(exports, "EXPORTS_BASE_DIR", tmp_path)
    monkeypatch.setattr(exports, "SERVER_URL", "")
    mcp = FastMCP("test")
    manager = SessionManager(confine_files=False)
    register_all_tools(mcp, manager)
    tools = asyncio.run(mcp._tool_manager.get_tools())
    return tools, manager.get_or_create(SID)


def _series(rows: int, with_dates: bool = False) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"y": np.cumsum(rng.normal(size=rows)) + 100})
    if with_dates:
        df["date"] = pd.date_range("2024-01-01", periods=rows, freq="D")
    return df


def _run(tools, **kwargs) -> dict:
    result = tools["run_timeseries_workflow"].fn(ctx=SimpleNamespace(session_id=SID), **kwargs)
    return result[0] if isinstance(result, list) else result


def _fitted_rows(result: dict) -> int:
    counts = [s["result"]["n_observations"] for s in result["steps"]
              if isinstance(s.get("result"), dict) and "n_observations" in s["result"]]
    assert len(counts) == 1, result["steps"]
    return counts[0]


def _names(session) -> set[str]:
    return {info.name for info in session.state.list_dataframes()}


class TestSlicing:
    def test_a_long_series_is_fitted_on_its_last_500_rows(self, served):
        tools, session = served
        session.state.set_dataframe(_series(600), name="series", operation="test")
        result = _run(tools, target_column="y", dataframe_name="series")
        assert result["status"] == "success"
        assert _fitted_rows(result) == 500
        # The forecast says what it was fitted on; the slice itself is removed afterwards.
        assert "series_last500_forecast" in _names(session)
        assert "series_last500" not in _names(session)
        assert len(session.state.get_dataframe("series")) == 600

    def test_the_slice_forecasts_without_statsmodels_index_warnings(self, served):
        # A slice keeping rows 100-599 drew "No supported index ... will result in an
        # exception" from statsmodels; the slice is renumbered from 0.
        tools, session = served
        session.state.set_dataframe(_series(600), name="series", operation="test")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = _run(tools, target_column="y", dataframe_name="series")
        assert _fitted_rows(result) == 500
        assert not [w for w in caught if "supported index" in str(w.message)]

    def test_a_series_with_a_date_column_out_of_order_is_sliced_by_date(self, served):
        tools, session = served
        df = _series(600, with_dates=True).sample(frac=1, random_state=1)
        session.state.set_dataframe(df, name="series", operation="test")
        result = _run(tools, target_column="y", dataframe_name="series", date_column="date")
        assert result["status"] == "success"
        assert _fitted_rows(result) == 500

    def test_the_active_dataframe_is_sliced_when_none_is_named(self, served):
        tools, session = served
        session.state.set_dataframe(_series(600), name="series", operation="test")
        assert _fitted_rows(_run(tools, target_column="y")) == 500

    def test_a_short_series_is_fitted_whole(self, served):
        tools, session = served
        session.state.set_dataframe(_series(120), name="series", operation="test")
        assert _fitted_rows(_run(tools, target_column="y", dataframe_name="series")) == 120
        assert "series_forecast" in _names(session)

    def test_a_dataframe_the_user_named_like_the_slice_is_left_alone(self, served):
        tools, session = served
        session.state.set_dataframe(_series(600), name="series", operation="test")
        theirs = pd.DataFrame({"mine": [1, 2, 3]})
        session.state.set_dataframe(theirs, name="series_last500", operation="test")
        assert _fitted_rows(_run(tools, target_column="y", dataframe_name="series")) == 500
        assert session.state.get_dataframe("series_last500").equals(theirs)
        assert "series_last500_2" not in _names(session)

    def test_if_the_slice_cannot_be_stored_the_whole_series_is_fitted_and_logged(self, served, monkeypatch, caplog):
        tools, session = served
        session.state.set_dataframe(_series(600), name="series", operation="test")
        store = session.state.set_dataframe

        def no_room_for_slices(df, name, operation, set_active=True):
            if operation == "timeseries_slice":
                raise MemoryError("over the session's memory limit")
            return store(df, name=name, operation=operation, set_active=set_active)

        monkeypatch.setattr(session.state, "set_dataframe", no_room_for_slices)
        with caplog.at_level(logging.WARNING, logger="stats_compass_mcp.tools.workflows"):
            result = _run(tools, target_column="y", dataframe_name="series")
        assert _fitted_rows(result) == 600
        assert "fitting all 600" in caplog.text


class TestMostRecentRows:
    def test_rows_out_of_date_order_are_cut_by_date(self):
        df = _series(600, with_dates=True).sample(frac=1, random_state=1)
        kept = most_recent_rows(df, "date", 500)
        assert sorted(kept["date"]) == list(pd.date_range("2024-01-01", periods=600, freq="D")[100:])

    def test_unreadable_dates_are_dropped_first(self):
        df = pd.DataFrame({"date": ["2024-01-03", "not a date", "2024-01-01", "2024-01-02"], "y": [3, 0, 1, 2]})
        assert list(most_recent_rows(df, "date", 3)["y"]) == [1, 2, 3]

    def test_without_a_date_column_the_last_rows_are_kept(self):
        df = _series(600)
        kept = most_recent_rows(df, None, 500)
        assert list(kept["y"]) == list(df["y"].iloc[100:])
        assert list(kept.index) == list(range(500))

    def test_a_date_index_is_kept(self):
        df = _series(600).set_index(pd.date_range("2024-01-01", periods=600, freq="D"))
        assert most_recent_rows(df, None, 500).index.equals(df.index[100:])
