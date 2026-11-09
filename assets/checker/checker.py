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
import re
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


# -- other sales, found from the discounts ---------------------------------------------
# The app finds promotions from the discount codes on orders (commerce
# packages/metrics/src/promotion-windows.ts). The export has only daily totals,
# so here a sale is a run of days whose discount share stands well above the
# store's usual day. The merge gap and the always-on span are the app's.

MERGE_GAP_DAYS = 2  # runs fewer than 2 ordinary days apart are one sale (the app's)
ALWAYS_ON_SPAN_DAYS = 56  # a run longer than 8 weeks is an always-on discount, not a sale (the app's)
MIN_SALE_DAYS = 2  # one discounted day is more often one large order than a sale
ABOVE_USUAL = 0.05  # at least 5 points of discount share above the usual day
ROBUST_SIGMAS = 3.0  # and beyond the day-to-day spread of a store whose discounts vary
QUIET_DAY = 0.25  # a day under a quarter of the usual day's gross sales can't tell


def find_sales(rows: pd.DataFrame) -> list[dict]:
    """Runs of days with a discount share well above the store's usual day, as {start, end} (ISO dates)."""
    days = rows[rows["Gross sales"] > 0]
    if days.empty:
        return []
    share = days["Discounts"].abs() / days["Gross sales"]
    usual = float(share.median())
    spread = 1.4826 * float((share - usual).abs().median())
    above = share > usual + max(ABOVE_USUAL, ROBUST_SIGMAS * spread)
    above &= days["Gross sales"] >= QUIET_DAY * float(days["Gross sales"].median())
    found, run = [], None
    for day in days.loc[above, "Day"]:
        if run and (day - run[1]).days - 1 < MERGE_GAP_DAYS:
            run[1], run[2] = day, run[2] + 1
        else:
            run = [day, day, 1]
            found.append(run)
    return [
        {"start": a.date().isoformat(), "end": b.date().isoformat()}
        for a, b, n in found
        if n >= MIN_SALE_DAYS and (b - a).days + 1 <= ALWAYS_ON_SPAN_DAYS
    ]


def detect(csv_text: str, today: str | None = None) -> list[dict]:
    """The other sales to suggest when a report is chosen; none if it can't be read (the check says why)."""
    try:
        return find_sales(read_export(csv_text, today))
    except ValueError:
        return []


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


def break_even(revenue: dict | None, margin: dict | None, symbol: str, ads: float = 0.0) -> dict | None:
    """``breakEven`` from the app: the same arithmetic, in the same order.

    ``ads``, the merchant's extra ad spend for the sale, is a fixed cost: the sale's
    margin must cover the usual margin plus the ads, so it needs (c₀ + ads) ÷ m₁ of
    sales. With none, every figure is the app's.
    """
    if not revenue or not margin or not revenue.get("pct") or not margin.get("pct"):
        return None
    r0 = revenue["estimate"] / (revenue["pct"] / 100)
    c0 = margin["estimate"] / (margin["pct"] / 100)
    if not (r0 > 0) or not (c0 > 0):
        return None
    r1 = r0 + revenue["estimate"]
    c1 = c0 + margin["estimate"]
    max_discount = _discount_sentence(c0 / r0, c1 / r1, r1 / r0, ads / r0) if r1 > 0 else None
    if c1 <= 0 or r1 <= 0:
        return {
            "needed": None,
            "got": None,
            "sentence": "At the margin it sold at, no amount of extra sales would have paid for this promotion: each sale earned nothing.",
            "max_discount": max_discount,
        }
    about = lambda x: money_about(max(0.0, x), symbol)  # noqa: E731
    needed = about((c0 + ads) * r1 / c1)
    expected = about(r0)
    lo, hi = revenue["interval"]
    rng = f"likely between {about(r1 - hi)} and {about(r1 - lo)}"
    paid = f" and pay for {ad_spend(ads, symbol)} of ads" if ads else ""
    paid_for = f" and paid for {ad_spend(ads, symbol)} of ads" if ads else ""
    if c1 / r1 < c0 / r0:
        sentence = (
            f"It earned less on each sale, so to match its usual margin{paid} it needed about {needed} of sales, "
            f"against about {expected} you'd normally have had ({rng}). It brought {about(r1)}."
        )
    else:
        sentence = (
            f"It earned as much or more on each sale, so about {needed} of sales would have matched its usual "
            f"margin{paid_for}, against about {expected} you'd normally have had ({rng}). It brought {about(r1)}."
        )
    ratio = (c0 / r0) / (c1 / r1) if not ads else (c0 + ads) * r1 / (c1 * r0)
    return {"needed": multiple(ratio), "got": multiple(r1 / r0), "sentence": sentence, "max_discount": max_discount}


