"""Did my sale make money? The checker's glue, run in the visitor's browser (Pyodide).

Reads Shopify's "Total sales over time" report, exported by day, then:
- measures the sale with stats-compass-core's promotion_lift: daily net sales
  against what was expected without it, with the app's settings, its range,
  verdict and the 3 weeks after;
- works out what it needed to break even and what it brought, with the
  Stats Compass app's own formula: commerce's @commerce/ui breakEven, ported
  below line for line (tests/test_sale_checker.py holds it to the app's figures).

The app measures margin from cost data. Here the merchant types their usual
margin, and the margin during the sale follows from the discount Shopify
reports: product cost per pound of gross sales is taken as unchanged, so a
deeper discount earns less on each sale. Nothing leaves the browser.
"""

from __future__ import annotations

import io
import math
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from stats_compass_core.sales import wording
from stats_compass_core.sales.schema import to_numbers
from stats_compass_core.state import DataFrameState
from stats_compass_core.workflows.sales import PromotionLiftInput, promotion_lift

MINUS = "−"
CEILING = "A smaller discount would usually have brought fewer extra sales, so this is a ceiling, not a recommendation."
DATE_COLUMNS = ("day", "date")
# The app's floor for promotions (commerce SECTION_MIN_HISTORY.promotions):
# each is compared with the same weeks a year earlier.
MIN_MONTHS = 13
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")
NEEDED = ("net sales", "gross sales", "discounts")


# -- reading the export -------------------------------------------------------------


def read_export(csv_text: str, today: str | None = None) -> pd.DataFrame:
    """The report's rows, one per complete day, with numeric Gross sales, Discounts and Net sales.

    Shopify's export (seen 2 Nov 2026): quoted ISO dates, plain numbers,
    discounts as negatives, "Sales reversals" (once "Returns"), and a last row
    for the period still under way, all zeros until it has sales. Rows from
    ``today`` on, and trailing rows with no orders and no sales, are dropped:
    they're incomplete, not days with no sales.
    """
    df = pd.read_csv(io.StringIO(csv_text.lstrip("\ufeff")))
    by_lower = {c.strip().lower(): c for c in df.columns}
    if not any(k in by_lower for k in DATE_COLUMNS):
        period = next((k for k in ("hour", "week", "month", "quarter", "year") if k in by_lower), None)
        if period:
            raise ValueError(f"This export is by {period}; set it to Day and export again.")
    date_col = next((by_lower[k] for k in DATE_COLUMNS if k in by_lower), None)
    missing = [k for k in NEEDED if k not in by_lower]
    if date_col is None or missing:
        wanted = ", ".join(["Day", "Gross sales", "Discounts", "Net sales"])
        raise ValueError(f"This doesn't look like Shopify's Total sales over time report: it needs the columns {wanted}.")
    out = pd.DataFrame({"Day": pd.to_datetime(df[date_col], errors="coerce")})
    if out["Day"].isna().any():
        raise ValueError("Some days in the report couldn't be read.")
    parsed = []
    for key, name in (("gross sales", "Gross sales"), ("discounts", "Discounts"), ("net sales", "Net sales")):
        values, example = to_numbers(df[by_lower[key]])
        if example:
            parsed.append(wording.money_parsed(name, example))
        out[name] = values
    if "orders" in by_lower:
        out["Orders"] = pd.to_numeric(df[by_lower["orders"]], errors="coerce").fillna(0)
    out = out.groupby("Day", as_index=False).sum(min_count=1).sort_values("Day").reset_index(drop=True)
    if today:
        out = out[out["Day"] < pd.Timestamp(today)]
    # The period still under way: trailing rows with nothing in them.
    empty = (out["Net sales"].fillna(0) == 0) & (out["Gross sales"].fillna(0) == 0) & (out.get("Orders", 0) == 0)
    while len(out) and empty.iloc[len(out) - 1]:
        out, empty = out.iloc[:-1], empty.iloc[:-1]
    out = out.drop(columns=["Orders"], errors="ignore")
    out.attrs["notes"] = parsed[:1]
    return out


