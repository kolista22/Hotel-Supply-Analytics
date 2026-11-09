# Hotel Supply Analytics

A small local portfolio MVP for descriptive hotel-booking analysis, built with Python, pandas, SQLite and Streamlit. Independent work; not Nuitée data or a collaboration with Nuitée. No authentication, deployment, LLM features or cloud database.

## Data source and permission

**Antonio, Nuno; de Almeida, Ana; Nunes, Luis (2019), “Hotel booking demand datasets”, Data in Brief 22, 41–49. DOI: https://doi.org/10.1016/j.dib.2018.11.126.**

The authors' publication identifies its open-access license as **CC BY 4.0**: https://creativecommons.org/licenses/by/4.0/ . Verified on page 1 of the institutional article copy: https://repositorio.iscte-iul.pt/bitstream/10071/16929/1/Hotelbookingdemanddatasets.pdf . Data is supplied with the paper. Author/hotel/customer identities were anonymized by the source.

CSV mirror: https://raw.githubusercontent.com/rfordatascience/tidytuesday/main/data/2020/2020-02-11/hotels.csv . TidyTuesday combines the two hotel tables and normalizes column names; dictionary/provenance: https://github.com/rfordatascience/tidytuesday/blob/main/data/2020/2020-02-11/readme.md . We downloaded only that CSV, not another person's application or analysis. Retrieval date, exact bytes, SHA-256 and columns are in `data/source.json`. Our cleaning/derived fields and synthetic mapping are changes described below. Keep attribution and license when sharing data or derivatives. No license for this new application code has been assigned yet.

The local source has **119,390 rows and 32 columns**, covering arrivals **2015-07-01 to 2017-08-31** in two Portuguese hotels (City/Resort). This is a historical sample, not current market data.

## Questions the fields can answer

1. What booking volume and cancellation share appear in each hotel-type group?
2. How much check-out lodging value is represented by ADR × nights under an explicit eligibility rule?
3. Which arrival months have the highest observed volume in the selected historical sample?

There is **no actual supplier ID**. `agent` represents travel agencies and `company` a booking/paying entity; neither is assumed to identify a hotel supplier. We therefore define two transparent **synthetic supplier demo labels**, one per anonymized hotel type:

| Actual source field | Synthetic demo group |
|---|---|
| Resort Hotel | Synthetic Resort Demo |
| City Hotel | Synthetic City Demo |

The mapping is for demonstrating JOIN/GROUP BY and Dashboard interactions. Comparisons are real hotel-type aggregates with synthetic labels, not actual supplier rankings, service quality or wholesale supply performance.

## Implemented

- pandas CSV loading, type conversion, missing-value audit, invalid-core exclusion and derived fields.
- SQLite `bookings` and explicitly synthetic `suppliers` dimension; SQL CTE, JOIN, GROUP BY, conditional parameter filters and rates.
- Headline volume/cancellation/value-proxy metrics, synthetic-group comparisons, arrival-month trend and three calculated observations.
- Supply-group/year filters, full-data quality report and readable SQL inside the UI.
- Local generated reports with the same definitions as the Dashboard.

## Metric definitions — read before interpreting

| Metric | Definition / denominator |
|---|---|
| Bookings | Number of retained source rows, cancelled and non-cancelled. Not unique customers or rooms. |
| Cancellations | SUM(is_canceled), using the source's binary field. |
| Cancellation rate | SUM(is_canceled) / COUNT(*). Overall rate is booking-weighted, never the mean of group percentages. |
| Nights | stays_in_weekend_nights + stays_in_week_nights. |
| Check-out value proxy | SUM(ADR × nights) only where is_canceled=0, reservation_status=Check-Out, nights>0, ADR finite and >=0. |
| Proxy-eligible bookings | Number satisfying that rule, including valid zero ADR. |
| Arrival month | YYYY-MM of scheduled arrival, not booking creation or cancellation-event month. |

**Value proxy is NOT audited revenue, realized cash, profit, commission, refunds or supplier settlement.** Missing transaction/currency/settlement details prevent those claims. Display uses ADR currency units, without assuming a currency code. Cancelled/no-show fees are not modeled. A zero proxy for a selection with zero eligible rows is not evidence of actual zero revenue; inspect the eligible count.

All views read the same cleaned SQLite rows. KPIs, observations and trend apply the selected supply group and arrival year. Comparison charts intentionally show ALL synthetic groups in the selected year, regardless of the group selector; the UI explicitly labels this different scope. Empty KPI selections show an undefined rate (N/A), not 0%.

## Cleaning and data quality

- Convert required numeric fields and construct arrival dates; exclude invalid cancellation labels, hotel labels, dates, negative or fractional night counts from booking metrics. Actual source excluded **0** core rows.
- Treat `NULL`/`NA` as missing. Actual missing values include children **4**, country **488**, agent **16,340**, company **112,593**. Do not infer missing agents are direct bookings or fill missing children with zero.
- Retain **31,994 exact duplicate rows** (beyond their first occurrences): no genuine booking ID exists, so identical rows may represent distinct bookings. `source_row` is only a generated source-row reference. This choice affects totals and is visible, not silently deduplicated.
- Actual data has **1 negative ADR** and **715 zero-night rows**. Keep these in booking counts; exclude invalid rates/zero nights from the value proxy. Other positive ADR outliers are retained, not silently capped; this can influence proxy totals.
- **74,485** bookings qualify for the proxy; **44,905** do not. They have not all been deleted from the booking denominator.

## Actual observations — full dataset, 2026-11-09 run