def ad_spend(ads: float, symbol: str) -> str:
    """The ad spend as the merchant typed it, to the pound: "£500", "£1,250"."""
    return f"{symbol}{ads:,.0f}"


def _discount(m0: float, m1: float, brought: float, ads_share: float = 0.0) -> tuple[float, float | None] | None:
    """The average discount given, and the most the extra sales could afford (None: no discount at all).

    ``ads_share``, the ad spend over what you'd normally have had, also has to come
    out of the margin: at a full-price-equivalent volume k times normal, the discount
    that breaks even is m₀(1 − 1/k) − ads_share/k (the app's, with no ads).
    """
    if not (m1 < m0) or not (m1 < 1):
        return None
    given = (m0 - m1) / (1 - m1)
    k = brought / (1 - given)
    affordable = m0 * (1 - 1 / k) - ads_share / k
    return given, (affordable if k > 1 and affordable > 0 else None)


def _discount_sentence(m0: float, m1: float, brought: float, ads_share: float = 0.0) -> str | None:
    """The app's sentence (``maxDiscount``), with the ads taken off when there are any."""
    numbers = _discount(m0, m1, brought, ads_share)
    if numbers is None:
        return None
    given, affordable = numbers
    gave = f"It gave away about {percent(given * 100)} on average across its sales"
    after = ", after the ads," if ads_share else ","
    if affordable is None:
        return f"{gave}; at the sales it brought{after} any discount at all lost money."
    if percent(affordable * 100) == percent(given * 100):
        return f"{gave}, about what the extra sales it brought could afford{' after the ads' if ads_share else ''}."
    return f"{gave}; at the extra sales it brought{after} anything above about {percent(affordable * 100)} lost money. {CEILING}"


def discount_line(m0: float, m1: float, brought: float, ads_share: float = 0.0, label: str = "Discount") -> str | None:
    """The page's line: "Discount: you gave about 12% off on average; at the extra sales it
    brought, anything above about 26% lost money. This is a ceiling, not a recommendation.".
    ``label``: "Discount", "Price cut" or "Discount and price cut"."""
    numbers = _discount(m0, m1, brought, ads_share)
    if numbers is None:
        return None
    given, affordable = numbers
    if percent(given * 100) == "0%":
        return None  # no discount to speak of: the note asks for a price cut instead
    gave = f"{label}: you gave about {percent(given * 100)} off on average"
    after = ", after the ads," if ads_share else ","
    if affordable is None:
        noun = "price cut" if label == "Price cut" else "discount"
        return f"{gave}; at the sales it brought{after} any {noun} at all lost money."
    if percent(affordable * 100) == percent(given * 100):
        return f"{gave}, about what the extra sales it brought could afford{' after the ads' if ads_share else ''}."
    return (f"{gave}; at the extra sales it brought{after} anything above about {percent(affordable * 100)} lost money. "
            "This is a ceiling, not a recommendation.")


def added_line(value: str | None, amount: str | None, verdict: str, interval_pct: tuple | None) -> str | None:
    """"+82%: £2,126 more than expected (likely +40% to +160%)."; no range beside an
    expected verdict, as in the app."""
    if not value or not amount:
        return None
    likely = ""
    if verdict != "expected" and interval_pct:
        low, high = interval_pct
        likely = f" (likely above {wording.signed_pct(low)})" if high is None else (
            f" (likely {wording.signed_pct(low)} to {wording.signed_pct(high)})")
    return f"{value}: {amount}{likely}."


def after_line(after: str | None) -> str | None:
    """"After the sale (3 weeks): sales were about as expected." from core's "In the 3 weeks after, …".

    Since core 0.1.46 the weeks after stop at the next promotion: "In the 11 days before
    the next promotion, …", or "The next promotion started 5 days later, so …".
    """
    if not after:
        return None
    m = re.match(r"In the (.+?) before the next promotion, (.*)$", after)
    if m:
        return f"After the sale ({m.group(1)}, until the next sale): {m.group(2)}"
    m = re.match(r"The next promotion (started .*)$", after)
    if m:
        return f"After the sale: the next sale {m.group(1)}"
    m = re.match(r"In the (.+?) after, (.*)$", after)
    return f"After the sale ({m.group(1)}): {m.group(2)}" if m else after


