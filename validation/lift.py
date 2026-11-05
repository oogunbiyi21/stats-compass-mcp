"""The checker's measurement, with the numbers the page doesn't show.

``measure`` makes exactly the promotion_lift call assets/checker/checker.py's
``analyse`` makes (``same_as_analyse`` checks that), and returns the row's raw
numbers: the lift and its 90% interval in percent, the verdict, and each day's
actual, expected and 90% range.
"""

import importlib.util
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("checker", ROOT / "assets" / "checker" / "checker.py")
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)


def report(path: Path) -> pd.DataFrame:
    """A daily report as the checker reads it (checker.read_export)."""
    return checker.read_export(path.read_text())


def csv_text(rows: pd.DataFrame) -> str:
    out = rows.assign(Day=rows["Day"].dt.strftime("%Y-%m-%d"))
    return out.to_csv(index=False)


def measure(rows: pd.DataFrame, start: str, end: str, others: list[dict] | None = None) -> dict:
    first, last = pd.Timestamp(start), pd.Timestamp(end)
    extra = checker.other_sales(others, first, last, rows)
    state = checker.DataFrameState()
    state.set_dataframe(rows, name="sales", operation="upload")
    lift = checker.promotion_lift(state, checker.PromotionLiftInput(
        dataframe_name="sales", date_column="Day", value_column="Net sales", currency="£",
        include_series=True, windows=[{"name": "The sale", "start": first.date(), "end": last.date()}, *extra],
    ))
    row = next(r for r in lift.rows if (r.start, r.end) == (first.date().isoformat(), last.date().isoformat()))
    days = [p for p in row.series or [] if p.in_promotion]
    return {
        "verdict": row.verdict,
        "summary": row.summary,
        "estimate_pct": row.estimate_pct,
        "interval_lo": row.interval_pct[0] if row.interval_pct else None,
        "interval_hi": row.interval_pct[1] if row.interval_pct else None,
        "days": len(days),
        "days_in_range": sum(1 for p in days if p.actual is not None and p.low <= p.actual <= p.high),
        "days_with_data": sum(1 for p in days if p.actual is not None),
    }


def same_as_analyse(rows: pd.DataFrame, start: str, end: str) -> bool:
    return measure(rows, start, end)["summary"].replace("The sale", "X") == checker.analyse(csv_text(rows), start, end, None, "£", "X")["summary"]
