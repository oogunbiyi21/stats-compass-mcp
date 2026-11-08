"""The "Did my sale make money?" checker's glue (assets/checker/checker.py).

The break-even must be the Stats Compass app's exactly: each case below is one
of commerce's own tests (apps/web/src/promotions.test.ts, "break-even, beside
the lifts"), with the app's inputs (pence, so divided by 100 here) and its
exact sentences. The rest runs the glue on synthetic Shopify exports, as the
browser does.
"""

import csv
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


def shopify_export(
    lift_share: float = 0.8, discount: float = 0.3, days: int = 760, money_as_text: bool = False,
    earlier_sale: tuple[str, str, float] | None = None,
) -> str:
    """Shopify's Total sales over time, by day, as exported (seen 2 Nov 2026): quoted ISO
    dates, plain numbers, negative discounts, "Sales reversals", and a last all-zero row
    for the day still under way. A store with a Black Friday sale near the end."""
    rng = np.random.default_rng(4)
    day = pd.date_range(end="2026-12-14", periods=days, freq="D")
    t = np.arange(days) / 365.25
    base = 1500 * 1.2**t * (1 + 0.12 * np.sin(2 * np.pi * day.dayofweek / 7)) * rng.lognormal(-0.01, 0.15, days)
    sale = (day >= "2026-11-27") & (day <= "2026-11-30")
    depth = np.where(sale, discount, 0.03)
    net = base * np.where(sale, 1 + lift_share, 1.0)
    if earlier_sale:
        start, end, deeper = earlier_sale
        earlier = (day >= start) & (day <= end)
        depth = np.where(earlier, deeper, depth)
        net = net * np.where(earlier, 1.5, 1.0)
    gross = net / (1 - depth)
    frame = pd.DataFrame({
        "Day": day.strftime("%Y-%m-%d"), "Orders": np.round(net / 45).astype(int),
        "Gross sales": gross.round(2), "Discounts": (-(gross - net)).round(2), "Sales reversals": 0,
        "Net sales": net.round(2), "Shipping charges": 0, "Duties": 0, "Additional fees": 0,
        "Taxes": (net * 0.2).round(2), "Total sales": (net * 1.2).round(2),
    })
    under_way = {c: 0 for c in frame.columns}
    under_way["Day"] = (day[-1] + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    frame = pd.concat([frame, pd.DataFrame([under_way])], ignore_index=True)
    if money_as_text:
        for c in ("Gross sales", "Discounts", "Net sales"):
            frame[c] = frame[c].map(lambda v: f"£{v:,.2f}" if v >= 0 else f"-£{-v:,.2f}")
    return frame.to_csv(index=False, quoting=csv.QUOTE_NONNUMERIC)


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

    def test_the_money_range_is_centred_on_what_was_expected(self):
        # Core 0.1.45's percentage range is the test inverted (wider above), so the money
        # range comes from core's amount range: what you'd normally have had, plus or minus.
        import re
        sentence = checker.analyse(shopify_export(), "2026-11-27", "2026-11-30", 50)["break_even"]["sentence"]
        expected, low, high = (float(x.replace(",", "")) for x in re.search(
            r"against about £([\d,]+) you'd normally have had \(likely between £([\d,]+) and £([\d,]+)\)", sentence).groups())
        assert (low + high) / 2 == pytest.approx(expected, rel=0.01)

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

    def test_a_monthly_export_is_refused_plainly(self):
        # The shape of Tunji's first real export (2 Nov 2026), by month.
        monthly = (
            '"Month","Orders","Gross sales","Discounts","Sales reversals","Net sales","Shipping charges","Duties","Additional fees","Taxes","Total sales"\n'
            '"2026-09-01",197,7648.72,0,0,7648.72,0,0,0,1529.78,9178.5\n'
            '"2026-10-01",104,4054.57,0,0,4054.57,0,0,0,810.93,4865.5\n'
            '"2026-11-01",0,0,0,0,0,0,0,0,0,0\n'
        )
        with pytest.raises(ValueError, match="^This export is by month; set it to Day and export again.$"):
            checker.analyse(monthly, "2026-11-27", "2026-11-30", 50)

    def test_the_day_under_way_is_left_out(self):
        rows = checker.read_export(shopify_export())
        assert rows["Day"].max() == pd.Timestamp("2026-12-14")  # the all-zero last row is gone
        rows = checker.read_export(shopify_export(), today="2026-12-14")
        assert rows["Day"].max() == pd.Timestamp("2026-12-13")  # and today's own row, still under way

    def test_discounts_given_as_negatives(self):
        rows = checker.read_export(shopify_export())
        assert (rows["Discounts"] <= 0).all()
        sale = rows[(rows["Day"] >= "2026-11-27") & (rows["Day"] <= "2026-11-30")]
        assert checker.discount_depth(sale) == pytest.approx(0.3, abs=0.005)

    def test_not_the_report(self):
        with pytest.raises(ValueError, match="Total sales over time"):
            checker.analyse("Product,Units\nMug,3\n", "2026-11-27", "2026-11-30", 50)

    def test_another_sale_in_the_weeks_before_is_not_the_usual_discount(self):
        # SUMMER40 then FLASH20 on Tunji's demo store: a deep 3-week sale ending 10 days
        # before a shallower one. The shallower one still earned less on each sale.
        csv_text = shopify_export(discount=0.12, earlier_sale=("2026-10-27", "2026-11-16", 0.36))
        out = checker.analyse(csv_text, "2026-11-27", "2026-11-30", 50)
        assert out["break_even"]["sentence"].startswith("It earned less on each sale")
        assert float(out["break_even"]["needed"].rstrip("×")) > 1

    def test_other_sales_are_left_out_of_the_comparison(self):
        # A deep sale ending 11 days before Black Friday inflates what Black Friday is
        # compared with. Added as another sale, it's left out, as the app leaves out
        # every promotion: the comparison comes back to the store without that sale.
        def expected(out):
            return sum(p["expected"] for p in out["chart"] if p["in_promotion"])
        earlier = {"start": "2026-10-27", "end": "2026-11-16"}
        csv_text = shopify_export(discount=0.12, earlier_sale=(earlier["start"], earlier["end"], 0.36))
        clean = expected(checker.analyse(shopify_export(discount=0.12), "2026-11-27", "2026-11-30", 50))
        alone = expected(checker.analyse(csv_text, "2026-11-27", "2026-11-30", 50))
        out = checker.analyse(csv_text, "2026-11-27", "2026-11-30", 50, "£", "Black Friday", others=[earlier])
        assert out["summary"].startswith("Black Friday, 27–30 November 2026: ")  # the chosen sale, not the other
        assert abs(alone / clean - 1) > 0.2
        assert abs(expected(out) / clean - 1) < 0.05

    def test_another_sale_overlapping_is_refused(self):
        with pytest.raises(ValueError, match="overlaps the sale you're checking"):
            checker.analyse(shopify_export(), "2026-11-27", "2026-11-30", 50, others=[{"start": "2026-11-29", "end": "2026-12-02"}])

    def test_other_sales_outside_the_report_change_nothing(self):
        alone = checker.analyse(shopify_export(), "2026-11-27", "2026-11-30", 50)
        out = checker.analyse(shopify_export(), "2026-11-27", "2026-11-30", 50, others=[{"start": "2020-01-01", "end": "2020-01-10"}])
        assert out["summary"] == alone["summary"]

    def test_a_found_sale_overlapping_the_one_checked_is_that_sale(self):
        bf = {"start": "2026-11-27", "end": "2026-11-30"}
        alone = checker.analyse(shopify_export(), "2026-11-27", "2026-11-30", 50)
        assert checker.analyse(shopify_export(), "2026-11-27", "2026-11-30", 50, others=[{**bf, "auto": True}])["summary"] == alone["summary"]
        with pytest.raises(ValueError, match="overlaps the sale you're checking"):
            checker.analyse(shopify_export(), "2026-11-27", "2026-11-30", 50, others=[{**bf, "auto": False}])

    def test_dates_outside_the_report(self):
        with pytest.raises(ValueError, match="no days inside the sale"):
            checker.analyse(shopify_export(), "2027-01-01", "2027-01-05", 50)


def daily_report(depth: np.ndarray, sales: list[tuple[str, str, float]], seed: int = 2) -> str:
    """A store's daily report with a given discount share each day, and sales at set shares."""
    rng = np.random.default_rng(seed)
    day = pd.date_range("2025-04-01", periods=len(depth), freq="D")
    net = 300 * (1 + 0.1 * np.sin(2 * np.pi * day.dayofweek / 7)) * rng.lognormal(0, 0.2, len(day))
    depth = depth.copy()
    for start, end, share in sales:
        depth[(day >= start) & (day <= end)] = share
    gross = net / (1 - depth)
    frame = pd.DataFrame({"Day": day.strftime("%Y-%m-%d"), "Gross sales": gross.round(2), "Discounts": (-(gross - net)).round(2), "Net sales": net.round(2)})
    return frame.to_csv(index=False, quoting=csv.QUOTE_NONNUMERIC)


class TestFindingOtherSales:
    def test_the_demo_stores_two_promotions(self):
        # Tunji's demo store (2 Nov 2026): no discounts on ordinary days, SUMMER40 for
        # 21 days with one shallower day (29 May, 22%), then FLASH20 12 days later.
        report = daily_report(np.zeros(565), [("2026-05-14", "2026-06-03", 0.36), ("2026-05-29", "2026-05-29", 0.22),
                                             ("2026-06-15", "2026-06-21", 0.12)])
        assert checker.detect(report) == [{"start": "2026-05-14", "end": "2026-06-03"}, {"start": "2026-06-15", "end": "2026-06-21"}]

    def test_last_years_black_friday(self):
        found = checker.detect(shopify_export(earlier_sale=("2025-11-28", "2025-12-01", 0.3)))
        assert found == [{"start": "2025-11-28", "end": "2025-12-01"}, {"start": "2026-11-27", "end": "2026-11-30"}]

    def test_nothing_in_a_store_whose_discounts_just_vary(self):
        rng = np.random.default_rng(7)
        for seed in range(5):
            assert checker.detect(daily_report(np.clip(rng.normal(0.08, 0.03, 565), 0, 0.6), [], seed)) == []

    def test_one_discounted_day_and_an_always_on_discount_are_not_sales(self):
        report = daily_report(np.zeros(565), [("2026-02-14", "2026-02-14", 0.5), ("2025-06-01", "2025-09-30", 0.2)])
        assert checker.detect(report) == []

    def test_a_report_that_cannot_be_read_finds_nothing(self):
        assert checker.detect("Product,Units\nMug,3\n") == []


class TestDidItMakeMoney:
    """The result's headline: break-even's multiple against the likely range of what it brought."""

    def test_the_three_calls(self):
        made = checker.profitability(1.17, 1.82, 1.40, 2.60, "")
        assert (made["call"], made["headline"]) == ("yes", "It made money.")
        assert made["sub"] == ("It needed about 1.17× your normal sales to break even and brought about 1.82×. "
                               "Even at the low end of the likely range (1.4×), it beat break-even.")
        lost = checker.profitability(2.29, 1.29, 1.10, 1.83, "")
        assert (lost["call"], lost["headline"]) == ("no", "It lost money.")
        assert lost["sub"].endswith("Even at the high end of the likely range (1.83×), it fell short.")
        unclear = checker.profitability(1.63, 1.62, 1.42, 1.89, "")
        assert (unclear["call"], unclear["headline"]) == ("unclear", "Can't tell: it could have gone either way.")
        assert unclear["sub"] == "It needed about 1.63× your normal sales to break even and brought about 1.62×, likely between 1.42× and 1.89×."

    def test_not_one_of_the_four_verdicts(self):
        for call in (checker.MADE_MONEY, checker.LOST_MONEY, checker.CANT_TELL):
            assert not any(word.lower() in call.lower() for word in ("real change", "expected", "noise", "not enough data"))

    def test_when_no_extra_sales_could_have_paid(self):
        out = checker.profitability(None, 1.3, 1.1, 1.5, "At the margin it sold at, no amount of extra sales would have paid for this promotion: each sale earned nothing.")
        assert out["call"] == "no" and out["sub"].startswith("At the margin it sold at")

    def test_under_one_times_says_it_as_break_even_does(self):
        sentence = "It earned as much or more on each sale, so about £917 of sales would have matched its usual margin, ..."
        assert checker.profitability(0.92, 1.1, 0.95, 1.3, sentence) == {"call": "yes", "headline": checker.MADE_MONEY, "sub": sentence}
        assert checker.profitability(0.92, 1.0, 0.85, 1.2, sentence)["call"] == "unclear"

    def test_unbounded_above(self):
        out = checker.profitability(2.0, 2.5, 1.5, None, "")
        assert out["call"] == "unclear" and out["sub"].endswith("likely above 1.5×.")

    @pytest.mark.parametrize("lift, call", [(0.9, "yes"), (0.45, "unclear"), (0.1, "no")])
    def test_on_a_black_friday(self, lift, call):
        # A 30% discount at a 50% margin needs about 1.63× normal sales.
        out = checker.analyse(shopify_export(lift_share=lift), "2026-11-27", "2026-11-30", 50)
        assert out["profit"]["call"] == call

    def test_no_headline_without_a_margin_or_enough_data(self):
        assert checker.analyse(shopify_export(), "2026-11-27", "2026-11-30", None)["profit"] is None
        assert checker.analyse(shopify_export(days=200), "2026-11-27", "2026-11-30", 50)["profit"] is None
