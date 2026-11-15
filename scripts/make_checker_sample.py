"""The sale checker's sample file: a made-up store's daily "Total sales over time" export.

A store selling about £1,600 a day, growing about 15% a year, busier at weekends and in
the autumn, with two sales: a summer sale (14–20 July 2025, 15% off) and Black Friday
(28 November – 1 December 2025, 25% off). Nobody's real data. The seed is fixed, so
running it again gives the same file.

Run: python scripts/make_checker_sample.py  (writes assets/checker/sample-export.csv)
"""

import csv
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "assets" / "checker" / "sample-export.csv"
SALES = [("2025-07-14", "2025-07-20", 0.15, 0.30), ("2025-11-28", "2025-12-01", 0.25, 1.00)]


def main() -> None:
    rng = np.random.default_rng(2026)
    day = pd.date_range("2024-09-01", "2026-01-31", freq="D")
    n = len(day)
    years = np.arange(n) / 365.25
    weekly = 1 + 0.15 * np.isin(day.dayofweek, [4, 5, 6]) - 0.05 * np.isin(day.dayofweek, [1, 2])
    autumn = 1 + 0.2 * np.exp(-0.5 * ((day.dayofyear.to_numpy() - 320) / 30.0) ** 2)
    net = 1600 * 1.15**years * weekly * autumn * rng.lognormal(-0.02, 0.18, n)
    depth = np.clip(rng.normal(0.02, 0.01, n), 0, 0.08)
    for start, end, off, lift in SALES:
        on = (day >= start) & (day <= end)
        depth[on] = off
        net[on] *= 1 + lift
    gross = net / (1 - depth)
    orders = np.maximum(1, np.round(net / 38)).astype(int)
    taxes = net * 0.2
    frame = pd.DataFrame({
        "Day": day.strftime("%Y-%m-%d"), "Orders": orders, "Gross sales": gross.round(2),
        "Discounts": (-(gross - net)).round(2), "Sales reversals": 0, "Net sales": net.round(2),
        "Shipping charges": 0, "Duties": 0, "Additional fees": 0, "Taxes": taxes.round(2),
        "Total sales": (net + taxes).round(2),
    })
    frame.to_csv(OUT, index=False, quoting=csv.QUOTE_NONNUMERIC)
    print(f"{OUT.name}: {len(frame)} days, {frame['Day'].iloc[0]} to {frame['Day'].iloc[-1]}")


if __name__ == "__main__":
    main()
