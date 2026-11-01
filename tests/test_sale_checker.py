"""The "Did my sale make money?" checker's glue (assets/checker/checker.py).

The break-even must be the Stats Compass app's exactly: each case below is one
of commerce's own tests (apps/web/src/promotions.test.ts, "break-even, beside
the lifts"), with the app's inputs (pence, so divided by 100 here) and its
exact sentences. The rest runs the glue on synthetic Shopify exports, as the
browser does.
"""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("stats_compass_core.workflows.sales")

spec = importlib.util.spec_from_file_location("checker", Path(__file__).parents[1] / "assets" / "checker" / "checker.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

CEILING = checker.CEILING


def lift(estimate, interval, pct):
    """A lift as the app holds it, in pence, given in pounds here."""
    return {"estimate": estimate / 100, "interval": (interval[0] / 100, interval[1] / 100), "pct": pct}


# Hosted's recorded SPRING10: revenue +23.4% (£1,840 more), contribution margin −10% (£210 less).
REVENUE = lift(184000, (62000, 301000), 23.4)
MARGIN = lift(-21000, (-58000, 14000), -10)


class TestBreakEvenParity:
    def test_needed_and_got(self):
        b = checker.break_even(REVENUE, MARGIN, "£")
        assert (b["needed"], b["got"]) == ("1.37×", "1.23×")
        assert checker.headline(b) == "Needed 1.37× normal sales · Got 1.23×"

    def test_the_sentence_in_money(self):
        assert checker.break_even(REVENUE, MARGIN, "£")["sentence"] == (
            "It earned less on each sale, so to match its usual margin it needed about £10,800 of sales, "
            "against about £7,860 you'd normally have had (likely between £6,690 and £9,080). It brought £9,700."
        )

    def test_as_much_or_more_on_each_sale(self):
        up = lift(10000, (4000, 16000), 10)
        assert checker.break_even(up, {**MARGIN, "estimate": 60.0, "pct": 20}, "£")["sentence"] == (
            "It earned as much or more on each sale, so about £917 of sales would have matched its usual margin, "
            "against about £1,000 you'd normally have had (likely between £940 and £1,060). It brought £1,100."
        )

    def test_the_discount_it_could_afford(self):
        assert checker.break_even(REVENUE, MARGIN, "£")["max_discount"] == (
            f"It gave away about 9% on average across its sales; at the extra sales it brought, anything above about 7% lost money. {CEILING}"
        )

    def test_the_demo_stores_summer40(self):
        # commerce packages/charts/test/fixtures/demo-output.json, SUMMER40.
        revenue = {"estimate": 914436.31348474 / 100, "interval": (390074.164648436 / 100, 1438798.462321044 / 100), "pct": 32.03879026574804}
        margin = {"estimate": -592083.4933810665 / 100, "interval": (0, 0), "pct": -44.17470394662186}
        b = checker.break_even(revenue, margin, "£")
        assert (b["needed"], b["got"]) == ("2.37×", "1.32×")
        assert b["max_discount"] == (
            f"It gave away about 34% on average across its sales; at the extra sales it brought, anything above about 23% lost money. {CEILING}"
        )

    def test_no_extra_full_price_sales(self):
        down = {**REVENUE, "estimate": -150.0, "pct": -15}
        assert checker.break_even(down, {**MARGIN, "estimate": -90.0, "pct": -30}, "£")["max_discount"] == (
            "It gave away about 7% on average across its sales; at the sales it brought, any discount at all lost money."
        )

    def test_about_what_it_could_afford(self):
        b = checker.break_even({**REVENUE, "estimate": 200.0, "pct": 20}, {**MARGIN, "estimate": -0.3, "pct": -0.1}, "£")
        assert b["max_discount"] == "It gave away about 7% on average across its sales, about what the extra sales it brought could afford."

    def test_no_discount_sentence_when_the_margin_rate_did_not_fall(self):
        b = checker.break_even({**REVENUE, "estimate": 100.0, "pct": 10}, {**MARGIN, "estimate": 60.0, "pct": 20}, "£")
        assert b["needed"] and b["max_discount"] is None

    def test_no_volume_could_have_paid(self):
        assert checker.break_even(REVENUE, {**MARGIN, "estimate": -2500.0, "pct": -119}, "£") == {
            "needed": None,
            "got": None,
            "sentence": "At the margin it sold at, no amount of extra sales would have paid for this promotion: each sale earned nothing.",
            "max_discount": f"It gave away about 30% on average across its sales; at the extra sales it brought, anything above about 11% lost money. {CEILING}",
        }

    def test_absent_without_both_lifts(self):
        assert checker.break_even(REVENUE, None, "£") is None
        assert checker.break_even(None, MARGIN, "£") is None
        assert checker.break_even({**REVENUE, "pct": None}, MARGIN, "£") is None
        assert checker.break_even(REVENUE, {**MARGIN, "pct": 0}, "£") is None


def shopify_export(lift_share: float = 0.8, discount: float = 0.3, days: int = 760, money_as_text: bool = False) -> str:
    """Shopify's Sales over time, by day: a store with a Black Friday sale at the end."""
    rng = np.random.default_rng(4)
    day = pd.date_range(end="2026-12-14", periods=days, freq="D")
    t = np.arange(days) / 365.25
    base = 1500 * 1.2**t * (1 + 0.12 * np.sin(2 * np.pi * day.dayofweek / 7)) * rng.lognormal(-0.01, 0.15, days)
    sale = (day >= "2026-11-27") & (day <= "2026-11-30")
    depth = np.where(sale, discount, 0.03)
    net = base * np.where(sale, 1 + lift_share, 1.0)
    gross = net / (1 - depth)
    frame = pd.DataFrame({
        "Day": day.strftime("%Y-%m-%d"), "Orders": np.round(net / 45).astype(int),
        "Gross sales": gross.round(2), "Discounts": (-(gross - net)).round(2), "Returns": 0.0,
        "Net sales": net.round(2), "Shipping charges": 0.0, "Taxes": (net * 0.2).round(2), "Total sales": (net * 1.2).round(2),
    })
    if money_as_text:
        for c in ("Gross sales", "Discounts", "Net sales"):
            frame[c] = frame[c].map(lambda v: f"£{v:,.2f}" if v >= 0 else f"-£{-v:,.2f}")
    return frame.to_csv(index=False)


class TestCheck:
    def test_a_black_friday_that_lifted_sales(self):
        out = checker.analyse(shopify_export(), "2026-11-27", "2026-11-30", 50, "£", "Black Friday")
        assert out["verdict"] == "real change"
        assert out["summary"].startswith("Black Friday, 27–30 November 2026: +")
        assert out["discount_depth"] == pytest.approx(0.3, abs=0.005)
        assert out["break_even_headline"].startswith("Needed ")
        assert out["break_even"]["sentence"].startswith("It earned less on each sale")
        assert len(out["chart"]) > 30 and any(p["in_promotion"] for p in out["chart"])
        assert out["after"].startswith("In the ") and " after, " in out["after"]

    def test_without_a_margin_there_is_no_break_even(self):
        out = checker.analyse(shopify_export(), "2026-11-27", "2026-11-30", None)
        assert out["break_even"] is None and out["verdict"] == "real change"

    def test_money_written_as_text_reads(self):
        out = checker.analyse(shopify_export(money_as_text=True), "2026-11-27", "2026-11-30", 50)
        assert out["verdict"] == "real change"
        assert any("Money written as text" in w for w in out["warnings"])

    def test_not_enough_history_says_how_far_back_to_export(self):
        out = checker.analyse(shopify_export(days=200), "2026-11-27", "2026-11-30", 50)
        assert out["verdict"] == "insufficient" and out["break_even"] is None
        assert out["summary"] == (
            "Not enough data yet: promotions need about 13 months of sales before them, so each can be compared "
            "with the same weeks a year earlier. Your report starts on 29 May 2026: export it from 27 October 2025 or earlier."
        )

    def test_not_a_daily_export(self):
        weekly = pd.DataFrame({"Week": ["2026-11-02"], "Gross sales": [1.0], "Discounts": [0.0], "Net sales": [1.0]}).to_csv(index=False)
        with pytest.raises(ValueError, match="isn't by day"):
            checker.analyse(weekly, "2026-11-27", "2026-11-30", 50)

    def test_not_the_report(self):
        with pytest.raises(ValueError, match="Sales over time"):
            checker.analyse("Product,Units\nMug,3\n", "2026-11-27", "2026-11-30", 50)

    def test_dates_outside_the_report(self):
        with pytest.raises(ValueError, match="no days inside the sale"):
            checker.analyse(shopify_export(), "2027-01-01", "2027-01-05", 50)
