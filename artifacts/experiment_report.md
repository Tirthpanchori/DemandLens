# DemandLens experiment report

Run: `43465a06f2cc-0ce2c57bbd29`
Source SHA-256: `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`

## Protocol

**Retrospective revision.** Cancellation handling and added baselines were motivated by inspecting the original test period. The revised October–December results are a retrospective comparison, not a fresh untouched holdout. Candidate settings remain fixed during this run.

20-product maximum, selected using sales through 31 August 2011. Five weekly validation origins (1–29 September) select the model; nine weekly test origins (6 October–1 December) evaluate it. Each origin predicts seven days using only history before that origin. Models refit on expanding history.

Validation-selected champion: **trailing_median**. The October–December outcomes do not reselect the serving model within this revised run.

## Cancellation reconciliation

Unique same-day full reversals identified: **454**. Merchandise units removed from positive sales before the final excluded day: **85,766**. Matching requires a known customer, product, exact quantity and price, and strictly later same-day cancellation. Ambiguous, partial, and cross-day returns are left separate. The source is unchanged; a row-index audit is retained without customer IDs.

## Revised retrospective metrics

| Model | MAE (units) | WAPE (%) | Bias (units) |
|---|---:|---:|---:|
| trailing_median | 71.900 | 82.837 | -44.288 |
| hgb_15 | 77.279 | 89.036 | -4.434 |
| trailing_mean | 82.232 | 94.741 | -1.883 |
| weekday_mean4 | 84.859 | 97.768 | -1.883 |
| seasonal_naive | 95.794 | 110.367 | 0.515 |

## Baseline comparisons

- Champion WAPE improvement relative to trailing_median: 0.00% (negative means worse; zero can mean the champion is this baseline).
- Champion WAPE improvement relative to trailing_mean: 12.56% (negative means worse; zero can mean the champion is this baseline).
- Champion WAPE improvement relative to weekday_mean4: 15.27% (negative means worse; zero can mean the champion is this baseline).
- Champion WAPE improvement relative to seasonal_naive: 24.94% (negative means worse; zero can mean the champion is this baseline).

Mean seven-day cumulative absolute error: 337.114 units.

## Three observed failure cases

1. Product **84077**, 2011-10-27, horizon 1: actual 4848, predicted 109.50, absolute error 4738.50. The pre-origin 28-day mean was 132.32 units/day. Underprediction: the recorded sales exceeded the forecast. The data does not identify promotions, stock availability, or customer intent, so the cause is unconfirmed.
2. Product **22197**, 2011-10-28, horizon 2: actual 2065, predicted 125.00, absolute error 1940.00. The pre-origin 28-day mean was 172.46 units/day. Underprediction: the recorded sales exceeded the forecast. The data does not identify promotions, stock availability, or customer intent, so the cause is unconfirmed.
3. Product **22197**, 2011-11-07, horizon 5: actual 2012, predicted 135.00, absolute error 1877.00. The pre-origin 28-day mean was 216.18 units/day. Underprediction: the recorded sales exceeded the forecast. The data does not identify promotions, stock availability, or customer intent, so the cause is unconfirmed.

## Product and window consistency

- Champion strictly beats hgb_15 on WAPE for 12/20 products and 8/9 windows.
- Champion strictly beats trailing_mean on WAPE for 17/20 products and 8/9 windows.
- Champion strictly beats weekday_mean4 on WAPE for 17/20 products and 8/9 windows.
- Champion strictly beats seasonal_naive on WAPE for 20/20 products and 9/9 windows.

## Window stability

| Origin | MAE | WAPE (%) |
|---|---:|---:|
| 2011-10-06 | 65.850 | 86.127 |
| 2011-10-13 | 53.882 | 82.452 |
| 2011-10-20 | 57.707 | 91.588 |
| 2011-10-27 | 105.879 | 90.927 |
| 2011-11-03 | 92.804 | 85.748 |
| 2011-11-10 | 100.004 | 81.726 |
| 2011-11-17 | 54.754 | 68.479 |
| 2011-11-24 | 56.586 | 79.827 |
| 2011-12-01 | 59.632 | 75.992 |

## Limits and interpretation

- Recorded sales are not uncensored demand; zero records do not establish availability or closure.
- One historical gift retailer, about one year, and a development-selected established-product cohort limit generalization.
- The last recorded date is excluded by conservative policy; inventory is a user-input scenario with no real stock validation.
- Unmatched duplicate-looking lines and large orders remain; only unambiguous same-day reversals are removed.
- No calibrated prediction intervals, causal claims, service guarantees, or measured inventory savings.

## Source

Chen, D. (2015). Online Retail. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33. CC BY 4.0.

## Original versus revised experiment

The original source bundle and report are archived in artifacts/history/v1. The sales target and selected products changed after cancellation reconciliation. Cross-version score differences cannot be attributed solely to a better model or compared as controlled improvement.

Products removed from cohort: 23166.
Products added to cohort: 22151.

| Original model | Original MAE | Original WAPE (%) |
|---|---:|---:|
| hgb_15 | 78.762 | 90.046 |
| trailing_mean | 82.999 | 94.890 |
| seasonal_naive | 97.299 | 111.238 |
