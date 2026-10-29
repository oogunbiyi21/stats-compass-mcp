# Simulated Amazon Vendor data, and the sales tools on it

A made-up kitchenware brand, **Kestrelmoor Home**, sells 50 products to Amazon as a vendor. Its data is shaped like Amazon Vendor Central's Retail Analytics "Sales" report (view by ASIN), one week per row. It's for testing and demos of the Stats Compass sales tools (`sales_verdict`, `sales_seasonality`, `promotion_lift`, core 0.1.42). The brand, ASINs (`B0SIM…`) and every figure are invented.

```
python generate.py    # writes data/ (seed 20261029, deterministic)
python run_tools.py   # runs the three tools, writes results.json (about 8 seconds)
```

## The data

| File | What | Rows |
|---|---|---|
| `data/sell_out.csv` | Week ending (Saturday), ASIN, Product title, Brand, Ordered Revenue, Ordered Units, Shipped Revenue, Shipped COGS, Shipped Units, Customer Returns. GBP, 156 weeks (4 Nov 2023 to 24 Oct 2026) | 7,021 |
| `data/sell_in.csv` | What Amazon bought, from the brand's ERP: Week ending, ASIN, Vendor SKU, PO number, Units shipped, Value at cost (£) | 3,944 |
| `data/promo_calendar.csv` | ASIN (or `all`), Event, Start, End, Mechanic, Funding (£) | 9 |
| `data/product_master.csv` | ASIN, Vendor SKU, Product title, Category, Range, Launched, Status: Amazon's report has no category, so this is joined on | 50 |
| `data/truth.json` | Every planted effect, and each product's settings | |

**What's built in:**
- **Range and mix.** Five categories (Cookware, Bakeware, Food Storage, Kitchen Utensils, Cleaning) and a skewed mix: 3 hero ASINs carry 42% of sales, and the smallest 25 carry 7%.
- **Seasonality by category.** A Q4 peak for cookware and bakeware, January and back-to-school for storage, spring for cleaning, and a summer lull.
- **Growth and prices.** Growth of about 6% a year varies by product, and a 3% price rise lands each January.
- **Costs and returns.** Shipped COGS runs 55–65% of shipped revenue by product (62% overall), and returns 2–5% (2.9% overall).
- **Shipping.** A fifth of each week's orders ship the following week.
- **Promotions.**
  - Prime Day each July and Black Friday & Cyber Monday each November, on all lines. Heroes sell about 5× on deal days, the tail about 2×, and cleaning barely moves.
  - A **Best Deal** on the hero frying pan (September 2025): real, with a small discount and £1,500 of funding.
  - A **Lightning deal** on the bento box (March 2026): just discounting, about +4%.
  - A **Lightning deal** on microfibre cloths (April 2026): +90% for two weeks, then a pull-forward dip of 45%, 30% and 15% in ordered units over the next three weeks.
- **Launch.** A new Air Fryer Accessories range of 6 ASINs, launched in the week ending 31 January 2026 (38 weeks before the end).
- **Delisting.** One SKU (Egg poacher pan) runs down over 8 weeks and is delisted after 17 May 2025.
- **A gap.** Two weekly rows are missing for one ASIN (Cereal dispenser, June 2025).
- **Sell-in.** Amazon reorders to about 6 weeks' cover, 2 weeks ahead, in case packs, skipping some weeks. Two flops:
  - the new air fryer cake barrel: Amazon bought 2,178 against 986 sold;
  - the vacuum food containers: Amazon built them up for Q4 2025, buying 5,772 against 3,105 sold from August to November, then 2,604 against 5,870 sold in 2026.

## What the tools found

`run_tools.py` loads the four files, merges the product master for categories, and runs each tool on Shipped COGS ("sales at COGS"), then once on Ordered Units.

