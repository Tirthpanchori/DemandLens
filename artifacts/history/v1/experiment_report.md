# DemandLens experiment report

Run: `43465a06f2cc-9f55816d25ce`
Source SHA-256: `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`

## Protocol

20-product maximum, selected using sales through 31 August 2011. Five weekly validation origins (1–29 September) select the model; nine weekly test origins (6 October–1 December) evaluate it. Each origin predicts seven days using only history before that origin. Models refit on expanding history.

Validation-selected champion: **hgb_15**. Test results did not select or change the serving model.

## Test metrics

| Model | MAE (units) | WAPE (%) | Bias (units) |
|---|---:|---:|---:|
| hgb_15 | 78.762 | 90.046 | -2.955 |
| trailing_mean | 82.999 | 94.890 | -2.144 |
| seasonal_naive | 97.299 | 111.238 | 0.425 |

## Baseline comparisons

- Champion WAPE improvement relative to trailing_mean: 5.11% (negative means worse; zero can mean the champion is this baseline).
- Champion WAPE improvement relative to seasonal_naive: 19.05% (negative means worse; zero can mean the champion is this baseline).

Mean seven-day cumulative absolute error: 320.587 units.

## Three observed failure cases

1. Product **84077**, 2011-10-27, horizon 1: actual 4848, predicted 170.20, absolute error 4677.80. The pre-origin 28-day mean was 132.32 units/day. Underprediction: the recorded sales exceeded the forecast. The data does not identify promotions, stock availability, or customer intent, so the cause is unconfirmed.
2. Product **22197**, 2011-10-28, horizon 2: actual 2065, predicted 158.48, absolute error 1906.52. The pre-origin 28-day mean was 172.46 units/day. Underprediction: the recorded sales exceeded the forecast. The data does not identify promotions, stock availability, or customer intent, so the cause is unconfirmed.
3. Product **22197**, 2011-11-07, horizon 5: actual 2012, predicted 122.22, absolute error 1889.78. The pre-origin 28-day mean was 216.18 units/day. Underprediction: the recorded sales exceeded the forecast. The data does not identify promotions, stock availability, or customer intent, so the cause is unconfirmed.

## Window stability

| Origin | MAE | WAPE (%) |
|---|---:|---:|
| 2011-10-06 | 73.545 | 88.853 |
| 2011-10-13 | 73.645 | 113.102 |
| 2011-10-20 | 63.384 | 102.174 |
| 2011-10-27 | 111.025 | 95.918 |
| 2011-11-03 | 93.748 | 87.022 |
| 2011-11-10 | 87.647 | 71.536 |
| 2011-11-17 | 72.273 | 88.725 |
| 2011-11-24 | 60.643 | 84.858 |
| 2011-12-01 | 72.949 | 93.073 |

## Limits and interpretation

- Recorded sales are not uncensored demand; zero records do not establish availability or closure.
- One historical gift retailer, about one year, and a development-selected established-product cohort limit generalization.
- The last recorded date is excluded by conservative policy; inventory is a user-input scenario with no real stock validation.
- Exact duplicate-looking lines and valid large orders remain; they can produce difficult spikes.
- No calibrated prediction intervals, causal claims, service guarantees, or measured inventory savings.

## Source

Chen, D. (2015). Online Retail. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33. CC BY 4.0.