def headline(b: dict) -> str | None:
    """``breakEvenHeadline``: "Needed 2.37× normal sales · Got 1.32×"."""
    return f"Needed {b['needed']} normal sales · Got {b['got']}" if b.get("needed") and b.get("got") else None


# -- did it make money? ---------------------------------------------------------------
# The result's headline: break-even's multiple against the likely range of what the
# sale brought. Got's range is what you sold over the range of what you'd normally
# have had, the same range as break-even's sentence. A call on profit, so it doesn't
# use the four verdict words.

# A sale whose discount share is under 2 points above the usual day's shows no discount:
# it may have been run by lowering prices, which Shopify's discounts don't record.
NO_DISCOUNT_FOUND = 0.02
NO_DISCOUNT_NOTE = (
    "We didn't find discounts for these dates. If you cut prices instead, enter the average cut so break-even counts it."
)

MADE_MONEY = "It made money."
LOST_MONEY = "It lost money."
CANT_TELL = "Can't tell: it could have gone either way."


def profitability(
    needed: float | None, got: float, got_low: float, got_high: float | None, sentence: str, ads: str | None = None,
    covers: str = "the discount",
) -> dict:
    """Made money, lost money or can't tell, and the line under it.

    The line says what break-even covers: the discount, and the ad spend when it's
    given ("£500"), otherwise that ad spend isn't included.

    One line under it: what it needed, what it brought and the likely range of that,
    which is why the call can be made (or not). ``needed`` is None when no amount of
    extra sales could have paid (each sale earned nothing), and break-even's sentence
    says so; ``got_high`` is None when the range is unbounded above.
    """
    if needed is None:
        return {"call": "no", "headline": LOST_MONEY, "sub": sentence}
    cover = f"to cover {covers} and {ads} of ads," if ads else f"to cover {covers} (ad spend not included)"
    since = ", as it earned as much or more on each sale," if needed <= 1 else ""
    likely = f"likely above {multiple(got_low)}" if got_high is None else f"likely {multiple(got_low)} to {multiple(got_high)}"
    sub = f"It needed about {multiple(needed)} your normal sales {cover}{since} and brought about {multiple(got)} ({likely})."
    if got_low >= needed:
        return {"call": "yes", "headline": MADE_MONEY, "sub": sub}
    if got_high is not None and got_high < needed:
        return {"call": "no", "headline": LOST_MONEY, "sub": sub}
    return {"call": "unclear", "headline": CANT_TELL, "sub": sub}


# -- the check ------------------------------------------------------------------------------


def other_sales(others: list[dict] | None, first: pd.Timestamp, last: pd.Timestamp, rows: pd.DataFrame) -> list[dict]:
    """The other sales, as windows: left out of the fitted history, as the app does.

    Each is one the merchant added or one found from the discounts (``auto``). A found one
    overlapping the sale being checked is that sale, so it's dropped; an added one is refused.
    One with no days in the report is left out.
    """
    windows = []
    for i, other in enumerate(others or [], start=1):
        a, b = pd.Timestamp(other["start"]), pd.Timestamp(other["end"])
        if b < a:
            raise ValueError("One of the other sales ends before it starts.")
        if a <= last and b >= first:
            if other.get("auto"):
                continue
            raise ValueError("One of the other sales overlaps the sale you're checking. Remove it, or check it on its own.")
        if a <= rows["Day"].max() and b >= rows["Day"].min():
            windows.append({"name": f"Other sale {i}", "start": a.date(), "end": b.date()})
    return windows