- **119,390** bookings; **44,224** cancellations; rate **37.0416%**.
- Synthetic City Demo has about **41.7%** cancellations versus **27.8%** for Synthetic Resort Demo, a roughly **14.0 percentage-point** difference using unrounded rates. These are descriptive hotel-type differences, not causal supplier effects.
- Highest observed arrival month: **May 2017, 6,313 bookings**. Partial first/last years make unadjusted annual comparisons misleading.

Check-out value proxy: **25,996,324.21 ADR currency units** under the rule above, not confirmed revenue. Dashboard observations recalculate under filters.

## Install and run

Python 3.11 is the verified local runtime. From the project directory:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python download_data.py
.venv/bin/python analytics.py
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8502 --browser.gatherUsageStats false
```

Open http://127.0.0.1:8502 . With the provided local CSV/database already prepared, only the final command is needed. CSV download requires internet once; the Dashboard reads only local files. The downloader refuses to overwrite an existing CSV, and processing verifies its source hash. `analytics.py` rebuilds this project's generated SQLite database/reports, not any external database. Exact installed versions are in `requirements-lock.txt` for reproduction.

## Basic tests

```sh
.venv/bin/python -m unittest discover -s tests -v
```

**10 tests passed**: hand-calculated fixtures, rate denominator, JOIN/monthly reconciliation, filters/empty selection, duplicate policy, invalid fields and rates, full-data pandas/SQL agreement, Streamlit AppTest startup/filter recalculation, plus a four-scenario chart-spec/data regression checking a temporal x-axis, numeric points, KPI/month reconciliation and two-group comparison scope. Latest raw output: `reports/chart-fix-tests.txt` (local, ignored).

The live Streamlit server returned HTTP 200 for the page and health endpoint. Isolated Chrome rendered all four metrics, the synthetic warning and chart canvases without app exception elements or captured runtime exceptions; the chart screenshot was inspected. Filter recalculation was exercised through Streamlit AppTest, not a claim of manual user/browser acceptance. Browser evidence: `reports/browser-check.json`; generated screenshot: `reports/dashboard.png`.

## Layout

- `download_data.py`: source download/provenance.
- `analytics.py`: cleaning, SQLite load, queries and computed observations.
- `sql/overview.sql`, `suppliers.sql`, `monthly.sql`: inspectable query definitions.
- `app.py`: Streamlit Dashboard.
- `data/source.json`: authors/license/source hash; CSV/database ignored.
- `reports/`: generated quality audit, three aggregate CSVs, observations and verification evidence (ignored).

## Contribution and approval boundary

User supplied the product name, goal, stack, time budget, synthetic-data conditions and acceptance boundary. **Codex wrote the implementation, selected/processed the data, wrote/executed tests and calculated the observations.** These are not user-independent coding, SQL mastery, personal debugging or hotel-industry employment claims. On 2026-11-09, the user explicitly confirmed passing personal browser re-acceptance after requesting the chart and comparison fixes, and authorized public source publication and a separately attributed CV update. The user defined the project direction and business-analysis goals, reviewed the output, requested corrections and performed browser acceptance. Codex implemented the code, investigated the rendering issue and executed automated tests. Independent code authorship or SQL mastery is not inferred. No job application submission is authorized.

## Manual review checkpoint

Open the Dashboard, change the group/year filters, read the SQL expander and check the data-quality section. Explain the cancellation denominator, why the value is only a proxy, why duplicates were retained, and why synthetic groups cannot rank real suppliers. Personal browser re-acceptance and permission to publish/update the CV were explicitly confirmed on 2026-11-09. This checklist remains useful for understanding the SQL and metrics; no claim of independent coding or professional hotel-supply work follows.

## User-reported chart corrections — 2026-11-09

The user reported an empty arrival-month plot and requested all-group comparisons even when KPIs select one group. Codex investigated and implemented the scoped changes; the user confirmed personal browser re-acceptance passed on 2026-11-09.

The monthly SQL was not empty: 26 months overall and 12 in 2016, with totals matching KPIs. The original `st.line_chart` received a string `YYYY-MM` index; its generated spec inferred nominal x encoding and added default scale-bound selections. Chrome showed scale-binding and infinite-extent warnings, and the trend lacked a visible line. The fix converts the real SQL month field to datetime, sorts it and uses an explicit temporal/quantitative Vega-Lite line with visible points, without those automatic selections. This isolates the failure to the inferred/default chart configuration, not missing data; no specific upstream-library defect has been independently proven. No data, SQL aggregation or metric formula was fabricated or changed.

Comparison data now queries all synthetic groups for the selected year. KPI/observations/trend still use the selected group and year. Observations were moved below KPIs and SQL result tables moved into an expander. Synthetic labels and value-proxy disclosures remain visible.

10 focused tests passed. Real Chrome dropdown interaction verified All years (26 points; 119,390 bookings), all groups/2016 (12; 56,707), City/2016 (12; 38,140), and Resort/2016 (12; 18,567). Each scenario had an actual SVG line and point marks and both comparison bars; the final trend screenshot was inspected. The earlier smoke test checked chart containers, not actual trend marks, so it missed this failure. New checks address that gap.

Transient Vega warnings can still occur during filter rerenders; the final visible marks/values were checked, not a claim of a warning-free renderer. During that fix, there was no dependency upgrade, deployment, GitHub publication or CV modification; publication and a CV update were authorized subsequently. Evidence: reports/trend-before-spec.json, chart-fix-tests.txt, chart-fix-browser.json and trend-fixed.png (local, ignored).