| Planted | Found? | What the tool said |
|---|---|---|
| Latest week, nothing planted | Yes | Total: Expected (£155,160). By ASIN: 40 Expected, 3 Noise, 0 Real change. The same on Ordered Units. |
| Prime Day 2025 and 2026, Black Friday 2025 | Yes | Total: +104%, +123%, +171%, all Real change. By ASIN, of the 150 product events: Real change 89, Expected 40 (mostly cleaning and the long tail, which barely move), too little data 21 (the new range, and the delisted SKU after it went). |
| Prime Day 2024, Black Friday 2023 and 2024 | Not measurable | Too early: a promotion needs a year of history before it. The wording is misleading (see below). |
| Best Deal on the frying pan, real | Yes | "+43%, £22,103 more than expected; likely between +29% and +56%. Real change." The planted lift, after its noise, is +50%: inside the range. |
| Lightning deal on the bento box, just discounting | Yes | "−16%, £133 less than expected. Expected." It had £2,000 of funding and a 30% discount, for nothing. |
| Lightning deal on the cloths, with pull-forward | Lift yes, dip only if you look | "+119% … likely between +105% and +133%. Real change." The planted lift is +109%. The lift doesn't net off the dip that follows. The chart series shows it (actual 22% below expected over the 3 weeks after; planted about 23%), and a verdict on those 3 weeks calls them a Real change, 53% below (overstated: see below). |
| New range launched 38 weeks ago | Yes, as too early | Each ASIN: "Too early to say what to expect: it needs at least 52 weeks of history; there are 38 weeks." Seasonality for the range: too early as well. |
| SKU delisted mid-year 2 | Yes, plainly | "The period has data for 0 weeks; it needs at least 1 week." |
| Two missing weeks for one ASIN | Filled, but not said | The verdict runs, but its warnings are empty: the "filled by interpolation" warning isn't passed through. |
| Seasonality by category | Mostly | Cleaning: April +34% (planted spring peak). Cookware and Bakeware: summer lull and Q4 found. Food Storage: January +12% found, but the narrow September back-to-school bump wasn't. November is dominated by Black Friday everywhere (Cookware +132%). Air Fryer: too early. |

## What's awkward, and what should change

1. **`sales_verdict` can't leave promotions out.** The app judges a week against a fit that leaves promotion weeks out; the sales tool has no way to be told about them. Here, Black Friday and Prime Day sit in the history and inflate the expectation:

   | Promotion weeks in the fit | Expected | Range |
   |---|---|---|
   | Included (as shipped today) | £195,497 | £102,353–£288,642 |
   | Left out | £156,402 | £148,196–£164,608 |

   The same over-statement makes the post-deal dip read as −53% rather than about −22%. **Recommend:** give `sales_verdict` and `sales_seasonality` the same promotion inputs as `promotion_lift` (list, flag column, calendar), and leave those weeks plus the 3 weeks after out of the fit. Core's `decompose(exclude=…)` already does this, so only the sales layer changes, and the Shopify app is untouched.

2. **Pull-forward isn't reported.** `promotion_lift` reads the lift over the promotion's weeks and leaves the 3 weeks after out of its fit, so a dip after it goes unmentioned. **Recommend:** add the 3 weeks after to each lift row, for example "In the 3 weeks after, sales ran 22% below expected: customers may have stocked up." The series already holds it.

3. **A calendar's `all` rows match nothing.** The calendar's ASIN column is matched literally, so a Prime Day row with ASIN `all` applies to no product. `run_tools.py` expands `all` rows to every ASIN first. **Recommend:** treat `all`, `*` or a blank as every group.

4. **Some messages mislead or leave things out.**
   - Promotions in the first year say "There isn't enough data just before the promotion … there are 0 weeks". The real reason is that there's no year of history before them to know the season. Say "The promotion needs a year of data before it…", the existing sentence.
   - Launch ASINs say "needs at least 52 weeks", then the note says about 18 months; a week first gets a verdict at 77. Say about 77 weeks.
   - The delisted SKU could say when its rows stopped ("no rows since the week ending 17 May 2025").
   - Filled weeks should be passed through as a warning.

5. **Amazon's own downloads aren't one table.** As far as I know, Vendor Central's Retail Analytics export is one file per period. It has no date column, can start with a line of report settings above the header, and formats money as text ("£1,234.56"). **Check this against a real download.** To use them a user has to:
   - add a week-ending column to each weekly file (from its date range or file name);
   - stack the files;
   - skip any line above the header;
   - turn "£1,234.56" into a number.

   Today the sales tools would refuse "£1,234.56" ("… aren't numbers, for example '£1,234.56'"). **Possible tool:** load every file in a folder, take the week from each file name, and parse currency text.

6. **Categories need a join.** The report has no category, so seasonality by category needs a product master merged in (`merge_dataframes`, as here).

7. **Lift accuracy.** On the two single-product deals the true lift was inside the 90% range both times. Changing the Fourier terms (4, 6, 8, 10) moved the estimates by only a few points, so the current setting is fine for this data.

## Sell-through (not built)

`sell_in.csv` is there for a possible sell-through check: Amazon's purchases against what sold. The two flops stand out on a simple ratio (purchases ÷ sales over a rolling quarter): the cake barrel at 2.2× from launch, the vacuum containers at 1.9× in autumn 2025. Most lines sit near 1.0.
