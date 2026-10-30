# Data dictionary

Dates are naive calendar dates from the source. Sales values use source sterling amounts and exclude returns and invalid/non-merchandise records. No currency conversion or inflation adjustment is applied.

| Table | Grain | Important columns |
|---|---|---|
| products | One row per selected stock code | product_id, training-derived description, first_sale, positive_sales_days, training_units, history_days |
| daily_sales | Product × date | units_sold, gross_sales_value, order_count (distinct invoice numbers), large_order_rows, inserted_zero |
| retail_daily | Date, all valid merchandise | units_sold, gross_sales_value, large_order_rows; used for cohort coverage and notebook analysis |
| returns_daily | Product × date | return_units (absolute quantity), cancellation_rows; separate from sales; includes matched cancellations, not an amount to subtract again |
| forecasts | Run × model × split × origin × product × horizon | target_date, horizon 1–7, prediction, actual (NULL for final), run_id |
| metrics | Split × model × level × group × metric | value; NULL when WAPE denominator is zero; product_window cumulative error uses absolute difference of seven-day totals |
| timings | Split × origin × model | training_seconds, prediction_seconds, training_rows, forecast_rows |
| runs | One published experiment | run_id, source_sha256, configuration JSON |
| cleaning_report | Exclusion rule | affected_rows, before, after; rules applied sequentially |

`origin` is the first unknown forecast date, not the last observed date. A row's target is `origin + horizon - 1`; every sales feature predates the origin. Baseline names are `seasonal_naive`, `trailing_mean`, `trailing_median`, and `weekday_mean4`; boosting configurations are `hgb_15` and `hgb_31`.

## Metrics

- MAE = mean absolute daily error, in units.
- WAPE = 100 × summed absolute daily errors / summed actual units. All-zero actuals produce NULL.
- Bias = mean(prediction − actual); positive means overprediction.
- Cumulative absolute error = abs(sum of seven daily predictions − sum of seven actuals). Opposite daily errors can cancel, so this does not replace daily MAE.

## Inventory inputs and results

Lead/review periods and stock quantities are nonnegative integers (lead/review at least one). `forecast_units` is a fractional expected total over the protection period. `inbound` must be available before that period starts. `inventory_position` includes backorders; it may be negative. `suggested_order` is a nonnegative integer rounded upward.

## Provenance and privacy

The cleaning JSON stores source DOI/license/URL, UTC preparation/retrieval metadata, original workbook SHA-256, missingness, exclusion policy, and row reconciliation. Evaluation JSON stores cutoffs, chosen model, parameters, code/data hashes, packages, and validation ranking. Manifest JSON stores schema version, run ID, bundle byte count, and per-file checksums. Published tables contain no customer IDs or raw customer transactions.

## Cancellation audit

`cancellation_matches` contains one row per unique full same-day reversal: product_id, date, units, price, purchase/cancellation timestamps, original zero-based source row indices, and sales_value. It contains no customer identifiers. Pairs on the final excluded date and non-merchandise pairs can appear in this source-level audit; the cleaning report separately counts merchandise units actually removed before that boundary. Positive matched purchases have exclusion reason `matched_same_day_reversal`; negative entries retain `returns_or_cancellations`.

Revision 2 is a retrospective evaluation following the first test audit. Original artifacts remain archived, and cohort changes are documented in the experiment report.
