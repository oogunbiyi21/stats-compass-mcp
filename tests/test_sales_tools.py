"""Stats Compass on any sales data (0.3.36): three top-level tools from core 0.1.42.

sales_verdict, sales_seasonality and promotion_lift are offered directly, not
behind describe/execute: they are the reason to load a sales table. They only
read DataFrames, so they are marked read-only. melt, for wide retailer exports,
is a transform, reached through execute_transform_tool.
"""

import asyncio
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from fastmcp import FastMCP

from stats_compass_mcp import exports
from stats_compass_mcp.session import SessionManager
from stats_compass_mcp.tools import register_all_tools

SID = "a1b2c3d4e5f60718293a4b5c6d7e8f91"
CTX = SimpleNamespace(session_id=SID)
SALES_TOOLS = ("sales_verdict", "sales_seasonality", "promotion_lift")


@pytest.fixture
def served(tmp_path, monkeypatch):
    monkeypatch.setattr(exports, "EXPORTS_BASE_DIR", tmp_path)
    monkeypatch.setattr(exports, "SERVER_URL", "")
    mcp = FastMCP("test")
    manager = SessionManager(confine_files=False)
    register_all_tools(mcp, manager)
    tools = asyncio.run(mcp._tool_manager.get_tools())
    return tools, manager.get_or_create(SID)


def sell_out() -> pd.DataFrame:
    """Weekly sell-out by retailer, weeks ending Saturday, a promotion at Tesco in June."""
    rng = np.random.default_rng(3)
    weeks = pd.date_range(end="2026-10-24", periods=130, freq="W-SAT")
    years = (weeks - weeks[0]).days.to_numpy() / 365.25
    rows = []
    for retailer, base in (("Tesco", 6000), ("Sainsbury's", 9000)):
        units = base * (1 + 0.2 * np.sin(2 * np.pi * years)) * (1 + 0.06 * rng.standard_normal(len(weeks)))
        on = (retailer == "Tesco") & (weeks >= "2026-06-06") & (weeks <= "2026-06-27")
        units = np.where(on, units * 1.35, units)
        rows += [{"week_ending": w.date().isoformat(), "retailer": retailer, "units": round(u)} for w, u in zip(weeks, units)]
    return pd.DataFrame(rows)


def test_offered_at_the_top_and_read_only(served):
    tools, _ = served
    for name in SALES_TOOLS:
        assert name in tools
        assert tools[name].annotations.readOnlyHint is True


def test_sales_verdict(served):
    tools, session = served
    session.state.set_dataframe(sell_out(), name="sales", operation="test")
    result = tools["sales_verdict"].fn(ctx=CTX, date_column="week_ending", value_column="units", kind="units", group_by=["retailer"])
    assert result["frequency"] == "weekly"
    assert result["period"] == "Week ending 24 October 2026"
    assert {r["group"] for r in result["rows"]} == {"Tesco", "Sainsbury's"}
    assert all(r["summary"] for r in result["rows"])


def test_sales_seasonality(served):
    tools, session = served
    session.state.set_dataframe(sell_out(), name="sales", operation="test")
    result = tools["sales_seasonality"].fn(ctx=CTX, date_column="week_ending", value_column="units")
    assert len(result["rows"][0]["months"]) == 12
    assert result["summary"].startswith("Sales usually run ")


def test_promotion_lift_from_windows(served):
    tools, session = served
    session.state.set_dataframe(sell_out(), name="sales", operation="test")
    result = tools["promotion_lift"].fn(
        ctx=CTX, date_column="week_ending", value_column="units", kind="units", group_by=["retailer"],
        windows=[{"name": "Summer offer", "start": "2026-05-31", "end": "2026-06-27", "group": {"retailer": "Tesco"}}],
    )
    row = result["rows"][0]
    assert row["group"] == "Tesco" and row["verdict"] == "real change"
    assert row["summary"].startswith("Summer offer, 31 May – 27 June 2026: +")


def test_a_wide_export_is_melted_through_the_transform_tools(served):
    tools, session = served
    long = sell_out()
    wide = long.pivot_table(index="retailer", columns="week_ending", values="units").reset_index()
    wide.columns = [str(c) for c in wide.columns]
    session.state.set_dataframe(wide, name="wide", operation="test")
    tools["execute_transform_tool"].fn(
        ctx=CTX, tool_name="melt",
        params={"dataframe_name": "wide", "id_columns": ["retailer"], "variable_name": "week_ending", "value_name": "units", "save_as": "long"},
    )
    result = tools["sales_verdict"].fn(ctx=CTX, dataframe_name="long", date_column="week_ending", value_column="units", kind="units")
    assert result["frequency"] == "weekly"


def test_promotions_left_out_of_the_verdict_and_seasonality(served):
    """0.3.37: the verdict and seasonality take the promotions, as the lift does."""
    tools, session = served
    session.state.set_dataframe(sell_out(), name="sales", operation="test")
    calendar = pd.DataFrame([{"retailer": "all", "start": "2026-05-31", "end": "2026-06-27", "event": "Summer offer"}])
    session.state.set_dataframe(calendar, name="promos", operation="test")
    # Loading the calendar made it the active DataFrame: name the sales table.
    promos = {"dataframe_name": "sales", "calendar_dataframe": "promos", "calendar_name_column": "event"}
    verdict = tools["sales_verdict"].fn(ctx=CTX, date_column="week_ending", value_column="units", kind="units",
                                        group_by=["retailer"], **promos)
    assert any("left out of what's expected" in n for n in verdict["notes"])
    seasons = tools["sales_seasonality"].fn(ctx=CTX, date_column="week_ending", value_column="units", **promos)
    assert "were left out" in seasons["rows"][0]["basis"]
    lift = tools["promotion_lift"].fn(ctx=CTX, date_column="week_ending", value_column="units", kind="units",
                                      group_by=["retailer"], **promos)
    assert {r["group"] for r in lift["rows"]} == {"Tesco", "Sainsbury's"}  # "all" reaches both
    assert all(r["after_summary"] for r in lift["rows"] if r["verdict"] != "insufficient")