def _day(d: pd.Timestamp) -> str:
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def discount_depth(rows: pd.DataFrame) -> float:
    """Discounts as a share of gross sales: Shopify reports discounts as negatives."""
    gross = float(rows["Gross sales"].sum())
    return abs(float(rows["Discounts"].sum())) / gross if gross > 0 else 0.0


def usual_discount(rows: pd.DataFrame) -> float:
    """The usual day's discount: the median day's depth, so another sale in these weeks doesn't count as usual."""
    days = rows[rows["Gross sales"] > 0]
    return float((days["Discounts"].abs() / days["Gross sales"]).median()) if len(days) else 0.0


# -- the app's break-even (commerce packages/ui/src/break-even.ts), ported ---------------


def _round_half_up(x: float, digits: int = 0) -> float:
    q = Decimal(1).scaleb(-digits)
    return float(Decimal(repr(x)).quantize(q, rounding=ROUND_HALF_UP))


def money_about(amount: float, symbol: str) -> str:
    """The app's money(…, {about: true}): three significant figures, no pence."""
    step = 1.0 if amount == 0 else max(1.0, 10 ** (math.floor(math.log10(abs(amount))) - 2))
    rounded = _round_half_up(amount / step) * step
    text = f"{abs(rounded):,.0f}"
    return f"{MINUS if rounded < 0 else ''}{symbol}{text}"


def percent(value: float) -> str:
    """The app's percent(): a whole percentage, rounding halves away from zero."""
    r = _round_half_up(value)
    return f"{MINUS if r < 0 else ''}{abs(r):.0f}%"


def multiple(value: float) -> str:
    """The app's multiple(): "1.37×", "2.0×", at least one decimal and at most two."""
    r = _round_half_up(value, 2)
    text = f"{abs(r):.2f}"
    if text.endswith("0"):
        text = text[:-1]
    return f"{MINUS if r < 0 else ''}{text}×"


def break_even(revenue: dict | None, margin: dict | None, symbol: str) -> dict | None:
    """``breakEven`` from the app: the same arithmetic, in the same order."""
    if not revenue or not margin or not revenue.get("pct") or not margin.get("pct"):
        return None
    r0 = revenue["estimate"] / (revenue["pct"] / 100)
    c0 = margin["estimate"] / (margin["pct"] / 100)
    if not (r0 > 0) or not (c0 > 0):
        return None
    r1 = r0 + revenue["estimate"]
    c1 = c0 + margin["estimate"]
    max_discount = _discount_sentence(c0 / r0, c1 / r1, r1 / r0) if r1 > 0 else None
    if c1 <= 0 or r1 <= 0:
        return {
            "needed": None,
            "got": None,
            "sentence": "At the margin it sold at, no amount of extra sales would have paid for this promotion: each sale earned nothing.",
            "max_discount": max_discount,
        }
    about = lambda x: money_about(max(0.0, x), symbol)  # noqa: E731
    needed = about((c0 * r1) / c1)
    expected = about(r0)
    lo, hi = revenue["interval"]
    rng = f"likely between {about(r1 - hi)} and {about(r1 - lo)}"
    if c1 / r1 < c0 / r0:
        sentence = (
            f"It earned less on each sale, so to match its usual margin it needed about {needed} of sales, "
            f"against about {expected} you'd normally have had ({rng}). It brought {about(r1)}."
        )
    else:
        sentence = (
            f"It earned as much or more on each sale, so about {needed} of sales would have matched its usual "
            f"margin, against about {expected} you'd normally have had ({rng}). It brought {about(r1)}."
        )
    return {"needed": multiple((c0 / r0) / (c1 / r1)), "got": multiple(r1 / r0), "sentence": sentence, "max_discount": max_discount}


def _discount_sentence(m0: float, m1: float, brought: float) -> str | None:
    if not (m1 < m0) or not (m1 < 1):
        return None
    given = (m0 - m1) / (1 - m1)
    k = brought / (1 - given)
    gave = f"It gave away about {percent(given * 100)} on average across its sales"
    if k <= 1:
        return f"{gave}; at the sales it brought, any discount at all lost money."
    affordable = m0 * (1 - 1 / k)
    if percent(affordable * 100) == percent(given * 100):
        return f"{gave}, about what the extra sales it brought could afford."
    return f"{gave}; at the extra sales it brought, anything above about {percent(affordable * 100)} lost money. {CEILING}"


