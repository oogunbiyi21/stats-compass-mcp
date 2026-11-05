# Validating the sale checker on real retail data

Results from 5 November 2026 for the "Did my sale make money?" checker (`assets/checker/checker.py`). The scripts are in this folder; the data isn't committed.

## What was run

- **The measurement.** `lift.py` makes the same `promotion_lift` call as the checker's `analyse`; `same_as_analyse` confirms the summaries match. It runs the checker's daily path: Fourier yearly pattern (4 harmonics) plus the weekly cycle, a 28-day baseline, and the 3 weeks after each listed sale left out of the fit. It returns the numbers the page doesn't show: the lift and its 90% interval in percent, and each day's 90% range.
- **The data.** UCI Online Retail II: a UK online gift-ware retailer, mostly selling to wholesalers, 1 Dec 2009 – 9 Dec 2011. Daily net sales are the sum of Quantity × Price, with cancellations counted. Days with no invoices are 0, as a Shopify export shows them. There are two series: all countries, and the United Kingdom only (about 85% of sales).
  > Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D. Licensed CC BY 4.0.
- **Not used: M5 (Walmart) and Rossmann.** Both come from Kaggle competitions, and their rules don't clearly allow using the data to validate a commercial product. A CC BY re-upload of M5 on Zenodo can't relicense it. So (c), known promotions, is **semi-synthetic**: known lifts injected into the real series, not marked real promotions.
- **The windows.** Starts from 4 Jan to 18 Nov 2011, which keeps the checker's 13-month floor and leaves 3 weeks of data after each window. Lengths are 4, 7, 14 and 21 days. A window and the day either side must avoid closures, bank holidays, the 29 Apr royal wedding and Black Friday weekend.
  - Windows starting before 1 Feb have the Christmas closure in their 28-day baseline, so they're reported separately.
  - Placebo uses every eligible start. Those windows overlap, so the non-overlapping subset is shown too, as the honest count of independent windows.

### What "real change" requires (core, `series/its.py`)

A lift is a real change only if it passes both tests:
- it's outside the expected band, the 95.4% point of the method's own past errors (`seasonal_band_z` 2);
- and p < 0.05.

So the **nominal false-alarm rate is about 4.6%**, split between rises and dips. The lift's interval and each day's range are both **90%** (`LEVEL`).

## Results

### (a, b) Placebo: windows with no sale

**As exported**, with closures left as zero days, which is what a merchant who lists nothing gets. Windows start from 1 Feb 2011.

| Series | Days | Windows (independent) | Real change | Interval holds 0 | Days in the 90% range | Median interval width, pts |
|---|---|---|---|---|---|---|
| all | 4 | 260 (67) | 0.0% | 96.2% | 92.0% | 137 |
| all | 7 | 248 (37) | 0.0% | 95.6% | 91.5% | 118 |
| all | 14 | 220 (17) | 0.0% | 97.3% | 90.0% | 108 |
| all | 21 | 192 (11) | 0.0% | 98.4% | 90.0% | 101 |
| UK | 4 | 260 (67) | 0.0% | 95.0% | 90.4% | 131 |
| UK | 7 | 248 (37) | 0.0% | 96.0% | 89.7% | 126 |
| UK | 14 | 220 (17) | 0.0% | 97.3% | 88.5% | 134 |
| UK | 21 | 192 (11) | 0.0% | 94.3% | 87.4% | 105 |

**With the closures listed as other sales**: Christmas and Easter in both years. This is a diagnostic of what drives the range's width, not advice for merchants (see What breaks, 2). Same windows.

| Series | Days | Real change, all windows (up) | Real change, independent | Interval holds 0 | Days in range | Interval width, pts |
|---|---|---|---|---|---|---|
| all | 4 | 5.8% (5.0%) | 4.5% of 67 | 89.6% | 91.4% | 79 |
| all | 7 | 4.4% (4.4%) | 2.7% of 37 | 92.3% | 90.8% | 71 |
| all | 14 | 9.1% (9.1%) | 5.9% of 17 | 86.8% | 90.2% | 61 |
| all | 21 | 10.9% (10.9%) | 9.1% of 11 | 87.0% | 90.0% | 60 |
| UK | 4 | 6.9% (6.2%) | 3.0% of 67 | 87.7% | 90.5% | 91 |
| UK | 7 | 4.4% (4.4%) | 5.4% of 37 | 89.5% | 89.6% | 78 |
| UK | 14 | 7.7% (7.7%) | 5.9% of 17 | 85.9% | 88.6% | 72 |
| UK | 21 | 10.9% (10.9%) | 9.1% of 11 | 85.4% | 87.9% | 72 |

