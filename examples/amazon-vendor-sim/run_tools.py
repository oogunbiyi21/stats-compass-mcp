"""Run the Stats Compass sales tools on the simulated Amazon Vendor data, end to end.

The path an AI assistant takes through the MCP server: load the CSVs, merge
the product master for categories, then sales_verdict, sales_seasonality and
promotion_lift. It calls core's tool functions directly (the MCP tools are
thin wrappers over them) and writes results.md and results.json beside it.

Run: python run_tools.py   (after python generate.py)
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from stats_compass_core.data.load_csv import LoadCSVInput, load_csv
from stats_compass_core.data.merge_dataframes import MergeDataFramesInput, merge_dataframes
from stats_compass_core.state import DataFrameState
from stats_compass_core.workflows.sales import (
    PromotionLiftInput,
    SalesSeasonalityInput,
    SalesVerdictInput,
    promotion_lift,
    sales_seasonality,
    sales_verdict,
)

HERE = Path(__file__).parent
DATA = HERE / "data"
TRUTH = json.loads((DATA / "truth.json").read_text())


def load(state: DataFrameState) -> None:
    for name in ("sell_out", "sell_in", "promo_calendar", "product_master"):
        load_csv(state, LoadCSVInput(file_path=str(DATA / f"{name}.csv"), name=name))
    merge_dataframes(state, MergeDataFramesInput(
        left_dataframe="sell_out", right_dataframe="product_master", on=["ASIN"], how="left",
        save_as="sell_out_cat",
    ))


def expand_all_rows(state: DataFrameState) -> None:
    """The calendar's "all" rows, one per ASIN: the sales tools match a calendar's
    ASIN column literally, so "all" matches no product. (A user step today.)"""
    cal = state.get_dataframe("promo_calendar")
    asins = state.get_dataframe("product_master")["ASIN"].tolist()
    rows = []
    for _, r in cal.iterrows():
        for a in (asins if r["ASIN"] == "all" else [r["ASIN"]]):
            rows.append({**r.to_dict(), "ASIN": a})
    state.set_dataframe(pd.DataFrame(rows), name="promo_calendar_by_asin", operation="expand_all")


def main() -> None:
    state = DataFrameState()
    load(state)
    expand_all_rows(state)
    common = {"dataframe_name": "sell_out_cat", "date_column": "Week ending"}
    out: dict = {}

    out["verdict_cogs_by_asin"] = sales_verdict(state, SalesVerdictInput(
        **common, value_column="Shipped COGS", group_by=["ASIN"], currency="£")).model_dump(mode="json")
    out["verdict_cogs_total"] = sales_verdict(state, SalesVerdictInput(
        **common, value_column="Shipped COGS", currency="£")).model_dump(mode="json")
    out["verdict_units_by_asin"] = sales_verdict(state, SalesVerdictInput(
        **common, value_column="Ordered Units", kind="units", group_by=["ASIN"])).model_dump(mode="json")
    out["verdict_units_total"] = sales_verdict(state, SalesVerdictInput(
        **common, value_column="Ordered Units", kind="units")).model_dump(mode="json")
    # The three weeks after the microfibre cloths' Lightning deal: is the dip seen?
    cloths = next(t for t in TRUTH["promotions"] if "cloths" in t["event"])
    out["verdict_after_pull_forward"] = sales_verdict(state, SalesVerdictInput(
        **common, value_column="Shipped COGS", group_by=["ASIN"], currency="£",
        period_start="2026-04-19", period_end="2026-05-09")).model_dump(mode="json")
    out["verdict_after_pull_forward"]["rows"] = [r for r in out["verdict_after_pull_forward"]["rows"] if r["group"] == cloths["asin"]]

    out["seasonality_total"] = sales_seasonality(state, SalesSeasonalityInput(
        **common, value_column="Shipped COGS")).model_dump(mode="json")
    out["seasonality_by_category"] = sales_seasonality(state, SalesSeasonalityInput(
        **common, value_column="Shipped COGS", group_by=["Category"])).model_dump(mode="json")

    out["lift_cogs_by_asin"] = promotion_lift(state, PromotionLiftInput(
        **common, value_column="Shipped COGS", group_by=["ASIN"], currency="£",
        calendar_dataframe="promo_calendar_by_asin", calendar_start_column="Start",
        calendar_end_column="End", calendar_name_column="Event", include_series=True)).model_dump(mode="json")
    out["lift_cogs_total"] = promotion_lift(state, PromotionLiftInput(
        **common, value_column="Shipped COGS", currency="£",
        calendar_dataframe="promo_calendar", calendar_start_column="Start",
        calendar_end_column="End", calendar_name_column="Event")).model_dump(mode="json")
    out["lift_units_by_asin"] = promotion_lift(state, PromotionLiftInput(
        **common, value_column="Ordered Units", kind="units", group_by=["ASIN"],
        calendar_dataframe="promo_calendar_by_asin", calendar_start_column="Start",
        calendar_end_column="End", calendar_name_column="Event")).model_dump(mode="json")

    (HERE / "results.json").write_text(json.dumps(out, indent=1))
    print("wrote results.json")


if __name__ == "__main__":
    main()