def headline(b: dict) -> str | None:
    """``breakEvenHeadline``: "Needed 2.37× normal sales · Got 1.32×"."""
    return f"Needed {b['needed']} normal sales · Got {b['got']}" if b.get("needed") and b.get("got") else None


# -- the check ------------------------------------------------------------------------------


def analyse(
    csv_text: str, start: str, end: str, margin_pct: float | None, symbol: str = "£",
    name: str | None = None, today: str | None = None,
) -> dict:
    """Everything the page shows, as plain data. ``today``, the visitor's date: its row and later are incomplete."""
    rows = read_export(csv_text, today)
    if rows.empty:
        raise ValueError("The report has no complete days with sales in it.")
    first, last = pd.Timestamp(start), pd.Timestamp(end)
    if last < first:
        raise ValueError("The sale ends before it starts.")
    in_sale = rows[(rows["Day"] >= first) & (rows["Day"] <= last)]
    if in_sale.empty:
        raise ValueError("The report has no days inside the sale. Check the dates, or export a longer period.")
    label = name or "The sale"
    starts = rows["Day"].min()
    needed_from = first - pd.DateOffset(months=MIN_MONTHS)
    if starts > needed_from:
        # The app's own words for its floor, for one report rather than a store.
        return {
            "verdict": "insufficient", "label": "Not enough data", "name": label, "chart": [], "warnings": rows.attrs.get("notes", []),
            "summary": (
                f"Not enough data yet: promotions need about {MIN_MONTHS} months of sales before them, so each can be "
                f"compared with the same weeks a year earlier. Your report starts on {_day(starts)}: export it from "
                f"{_day(needed_from)} or earlier."
            ),
            "after": None, "amount": None, "discount_depth": discount_depth(in_sale), "break_even": None, "break_even_headline": None,
        }
    state = DataFrameState()
    state.set_dataframe(rows, name="sales", operation="upload")
    lift = promotion_lift(state, PromotionLiftInput(
        dataframe_name="sales", date_column="Day", value_column="Net sales", currency=symbol,
        include_series=True, windows=[{"name": label, "start": first.date(), "end": last.date()}],
    ))
    row = lift.rows[0]
    out = {
        "verdict": row.verdict,
        "label": row.label,
        "summary": row.summary,
        "after": row.after_summary,
        "warnings": rows.attrs.get("notes", []) + row.warnings + lift.notes,
        "chart": [p.model_dump() for p in row.series or []],
        "name": label,
        "amount": row.amount,
        "discount_depth": discount_depth(in_sale),
        "break_even": None,
        "break_even_headline": None,
    }
    if row.verdict == "insufficient" or margin_pct is None:
        return out
    # The revenue lift as the app's breakEven reads it. Its range, in money, is
    # the percentage range applied to the expected total (one basis with the verdict).
    r0 = row.expected_total
    revenue = {
        "estimate": row.estimate,
        "pct": row.estimate_pct,
        "interval": (r0 * row.interval_pct[0] / 100, r0 * row.interval_pct[1] / 100) if row.interval_pct else row.interval,
    }
    # The margin lift, from the typed margin and the discount: cost per pound
    # of gross sales unchanged, so the margin on net sales during the sale is
    # 1 − (1 − d₀)(1 − m₀)/(1 − d₁), with d₀ the usual discount over the 8 weeks
    # before, d₁ the sale's.
    usual = rows[(rows["Day"] < first) & (rows["Day"] >= first - pd.Timedelta(days=56))]
    d0, d1 = usual_discount(usual), out["discount_depth"]
    m0 = margin_pct / 100
    m1 = 1 - (1 - d0) * (1 - m0) / (1 - d1) if d1 < 1 else -math.inf
    c0, c1 = r0 * m0, row.observed_total * m1
    margin = {"estimate": c1 - c0, "pct": 100 * (c1 - c0) / c0 if c0 else None}
    b = break_even(revenue, margin, symbol)
    out["break_even"] = b
    out["break_even_headline"] = headline(b) if b else None
    return out
