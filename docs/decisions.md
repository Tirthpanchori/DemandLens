# Technical decisions

## 1. Forecast recorded units, not revenue or unconstrained demand

Units connect to inventory arithmetic. Prices and customer intent are not known for future dates; observed transactions cannot identify stockouts. Keep returns separate and label all inventory outputs as scenarios.

## 2. Freeze a development-selected cohort

Products and descriptions are selected through 31 August 2011 only, before validation/test. New post-cutoff best sellers cannot influence inclusion. The top-20 cohort favors established products; this selection bias is disclosed.

## 3. Use a pooled direct horizon-conditioned model

A single model shares information across products and horizons. Origin features use only past observations; horizon and future calendar features identify the target. This avoids feeding actual future sales into recursive predictions. Only labels before each refit origin are admitted.

## 4. Compare against competitive simple baselines

Use same-weekday-last-week, trailing-28-day mean and median, and four-week same-weekday mean baselines. Select the champion by validation WAPE, MAE, then baseline simplicity. Choose between two predetermined boosting configurations only. October–December outcomes do not reselect the model within this revised run. The revision was informed by the original test audit and is explicitly retrospective.

## 5. Retain unexplained large sales and duplicate-looking lines

Unusual orders can be real wholesale transactions. Exact repeated lines are not conclusively erroneous. Flag large quantities using the training-only 99.5th percentile, but retain them. Keep exclusion counts sequential so they reconcile exactly to the input row count.

## 6. Interpret inserted dates conservatively

Build daily calendars from each selected product's first sale. Absent transactions become zero recorded sales under the source completeness assumption. Retain insertion flags. Do not infer opening hours, closures, availability, or lost sales.

## 7. Bound inventory calculations to the forecast horizon

Lead time plus review period cannot exceed seven days. Only inbound already available before protection day one counts. User safety buffers are not calibrated service levels. A ceiling applies only to suggested purchase quantities, not model estimates.

## 8. Separate offline computation from hosting

The dashboard reads precomputed SQLite/JSON artifacts. It does not need the original workbook, GPU, API, job queue, or writeable server storage. Scenarios are ephemeral session state. Downloadable CSVs provide usable results without account infrastructure.

## 9. Validate bundle consistency

Prepared products and sales hashes are recorded during evaluation; publication rejects stale inputs. A manifest binds published files to a source/code-derived run ID. SQLite unique indexes guard cardinality and read-only connections protect hosted analytics.

## 10. Keep the first release focused

Streamlit and SQLite keep effort on data correctness and evaluation. No GenAI, authentication, automatic purchasing, arbitrary uploads, or large hyperparameter search. Deeper modeling and operational simulation belong after the tested MVP.

## 11. Reconcile only clear same-day reversals

A full negative cancellation must uniquely match a positive non-cancellation purchase on known customer, product, absolute quantity, exact price, and calendar day, with a strictly later timestamp. Duplicate candidates on either side are left unmatched. Partial and cross-day returns remain separate. This removes known same-day reversals before the next daily forecast origin without using future-day cancellations. Matched source row IDs and timestamps are audited without customer IDs; both source records remain in the unchanged workbook and exclusion audit.

## 12. Preserve the original experiment

Original artifacts are archived in artifacts/history/v1. Cleaning changes can alter both the target and top-20 cohort, so old versus revised scores are not a controlled model-only improvement. Do not describe revised test results as untouched holdout performance or select per-product models using them.
