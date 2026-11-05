"""Diagnostic: the same placebo and injected lifts with the store's closures listed as other sales.

It tests what drives the range's width (the method's misses around closures, in its past
errors) through an input, without changing the method. It isn't advice for merchants:
an "other sale" also leaves out the 3 weeks after it, which a closure doesn't need.
Run after run_uci.py: python -I validation/closures.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

import lift
import run_uci

CLOSURES = [("2009-12-24", "2010-01-03"), ("2010-04-02", "2010-04-05"), ("2010-12-24", "2011-01-03"), ("2011-04-22", "2011-04-25")]
OTHERS = [{"start": a, "end": b} for a, b in CLOSURES]


def main() -> None:
    placebo, inject = [], []
    rng = np.random.default_rng(20261105)
    for name in ("all", "uk"):
        rows = lift.report(run_uci.HERE / "data" / f"uci_{name}.csv")
        for length in run_uci.LENGTHS:
            starts = run_uci.windows(length)
            independent = run_uci.spaced([s for s in starts if s >= run_uci.AFTER_CLOSURE], length)
            for s in starts:
                e = s + pd.Timedelta(days=length - 1)
                m = lift.measure(rows, s.date().isoformat(), e.date().isoformat(), OTHERS)
                placebo.append({"series": name, "length": length, "start": s.date(), "january": s < run_uci.AFTER_CLOSURE,
                                "independent": s in independent, **m})
            pool = [s for s in starts if s >= run_uci.AFTER_CLOSURE]
            for effect in run_uci.LIFTS:
                for s in rng.choice(np.array(pool, dtype="datetime64[ns]"), run_uci.PER_CELL, replace=False):
                    s = pd.Timestamp(s)
                    e = s + pd.Timedelta(days=length - 1)
                    m = lift.measure(run_uci.injected(rows, s, length, effect), s.date().isoformat(), e.date().isoformat(), OTHERS)
                    inject.append({"series": name, "length": length, "lift_pct": 100 * effect, "start": s.date(), **m})
    p, i = pd.DataFrame(placebo), pd.DataFrame(inject)
    p.to_csv(run_uci.RESULTS / "uci_placebo_closures_listed.csv", index=False)
    i.to_csv(run_uci.RESULTS / "uci_injected_closures_listed.csv", index=False)
    run_uci.summarise(p, i)


if __name__ == "__main__":
    main()
