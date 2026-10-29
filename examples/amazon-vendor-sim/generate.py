"""A simulated Amazon Vendor brand: three years of weekly sell-out, sell-in and promotions.

Everything here is invented: the brand (Kestrelmoor Home), its products, the
ASINs (B0SIM…) and every figure. It is built to test the Stats Compass sales
tools on data shaped like Amazon Vendor Central's Retail Analytics "Sales"
report, viewed by ASIN, one week per download, stacked with a week column.

Writes, into ./data:
- sell_out.csv      Week ending (Saturday), ASIN, Product title, Brand,
                    Ordered Revenue, Ordered Units, Shipped Revenue,
                    Shipped COGS, Shipped Units, Customer Returns
- sell_in.csv       What Amazon bought, from the brand's ERP: Week ending,
                    ASIN, Vendor SKU, PO number, Units shipped, Value at cost (£)
- promo_calendar.csv ASIN (or "all"), Event, Start, End, Mechanic, Funding (£)
- product_master.csv ASIN, Vendor SKU, Product title, Category, Range,
                    Launched (week ending), Status
- truth.json        Every planted effect, to check the tools against.

Run: python generate.py   (deterministic: seed 20261029)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20261029
BRAND = "Kestrelmoor Home"
OUT = Path(__file__).parent / "data"
# Amazon weeks run Sunday to Saturday; a row is labelled by its Saturday.
WEEKS = pd.date_range(end="2026-10-24", periods=156, freq="W-SAT")

rng = np.random.default_rng(SEED)


# =============================================================================
# The range
# =============================================================================

# Category: (products, seasonal bumps as (centre month, width in weeks, size)).
CATEGORIES = {
    "Cookware": (
        ["Non-stick frying pan 24cm", "Non-stick frying pan 28cm", "Stainless saucepan set (3)",
         "Cast iron casserole 4.5L", "Wok 30cm", "Griddle pan", "Milk pan 14cm", "Stock pot 8L",
         "Sauté pan with lid", "Pan protectors (6)", "Egg poacher pan"],
        [(11.8, 5, 0.40), (7.2, 6, -0.15)],
    ),
    "Bakeware": (
        ["Loaf tin 2lb", "Springform cake tin 23cm", "Muffin tray 12-cup", "Baking sheet set (2)",
         "Silicone baking mat", "Roasting tin with rack", "Cooling rack", "Pie dish ceramic"],
        [(12.0, 4, 0.55), (3.8, 3, 0.12), (7.5, 6, -0.20)],
    ),
    "Food Storage": (
        ["Glass storage set (10)", "Lunch box bento", "Freezer bags 50", "Airtight canisters (3)",
         "Spice jars (12)", "Cereal dispenser", "Bread bin", "Produce saver set (4)", "Vacuum food containers (5)"],
        [(1.2, 4, 0.30), (9.2, 3, 0.18), (12.0, 4, 0.08)],
    ),
    "Kitchen Utensils": (
        ["Silicone utensil set (6)", "Chef's knife 20cm", "Knife block set", "Garlic press",
         "Digital kitchen scale", "Measuring cups & spoons", "Tongs set (2)", "Peeler set (3)",
         "Grater box", "Rolling pin beech"],
        [(12.0, 4, 0.28), (6.5, 4, 0.10)],
    ),
    "Cleaning": (
        ["Dish brush set", "Microfibre cloths (12)", "Washing-up bowl", "Drying rack 2-tier",
         "Sink caddy", "Bottle brush set"],
        [(3.8, 5, 0.32), (12.3, 3, -0.10)],
    ),
}
NEW_RANGE = (
    "Air Fryer Accessories",
    ["Air fryer silicone liners (2)", "Air fryer paper liners 100", "Air fryer rack set",
     "Air fryer cake barrel", "Air fryer oil sprayer", "Air fryer tongs"],
    [(12.0, 4, 0.30), (1.3, 4, 0.20)],
)
LAUNCH = WEEKS[156 - 39]  # about 9 months before the end
DELIST_AFTER = pd.Timestamp("2025-05-17")  # mid year 2
DELISTED_TITLE = "Egg poacher pan"
GAP_TITLE = "Cereal dispenser"
GAP_WEEKS = [pd.Timestamp("2025-06-14"), pd.Timestamp("2025-06-21")]
FLOP_TITLES = ["Air fryer cake barrel", "Vacuum food containers (5)"]


@dataclass
class Product:
    asin: str
    sku: str
    title: str
    category: str
    range: str
    price: float  # Amazon's retail price, £
    cogs_ratio: float  # what Amazon pays the brand, as a share of retail
    base_units: float  # weekly ordered units at the start, before season
    growth: float  # a year
    return_rate: float
    noise: float
    bumps: list
    launched: pd.Timestamp | None = None
    delisted: pd.Timestamp | None = None


def build_range() -> list[Product]:
    products = []
    n = 0
    all_ranges = [(c, titles, bumps, "Core") for c, (titles, bumps) in CATEGORIES.items()]
    all_ranges.append((NEW_RANGE[0], NEW_RANGE[1], NEW_RANGE[2], "Air Fryer 2026"))
    # A skewed popularity mix: a few heroes, a long tail (lognormal ranks).
    popularity = np.sort(rng.lognormal(mean=3.6, sigma=1.1, size=sum(len(t) for _, t, _, _ in all_ranges)))[::-1]
    order = rng.permutation(len(popularity))
    for category, titles, bumps, range_name in all_ranges:
        for title in titles:
            asin = f"B0SIM{n:05d}"
            base = float(popularity[order[n]])
            products.append(Product(
                asin=asin,
                sku=f"KM-{category[:3].upper()}-{n:03d}",
                title=f"{BRAND} {title}",
                category=category,
                range=range_name,
                price=float(np.round(rng.uniform(7, 65), 2)),
                cogs_ratio=float(np.round(rng.uniform(0.55, 0.65), 3)),
                base_units=base,
                growth=float(rng.normal(0.06, 0.08)),
                return_rate=float(rng.uniform(0.02, 0.05)),
                noise=float(np.clip(0.10 + 0.25 / np.sqrt(base), 0.10, 0.30)),
                bumps=bumps,
                launched=LAUNCH if range_name != "Core" else None,
                delisted=DELIST_AFTER if title == DELISTED_TITLE else None,
            ))
            n += 1
    # Make the heroes deliberate: the top three by volume are a pan, a storage set and a utensil set.
    for title, units in (("Non-stick frying pan 28cm", 900.0), ("Glass storage set (10)", 650.0), ("Silicone utensil set (6)", 520.0)):
        next(p for p in products if p.title.endswith(title)).base_units = units
    return products


def season(bumps, weeks: pd.DatetimeIndex) -> np.ndarray:
    """1 plus Gaussian bumps around each centre month, wrapping round the year."""
    # The week's middle day, as a fraction of the year in months.
    mid = weeks - pd.Timedelta(days=3)
    month = (mid.dayofyear.to_numpy() - 1) / 365.25 * 12 + 0.5
    out = np.ones(len(weeks))
    for centre, width_weeks, size in bumps:
        d = np.abs(month - centre)
        d = np.minimum(d, 12 - d) * 52 / 12  # in weeks
        out += size * np.exp(-0.5 * (d / width_weeks) ** 2)
    return out


# =============================================================================
# Promotions: the calendar, and what each actually did (the truth)
# =============================================================================


def promo_calendar(products: list[Product]) -> tuple[pd.DataFrame, list[dict]]:
    by_title = {p.title.replace(f"{BRAND} ", ""): p for p in products}
    rows, truth = [], []

    def add(asin, event, start, end, mechanic, funding, effects, note):
        rows.append({"ASIN": asin, "Event": event, "Start": start, "End": end, "Mechanic": mechanic,
                     "Funding (£)": funding})
        truth.append({"asin": asin, "event": event, "start": start, "end": end, "effects": effects, "note": note})

    tentpole = {}
    for year, prime, black_friday in (
        (2024, ("2024-07-16", "2024-07-17"), ("2024-11-21", "2024-12-02")),
        (2025, ("2025-07-08", "2025-07-11"), ("2025-11-20", "2025-12-01")),
        (2026, ("2026-07-07", "2026-07-10"), None),
    ):
        tentpole[f"Prime Day {year}"] = prime
        if black_friday:
            tentpole[f"Black Friday & Cyber Monday {year}"] = black_friday
    tentpole["Black Friday & Cyber Monday 2023"] = ("2023-11-17", "2023-11-27")
    for event, (start, end) in sorted(tentpole.items(), key=lambda kv: kv[1][0]):
        prime = event.startswith("Prime")
        add("all", event, start, end, "Deal of the Day, 20% off selected lines" if prime else "Up to 30% off selected lines",
            8000 if prime else 12000,
            # The lift by product: heroes respond strongly, others less; set per product below.
            effects="per product: units ×(1.25–2.2), heroes highest; Bakeware and Cookware strongest in Black Friday",
            note="real lift for most lines")
    # Three single-product deals, each planted with a known effect.
    hero_pan = by_title["Non-stick frying pan 28cm"]
    tubs = by_title["Lunch box bento"]
    cloths = by_title["Microfibre cloths (12)"]
    add(hero_pan.asin, "Best Deal: frying pan", "2025-09-14", "2025-09-27", "Best Deal, 15% off", 1500,
        effects={"weeks": ["2025-09-20", "2025-09-27"], "units_multiplier": 1.7},
        note="REAL and profitable: +70% units for two weeks, small discount")
    add(tubs.asin, "Lightning deal: bento box", "2026-03-01", "2026-03-07", "Lightning deal, 30% off", 2000,
        effects={"weeks": ["2026-03-07"], "units_multiplier": 1.04},
        note="JUST DISCOUNTING: +4% units, a deep discount and funding for nothing")
    add(cloths.asin, "Lightning deal: microfibre cloths", "2026-04-05", "2026-04-18", "Lightning deal, 25% off", 1200,
        effects={"weeks": ["2026-04-11", "2026-04-18"], "units_multiplier": 1.9,
                 "after": {"2026-04-25": 0.55, "2026-05-02": 0.70, "2026-05-09": 0.85}},
        note="PULL-FORWARD: +90% for two weeks, then a dip of 45%, 30%, 15% as customers had stocked up")
    calendar = pd.DataFrame(rows)
    return calendar, truth


def tentpole_multiplier(p: Product, event: str, hero_rank: int) -> float:
    """How a product sells on each day of Prime Day or Black Friday (its planted lift).

    A multiple of a normal day: heroes about ×5, the long tail about ×2.
    Cleaning lines barely move. A week's lift is this, spread over the share
    of the week's days the deal covers.
    """
    base = 2.0 + 3.0 * np.exp(-hero_rank / 8)
    if event.startswith("Black") and p.category in ("Bakeware", "Cookware"):
        base += 0.5
    if p.category == "Cleaning":
        base = 1.0 + (base - 1.0) * 0.25
    return float(base)


# =============================================================================
# Sell-out
# =============================================================================


def simulate_sell_out(products: list[Product], calendar: pd.DataFrame, truth: list[dict]):
    ranks = {p.asin: r for r, p in enumerate(sorted(products, key=lambda q: -q.base_units))}
    years = (WEEKS - WEEKS[0]).days.to_numpy() / 365.25
    rows = []
    planted_tentpole = []
    for p in products:
        mult = np.ones(len(WEEKS))
        discount = np.zeros(len(WEEKS))
        # Tent-pole events: the weeks they touch (Sunday to Saturday).
        for _, ev in calendar[calendar.ASIN == "all"].iterrows():
            start, end = pd.Timestamp(ev.Start), pd.Timestamp(ev.End)
            hit = (WEEKS >= start) & (WEEKS - pd.Timedelta(days=6) <= end)
            m = tentpole_multiplier(p, ev.Event, ranks[p.asin])
            week_lifts = {}
            for i in np.flatnonzero(hit):
                overlap = min(end, WEEKS[i]) - max(start, WEEKS[i] - pd.Timedelta(days=6))
                days_in_week = overlap.days + 1
                lift = 1 + (m - 1) * days_in_week / 7
                mult[i] *= lift
                week_lifts[WEEKS[i].date().isoformat()] = round(lift, 2)
                # The deal price applies on deal days only: the week's average discount.
                discount[i] = max(discount[i], (0.2 if ev.Event.startswith("Prime") else 0.25) * days_in_week / 7)
            if ranks[p.asin] < 3:
                planted_tentpole.append({"asin": p.asin, "event": ev.Event, "deal_day_multiplier": round(m, 2),
                                         "week_multipliers": week_lifts})
        # Single-product deals.
        for t in truth:
            if t["asin"] != p.asin or not isinstance(t["effects"], dict):
                continue
            depth = {"Best Deal": 0.15}.get(t["event"].split(":")[0], 0.30 if "bento" in t["event"] else 0.25)
            for w in t["effects"]["weeks"]:
                i = WEEKS.get_loc(pd.Timestamp(w))
                mult[i] *= t["effects"]["units_multiplier"]
                discount[i] = max(discount[i], depth)
            for w, f in t["effects"].get("after", {}).items():
                mult[WEEKS.get_loc(pd.Timestamp(w))] *= f
        level = p.base_units * (1 + p.growth) ** years * season(p.bumps, WEEKS) * mult
        # Launch: nothing before, a ramp over 8 weeks. Flops never take off at Amazon.
        alive = np.ones(len(WEEKS), dtype=bool)
        if p.launched is not None:
            since = ((WEEKS - p.launched).days.to_numpy() / 7)
            alive = since >= 0
            ramp = np.clip((since + 1) / 8, 0, 1)
            if any(p.title.endswith(f) for f in FLOP_TITLES):
                level = np.full(len(WEEKS), 140.0) * season(p.bumps, WEEKS) * ramp * 0.2  # a fifth of the plan
            else:
                level = level * ramp
        if any(p.title.endswith(f) for f in FLOP_TITLES) and p.launched is None:
            # An existing line Amazon over-ordered for Q4 2025: sell-out sags from autumn 2025.
            sag = np.where(WEEKS >= pd.Timestamp("2025-09-06"), 0.55, 1.0)
            level = level * sag
        if p.delisted is not None:
            weeks_left = ((p.delisted - WEEKS).days.to_numpy() / 7)
            rundown = np.clip(weeks_left / 8, 0.15, 1.0)
            level = level * rundown
            alive &= WEEKS <= p.delisted
        noise = rng.lognormal(-0.5 * p.noise**2, p.noise, len(WEEKS))
        ordered = rng.poisson(np.maximum(level * noise, 0.0))
        # Most orders ship the same week, a fifth the week after.
        shipped = np.round(0.8 * ordered + 0.2 * np.concatenate([[ordered[0]], ordered[:-1]])).astype(int)
        price_rise = np.where(WEEKS >= pd.Timestamp("2025-01-04"), 1.03, 1.0) * np.where(WEEKS >= pd.Timestamp("2026-01-03"), 1.03, 1.0)
        price = p.price * price_rise
        cost = price * p.cogs_ratio
        returns = rng.binomial(np.concatenate([[0, 0], shipped[:-2]]), p.return_rate)
        for i, w in enumerate(WEEKS):
            if not alive[i]:
                continue
            if p.title.endswith(GAP_TITLE) and w in GAP_WEEKS:
                continue  # two weekly downloads missing for this ASIN
            sell_price = price[i] * (1 - discount[i])
            rows.append({
                "Week ending": w.date().isoformat(),
                "ASIN": p.asin,
                "Product title": p.title,
                "Brand": BRAND,
                "Ordered Revenue": round(ordered[i] * sell_price, 2),
                "Ordered Units": int(ordered[i]),
                "Shipped Revenue": round(shipped[i] * sell_price, 2),
                "Shipped COGS": round(shipped[i] * cost[i], 2),
                "Shipped Units": int(shipped[i]),
                "Customer Returns": int(returns[i]),
            })
    return pd.DataFrame(rows), planted_tentpole


# =============================================================================
# Sell-in: Amazon's purchase orders, shipped by the brand
# =============================================================================


def simulate_sell_in(products: list[Product], sell_out: pd.DataFrame) -> pd.DataFrame:
    """Amazon reorders to cover about 6 weeks, 2 weeks ahead, in case packs, lumpily.

    For the flops, Amazon's forecast stays far above what sells for months: the
    build-up a sell-through check should catch.
    """
    rows = []
    po = 4_500_000
    for p in products:
        s = sell_out[sell_out.ASIN == p.asin].set_index("Week ending")["Shipped Units"]
        s.index = pd.to_datetime(s.index)
        s = s.reindex(WEEKS).fillna(0)
        flop = any(p.title.endswith(f) for f in FLOP_TITLES)
        case = 12 if p.price < 20 else 6
        # Start in steady state: about four weeks' cover already at Amazon.
        inventory, pipeline = 4.0 * float(s.iloc[0]), {}
        for i, w in enumerate(WEEKS):
            inventory += pipeline.pop(i, 0)
            inventory = max(inventory - s.iloc[i], 0)
            if p.launched is not None and w < p.launched - pd.Timedelta(weeks=3):
                continue
            if p.delisted is not None and w > p.delisted - pd.Timedelta(weeks=6):
                continue
            recent = s.iloc[max(0, i - 4): i + 1].mean() if i else s.iloc[0]
            forecast = recent
            if p.launched is not None and w < p.launched + pd.Timedelta(weeks=20):
                forecast = max(recent, 0.6 * p.base_units)  # the launch forecast
            target = 6 * forecast
            on_order = sum(pipeline.values())
            need = target - inventory - on_order
            build = _flop_build(p, w)
            if build:
                # Amazon keeps buying against a plan the shelf never meets, whatever it holds.
                need = build * rng.uniform(0.8, 1.2)
            if need > case and rng.random() < 0.7:  # Amazon skips some weeks: lumpy orders
                qty = int(np.ceil(need * rng.uniform(0.9, 1.3) / case) * case)
                pipeline[i + 2] = pipeline.get(i + 2, 0) + qty
                po += 1
                ship_week = WEEKS[min(i + 1, len(WEEKS) - 1)]
                rows.append({
                    "Week ending": ship_week.date().isoformat(),
                    "ASIN": p.asin,
                    "Vendor SKU": p.sku,
                    "PO number": f"SIM{po}",
                    "Units shipped": qty,
                    "Value at cost (£)": round(qty * p.price * p.cogs_ratio * (1.03 if ship_week >= pd.Timestamp("2025-01-04") else 1.0), 2),
                })
    return pd.DataFrame(rows).sort_values(["Week ending", "ASIN"]).reset_index(drop=True)


def _flop_build(p: Product, week: pd.Timestamp) -> float:
    """Weekly units Amazon buys for a flop during its build-up, else 0.

    The new air fryer cake barrel: bought at a launch plan of 140 a week for 20
    weeks from 3 weeks before launch, while it sells about a fifth of that.
    The vacuum containers: Amazon's Q4 2025 build, buying twice the usual run
    from August to November, while sell-out sags 45% from September.
    """
    if not any(p.title.endswith(f) for f in FLOP_TITLES):
        return 0.0
    if p.launched is not None:
        start = p.launched - pd.Timedelta(weeks=3)
        return 140.0 if start <= week < start + pd.Timedelta(weeks=20) else 0.0
    return 2.0 * p.base_units if pd.Timestamp("2025-08-02") <= week <= pd.Timestamp("2025-11-29") else 0.0


def main() -> None:
    OUT.mkdir(exist_ok=True)
    products = build_range()
    calendar, truth = promo_calendar(products)
    sell_out, tentpole = simulate_sell_out(products, calendar, truth)
    sell_in = simulate_sell_in(products, sell_out)
    master = pd.DataFrame([{
        "ASIN": p.asin, "Vendor SKU": p.sku, "Product title": p.title, "Category": p.category,
        "Range": p.range, "Launched (week ending)": p.launched.date().isoformat() if p.launched is not None else "",
        "Status": "Delisted" if p.delisted is not None else "Live",
    } for p in products])
    sell_out.to_csv(OUT / "sell_out.csv", index=False)
    sell_in.to_csv(OUT / "sell_in.csv", index=False)
    calendar.to_csv(OUT / "promo_calendar.csv", index=False)
    master.to_csv(OUT / "product_master.csv", index=False)
    by_title = {p.title.replace(f"{BRAND} ", ""): p for p in products}
    (OUT / "truth.json").write_text(json.dumps({
        "seed": SEED,
        "weeks": [WEEKS[0].date().isoformat(), WEEKS[-1].date().isoformat()],
        "promotions": truth,
        "tentpole_lifts_for_heroes": tentpole,
        "launch": {"range": NEW_RANGE[0], "first_week": LAUNCH.date().isoformat(),
                   "asins": [p.asin for p in products if p.launched is not None]},
        "delisted": {"asin": by_title[DELISTED_TITLE].asin, "last_week": DELIST_AFTER.date().isoformat(),
                     "note": "sales run down over the 8 weeks before"},
        "gap": {"asin": by_title[GAP_TITLE].asin, "missing_weeks": [w.date().isoformat() for w in GAP_WEEKS]},
        "sell_in_flops": [{"asin": by_title[t].asin, "title": t} for t in FLOP_TITLES],
        "heroes": [p.asin for p in sorted(products, key=lambda q: -q.base_units)[:3]],
        "products": [{"asin": p.asin, "title": p.title, "category": p.category, "base_units": round(p.base_units, 1),
                      "growth": round(p.growth, 3), "cogs_ratio": p.cogs_ratio, "return_rate": round(p.return_rate, 3)}
                     for p in products],
    }, indent=1))
    print(f"{len(products)} ASINs; sell-out {len(sell_out)} rows; sell-in {len(sell_in)} rows; "
          f"{len(calendar)} promotions; weeks {WEEKS[0].date()} to {WEEKS[-1].date()}")


if __name__ == "__main__":
    main()