def analyse(
    csv_text: str, start: str, end: str, margin_pct: float | None, symbol: str = "£",
    name: str | None = None, today: str | None = None, others: list[dict] | None = None, ads: float | None = None,
    cut: float | None = None,
) -> dict:
    """Everything the page shows, as plain data.

    ``today``, the visitor's date: its row and later are incomplete. ``others``, any
    other sales in the period ({start, end}): measured with them left out, as the app does.
    ``ads``, extra ad spend for the sale: a cost break-even has to cover. ``cut``, the
    average price cut in percent, for a sale run by lowering prices, which Shopify's
    discounts don't show.
    """
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
    extra = other_sales(others, first, last, rows)
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
            "profit": None, "span": wording.span(first.date(), last.date()), "added": None, "after_line": None, "discount_line": None,
        }
    state = DataFrameState()
    state.set_dataframe(rows, name="sales", operation="upload")
    lift = promotion_lift(state, PromotionLiftInput(
        dataframe_name="sales", date_column="Day", value_column="Net sales", currency=symbol,
        include_series=True, windows=[{"name": label, "start": first.date(), "end": last.date()}, *extra],
    ))
    # Each window gets a row (others are left out of each one's fit); only the chosen sale is shown.
    row = next(r for r in lift.rows if (r.start, r.end) == (first.date().isoformat(), last.date().isoformat()))
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
        "profit": None,
        # The page's lines, each fact once: the dates go in the result's title.
        "span": wording.span(first.date(), last.date()),
        "added": added_line(row.value, row.amount, row.verdict, row.interval_pct),
        "after_line": after_line(row.after_summary),
        "discount_line": None,
    }
    if row.verdict == "insufficient" or margin_pct is None:
        return out
    # The revenue lift as the app's breakEven reads it, with core's range in money:
    # the test's half-width applied to the expected total (core 0.1.45), which holds
    # at any lift. The percentage range is the test inverted, so it isn't used here.
    r0 = row.expected_total
    revenue = {"estimate": row.estimate, "pct": row.estimate_pct, "interval": row.interval}
    # The margin lift, from the typed margin and the discount: cost per pound
    # of gross sales unchanged, so the margin on net sales during the sale is
    # 1 − (1 − d₀)(1 − m₀)/(1 − d₁), with d₀ the usual discount over the 8 weeks
    # before, d₁ the sale's.
    usual = rows[(rows["Day"] < first) & (rows["Day"] >= first - pd.Timedelta(days=56))]
    for w in extra:
        usual = usual[(usual["Day"] < pd.Timestamp(w["start"])) | (usual["Day"] > pd.Timestamp(w["end"]))]
    d0, d1 = usual_discount(usual), out["discount_depth"]
    # A price cut is off normal prices, and discount codes come off the cut price, so
    # the sale's depth against normal prices is 1 − (1 − cut)(1 − d₁).
    price_cut = min(max(float(cut or 0) / 100, 0.0), 0.95)
    codes = d1 - d0 >= NO_DISCOUNT_FOUND
    depth = 1 - (1 - price_cut) * (1 - d1)
    covers, label = (("the discount and price cut", "Discount and price cut") if codes and price_cut
                     else ("the price cut", "Price cut") if price_cut else ("the discount", "Discount"))
    if not codes and not price_cut:
        out["warnings"] = out["warnings"] + [NO_DISCOUNT_NOTE]
    m0 = margin_pct / 100
    m1 = 1 - (1 - d0) * (1 - m0) / (1 - depth) if depth < 1 else -math.inf
    c0, c1 = r0 * m0, row.observed_total * m1
    margin = {"estimate": c1 - c0, "pct": 100 * (c1 - c0) / c0 if c0 else None}
    spend = max(0.0, float(ads or 0))
    b = break_even(revenue, margin, symbol, spend)
    if b and r0 > 0:
        out["discount_line"] = discount_line(m0, m1, row.observed_total / r0, spend / r0, label)
    out["break_even"] = b
    out["break_even_headline"] = headline(b) if b else None
    if b and row.interval_pct and r0 > 0:
        # The sales needed for the sale's margin to cover the usual margin and the ads,
        # as a multiple of what you'd normally have had: (m₀·E + ads) ÷ (m₁·E).
        low, high = row.interval_pct
        out["profit"] = profitability(
            (m0 * r0 + spend) / (m1 * r0) if m1 > 0 else None, row.observed_total / r0,
            1 + low / 100, None if high is None else 1 + high / 100, b["sentence"],
            ad_spend(spend, symbol) if spend else None, covers,
        )
    return out


def sale_discount(csv_text: str, start: str, end: str, today: str | None = None) -> dict:
    """Whether the report shows a discount for these dates, for the page's price-cut hint.

    "Found" when the sale's discount share is NO_DISCOUNT_FOUND or more above the usual
    day's; a report that can't be read says found, so the page doesn't nag before the
    check explains what's wrong.
    """
    try:
        rows = read_export(csv_text, today)
    except ValueError:
        return {"found": True}
    first, last = pd.Timestamp(start), pd.Timestamp(end)
    in_sale = rows[(rows["Day"] >= first) & (rows["Day"] <= last)]
    usual = rows[(rows["Day"] < first) & (rows["Day"] >= first - pd.Timedelta(days=56))]
    if in_sale.empty:
        return {"found": True}
    return {"found": discount_depth(in_sale) - usual_discount(usual) >= NO_DISCOUNT_FOUND}