Pooled over the non-overlapping windows: 12 real changes in 264, which is 4.5% against a nominal 4.6%. Six of the 12 start in September and four in August. The all-starts rates of 4–11% count September's overlapping windows many times. The UK and all-countries series overlap, so the effective count is lower than 264: call this about nominal, not exactly. As exported, the same pool has 0 in 264.

With the closures listed, the false alarms are in **September**. Share of windows called a real change, by start month:

| Days | Feb | Mar–Jun | Jul | Aug | Sep | Oct | Nov |
|---|---|---|---|---|---|---|---|
| 4 (all, UK) | 14%, 14% | 0–9% | 6%, 10% | 8%, 12% | **17%, 27%** | 0% | 0% |
| 7 | 0%, 4% | 0–5% | 0% | 0% | **33%, 33%** | 0% | 0% |
| 14 | 0% | 0% | 16%, 0% | 0% | **47%, 53%** | 0% | 20%, 20% |
| 21 | 0% | 0% | 6%, 0% | 12%, 12% | **60%, 67%** | 0% | – |

Why September: the retailer's autumn ramp was steeper in 2011 than in 2010.
- August to September: +49% in 2011 against +30% in 2010 (UK: +60% against +29%).
- September 2011 was up 20% on September 2010, after February to August were flat (+1%).

The checker reads a season that's stronger than last year's as a change in that window. It can't tell a sale from anything else that happened in the same weeks.

**January windows**, whose baseline includes the 11-day Christmas closure, 27 windows per cell:

| | 4 days | 7 days | 14 days | 21 days |
|---|---|---|---|---|
| As exported: real change (all, UK) | 56%, 52% | 56%, 63% | 56%, 63% | 56%, 59% |
| Closures listed (all, UK) | 59%, 67% | 74%, 67% | 70%, 70% | 67%, 67% |

Nearly all of these are upward.

### (c) Injected lifts (semi-synthetic)

Known lifts of +10%, +20%, +50% and +80% were injected by multiplying a window's real sales. There are 60 random windows per cell, from 1 Feb 2011, away from events. "Detected" means a real change with a positive estimate.

**As exported:**

| Days | Lift | Detected (all, UK) | Median estimate (all, UK) | Interval holds the true lift (all, UK) |
|---|---|---|---|---|
| 4 | +10% | 0%, 2% | +12%, +11% | 97%, 90% |
| 4 | +20% | 0%, 2% | +22%, +17% | 97%, 97% |
| 4 | +50% | 8%, 12% | +62%, +56% | 92%, 88% |
| 4 | +80% | 15%, 45% | +80%, +88% | 80%, 70% |
| 7 | +50% | 5%, 0% | +47%, +58% | 92%, 88% |
| 7 | +80% | 17%, 20% | +84%, +89% | 82%, 77% |
| 14 | +50% | 0%, 0% | +53%, +45% | 78%, 87% |
| 14 | +80% | 13%, 5% | +80%, +97% | 80%, 77% |
| 21 | +50% | 0%, 0% | +45%, +46% | 78%, 80% |
| 21 | +80% | 8%, 2% | +89%, +92% | 83%, 77% |

At +10% and +20%, nothing is detected at 7, 14 or 21 days. The interval holds the true lift 90–98% of the time there.

**Closures listed:**

| Days | Lift | Detected (all, UK) | Median estimate (all, UK) | Interval holds the true lift (all, UK) |
|---|---|---|---|---|
| 4 | +10% | 10%, 18% | +12%, +12% | 85%, 78% |
| 4 | +20% | 17%, 8% | +19%, +14% | 88%, 93% |
| 4 | +50% | 60%, 45% | +66%, +54% | 67%, 78% |
| 4 | +80% | 80%, 68% | +90%, +92% | 68%, 53% |
| 7 | +50% | 62%, 57% | +49%, +54% | 70%, 78% |
| 7 | +80% | 92%, 82% | +78%, +95% | 63%, 65% |
| 14 | +50% | 68%, 55% | +54%, +47% | 65%, 73% |
| 14 | +80% | 97%, 92% | +84%, +92% | 70%, 65% |
| 21 | +50% | 73%, 58% | +47%, +47% | 73%, 70% |
| 21 | +80% | 98%, 93% | +74%, +77% | 67%, 65% |

`results/uci_injected*.csv` has every cell.

### (d) What breaks

