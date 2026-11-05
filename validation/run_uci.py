"""Placebo, coverage and injected lifts on UCI Online Retail II, through the checker's own measurement.

Run after fetch_uci.py: python -I validation/run_uci.py
Writes results/uci_placebo.csv, results/uci_injected.csv and prints the tables in the README.
"""

from pathlib import Path

import numpy as np
import pandas as pd

import lift

HERE = Path(__file__).parent
RESULTS = HERE / "results"
LENGTHS = (4, 7, 14, 21)
LIFTS = (0.1, 0.2, 0.5, 0.8)
PER_CELL = 60
# 13 months before the first window is the data's start (1 Dec 2009); the last window
# leaves 3 weeks of data after it (the data ends 9 Dec 2011).
FIRST, LAST = pd.Timestamp("2011-01-04"), pd.Timestamp("2011-11-18")
# 28 real days before a window starting before this include the Christmas closure.
AFTER_CLOSURE = pd.Timestamp("2011-02-01")
# Known events in 2011: closures, bank holidays, the royal wedding, Black Friday weekend.
EVENTS = pd.to_datetime([
    "2011-01-01", "2011-01-02", "2011-01-03", "2011-04-22", "2011-04-23", "2011-04-24", "2011-04-25",
    "2011-04-29", "2011-05-02", "2011-05-30", "2011-08-29", "2011-11-25", "2011-11-26", "2011-11-27", "2011-11-28",
])


def windows(length: int) -> list[pd.Timestamp]:
    """Every start whose window, and the day either side, is clear of the events."""
    starts = []
    for s in pd.date_range(FIRST, LAST - pd.Timedelta(days=length - 1)):
        e = s + pd.Timedelta(days=length - 1)
        if not ((EVENTS >= s - pd.Timedelta(days=1)) & (EVENTS <= e + pd.Timedelta(days=1))).any():
            starts.append(s)
    return starts


def spaced(starts: list[pd.Timestamp], length: int) -> set[pd.Timestamp]:
    """A subset with no two windows overlapping: the honest count of independent windows."""
    keep, last_end = set(), None
    for s in starts:
        if last_end is None or s > last_end:
            keep.add(s)
            last_end = s + pd.Timedelta(days=length - 1)
    return keep


def injected(rows: pd.DataFrame, start: pd.Timestamp, length: int, effect: float) -> pd.DataFrame:
    out = rows.copy()
    m = (out["Day"] >= start) & (out["Day"] <= start + pd.Timedelta(days=length - 1))
    out.loc[m, ["Gross sales", "Net sales"]] *= 1 + effect
    return out


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    placebo, inject = [], []
    rng = np.random.default_rng(20261105)
    for name in ("all", "uk"):
        rows = lift.report(HERE / "data" / f"uci_{name}.csv")
        for length in LENGTHS:
            starts = windows(length)
            independent = spaced([s for s in starts if s >= AFTER_CLOSURE], length)
            for s in starts:
                e = s + pd.Timedelta(days=length - 1)
                m = lift.measure(rows, s.date().isoformat(), e.date().isoformat())
                placebo.append({"series": name, "length": length, "start": s.date(), "january": s < AFTER_CLOSURE,
                                "independent": s in independent, **m})
            pool = [s for s in starts if s >= AFTER_CLOSURE]
            for effect in LIFTS:
                for s in rng.choice(np.array(pool, dtype="datetime64[ns]"), PER_CELL, replace=False):
                    s = pd.Timestamp(s)
                    e = s + pd.Timedelta(days=length - 1)
                    m = lift.measure(injected(rows, s, length, effect), s.date().isoformat(), e.date().isoformat())
                    inject.append({"series": name, "length": length, "lift_pct": 100 * effect, "start": s.date(), **m})
    p, i = pd.DataFrame(placebo), pd.DataFrame(inject)
    p.to_csv(RESULTS / "uci_placebo.csv", index=False)
    i.to_csv(RESULTS / "uci_injected.csv", index=False)
    summarise(p, i)


def summarise(p: pd.DataFrame, i: pd.DataFrame) -> None:
    pd.set_option("display.width", 200)
    def table(df: pd.DataFrame) -> pd.DataFrame:
        g = df.groupby(["series", "length"])
        return pd.DataFrame({
            "windows": g.size(),
            "real change %": 100 * g.verdict.apply(lambda v: (v == "real change").mean()),
            "  of which up %": 100 * g.apply(lambda d: ((d.verdict == "real change") & (d.estimate_pct > 0)).mean(), include_groups=False),
            "interval holds 0 %": 100 * g.apply(lambda d: ((d.interval_lo <= 0) & (d.interval_hi >= 0)).mean(), include_groups=False),
            "days in range %": 100 * g.days_in_range.sum() / g.days_with_data.sum(),
            "median |lift| %": g.estimate_pct.apply(lambda x: x.abs().median()),
            "median interval width, pts": g.apply(lambda d: (d.interval_hi - d.interval_lo).median(), include_groups=False),
        }).round(1)
    main_set = p[~p.january]
    print("PLACEBO, windows from 1 Feb 2011 (all starts):"); print(table(main_set).to_string())
    if main_set.independent.any():
        print("\nPLACEBO, non-overlapping windows only:"); print(table(main_set[main_set.independent]).to_string())
    print("\nPLACEBO, January windows (baseline includes the Christmas closure):"); print(table(p[p.january]).to_string())
    by_month = main_set.assign(month=lambda d: pd.to_datetime(d.start).dt.strftime("%m"))
    print("\nPLACEBO by start month, real change % (rows: series, window length):")
    print(by_month.groupby(["series", "length", "month"]).verdict.apply(lambda v: round(100 * (v == "real change").mean())).unstack().to_string())
    i = i.assign(detected=(i.verdict == "real change") & (i.estimate_pct > 0), error=i.estimate_pct - i.lift_pct,
                 covered=(i.interval_lo <= i.lift_pct) & (i.interval_hi >= i.lift_pct))
    g = i.groupby(["series", "length", "lift_pct"])
    inj = pd.DataFrame({
        "detected %": 100 * g.detected.mean(),
        "median estimate %": g.estimate_pct.median(),
        "median bias, pts": g.error.median(),
        "interval holds true lift %": 100 * g.covered.mean(),
    }).round(1)
    print(f"\nINJECTED LIFTS ({PER_CELL} random windows per cell, from 1 Feb 2011, away from events):"); print(inj.to_string())


if __name__ == "__main__":
    main()