1. **A closure in the baseline.** In January, the 28 days before a window include the 11-day Christmas closure. As exported, 52–63% of placebo windows come out as a real change, nearly all upward. Listing the closure doesn't fix it (59–74%).
2. **Closures in the history widen every range.** As exported, the method's past errors include its misses around the closures. That makes the expected band about 100–137 points wide, so it almost never claims anything: 0% placebo false alarms, and +80% for a week detected 17–20% of the time.
   - The caution is a side effect of the closures, not robustness.
   - Listing the closures narrows it to 60–91 points. Power rises (+80% detected 68–98%), and so do false alarms: 4–11% over all starts, 4.5% over non-overlapping windows, mostly August and September.
   - Listing a closure isn't the remedy. An "other sale" also leaves out the 3 weeks after it, which is meant for the dip after a sale, and a closure has no such dip. That's probably why January doesn't improve: windows starting 4–24 Jan sit inside the listed closure's 3 weeks after, so the baseline reaches back to before Christmas. The open question for core is how runs of zero-sales days should be treated: as missing days, or left out of the fit without the 3 weeks after. The found-sales suggestions can't find closures either, since closures carry no discounts.
3. **The percent range is too narrow for large lifts.** It should hold the true lift 90% of the time. At +80% it holds it 70–83% of the time as exported, and 53–70% with the closures listed. At +50%, 78–92% and 65–78%.
   - **Why:** its half-width comes from errors measured at no lift, but on the percent scale a window's error grows with (1 + lift).
   - **Confirmed:** with the half-width scaled by (1 + estimate), coverage of the true lift is 88–90% at every lift size with closures listed, and about 97% as exported, matching that run's placebo.
   - **The money range is already right.** The checker's "likely between £… and £…" is the expected total × the percent range, which cancels the factor. Only core's percent range on the page ("likely between +52% and +112%") understates.
   - **The fix** is small, for after approval: scale the percent half-width by (1 + lift) in core.
4. **A season unlike last year's.** With one earlier year to learn from, a stronger or earlier ramp than last year's reads as a change in the window. Here that's September 2011.
5. **Lumpy wholesale orders.** The biggest days are about 4× the median. Large cancellations make 4 negative days (the largest −£22k on 29 Apr 2010). Saturdays are always 0. The weekly cycle absorbs the Saturdays; the lumpiness is in the wide ranges above.
6. **Not tested:** stockouts (no stock data) and real promotions (none are marked).

This retailer is lumpier than a typical Shopify store selling to consumers: fewer, larger orders, and wholesale customers. The sizes above are for this series; the mechanisms apply to any store.

## After the fixes: core 0.1.45 (sales layer)

Core 0.1.45 (stats-compass-core #8) does three things in the sales layer only:
- shows the percentage range as the test inverted, (e − q)/(1 + q) to (e + q)/(1 − q);
- treats runs of 3 or more zero days as closures, given as missing days;
- adds result notes on closures, a sale starting within 14 days of one, and one earlier year.

Same windows and seed, as exported (`VALIDATION_TAG=_0.1.45`, results/uci_*_0.1.45.csv):

| | 0.1.44 | 0.1.45 |
|---|---|---|
| January placebo, called a real change | 52–63% | 26–30% |
| …windows starting from 12 Jan | 43% | 2.5% |
| Feb–Nov placebo, real change (all starts) | 0% | 0–4% |
| …non-overlapping windows, pooled | 0 of 264 | 0.8% of 264 |
| Placebo range holds 0 | 94–98% | 91–96% |
| Daily range covers the day | 87–92% | 86–91% |
| +80% lift detected | 2–45% (pooled 16%) | 48–78% (pooled 66%) |
| +50% lift detected | 0–12% (pooled 3%) | 17–48% (pooled 35%) |
| Range holds the true lift, +80% | 70–83% (pooled 78%) | 90–93% (pooled 91%) |
| Range holds the true lift, +50% | 78–92% (pooled 85%) | 85–97% (pooled 91%) |

The January flags left are windows containing the first trading week after the Christmas closure: 68k on 11 Jan 2011 against about 25k normally, and 72k on 7 Jan 2010. That's orders held over from the closure. The note for a sale starting within 14 days of a closure says so.

## Rerunning

```
python -I validation/fetch_uci.py    # downloads, checks the sha256, writes data/uci_*.csv
python -I validation/run_uci.py      # as exported: results/uci_placebo.csv, results/uci_injected.csv
python -I validation/closures.py     # closures listed: results/uci_*_closures_listed.csv
```

These need stats-compass-core 0.1.44 (the checker's wheel) and openpyxl. Window starts are every eligible day, and injected windows are drawn with seed 20261105, so a rerun reproduces these numbers.
