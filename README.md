# DemandLens

Retail demand forecasting and inventory analytics using Python, SQL, and machine learning.

[Live app](https://demandlens.streamlit.app/) · [Experiment report](artifacts/experiment_report.md)

DemandLens forecasts **recorded unit sales** for seven days across a development-selected cohort of up to 20 products. It compares a direct horizon-conditioned gradient-boosting model with four simple baselines, then uses the validation-selected model for transparent inventory scenarios. The Streamlit application reads compact precomputed artifacts; it never downloads data or trains during a page request.

## Run the included demo

Requires Python **3.11**. From the repository root on Windows:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

On macOS/Linux use `python3.11 -m venv .venv`, `.venv/bin/python -m pip install -r requirements.txt`, and `.venv/bin/python -m streamlit run app.py`.

The demo is historical: **forecast as of 9 December 2011**, using history through 8 December, for 9–15 December. It is not a live sales forecast. Unknown future actuals remain null.

## Revised retrospective results

The original audit exposed a cancelled bulk order and a missing robust baseline. Revision 2 reconciles unique same-day full reversals and expands the comparison. **These results are retrospective**, not an untouched holdout: the first test inspection motivated the changes. Within the revised run, validation selects the model before the October–December outcomes are scored.

| Method | MAE (units) | WAPE | Mean bias (units) |
|---|---:|---:|---:|
| 28-day median (selected) | 71.900 | 82.837% | -44.288 |
| Gradient boosting | 77.279 | 89.036% | -4.434 |
| 28-day average | 82.232 | 94.741% | -1.883 |
| Four-week weekday average | 84.859 | 97.768% | -1.883 |
| Previous week | 95.794 | 110.367% | 0.515 |

The median's WAPE is 12.56% lower relative to the trailing mean on the revised cohort. It beats boosting for 12/20 products and 8/9 windows. **The median substantially underpredicts volume:** its bias is -44.29 units per product-day. Minimizing absolute error favors medians, which can undershoot rare large sales. It is an error-minimizing baseline, not a guarantee of adequate inventory; no cost or stockout optimization is claimed.

The cleaning audit identifies 454 unique full same-day reversal pairs and removes 85,766 merchandise units from positive sales before the final excluded day. Product 23166 leaves the selected cohort and product 22151 enters. The bundle is about 3.32 MB. The original experiment report is retained in artifacts/history/v1; original binary artifacts remain in Git history and local working storage. Cross-version scores are not a model-only improvement because both the target and cohort changed.

## Reproduce the experiment

```powershell
.\.venv\Scripts\python.exe -m demandlens prepare
.\.venv\Scripts\python.exe -m demandlens evaluate
.\.venv\Scripts\python.exe -m demandlens publish-demo
```

`prepare` downloads the original UCI archive once and records provenance. To use an existing original workbook:

```powershell
.\.venv\Scripts\python.exe -m demandlens prepare --input "C:\path\Online Retail.xlsx"
```

The commands write ignored raw/intermediate data locally. `publish-demo` builds a read-only SQLite bundle in `demo/`; it does **not** upload or publish externally. Source checksum and prepared-data checks bind the bundle to one experiment. Do not hand-edit its database or JSON files; rebuild instead.

## Application

- **Sales:** product names, a 90-day chart with full-history controls, weekday patterns, product rankings, and expandable weekly sales/returns.
- **Forecasts:** seven-day estimates, readable model comparisons, error explanations, detailed historical results, and CSV exports.
- **Inventory:** stock and delivery inputs with additional stock options and calculation details available on demand.
- **About the data:** source attribution, current review findings, cleaning policy, evaluation method, and expandable technical details.

Product codes and experiment IDs are kept in technical details. Chart legends and exports use readable labels. Displayed values are rounded; CSVs preserve calculation precision. Forecasting and data-cleaning behavior are unchanged by these interface changes. The revised cancellation policy and retrospective evaluation limitations remain disclosed.

## Evaluation protocol

1. Freeze products and display descriptions using data through **31 August 2011**. Eligible products have at least 180 days of history and 40 selling dates. Select the top 20 by units; break ties lexically by stock code.
2. For origin D, derive all sales features strictly before D and directly predict D through D+6. Training examples are admitted only when their target is observable before D.
3. Five expanding-history weekly validation origins (**1–29 September**) compare four baselines and two boosting leaf configurations (15/31). Rank by pooled WAPE, then MAE, then simplicity.
4. Freeze the selected configuration and champion before nine weekly test origins (**6 October–1 December**). Refit on available history at each origin without retuning. Test targets end 7 December.
5. Refit the selected boosting configuration and calculate all four baselines at the final origin. The dashboard serves the frozen champion.

The feature pipeline includes lags 1/7/14/28, trailing means 7/14/28, 28-day population standard deviation and positive-day fraction, a recent-week trend, product one-hot encoding, horizon, and target weekday/month sine/cosine features. Future transaction prices, outcomes, and sales are never model inputs. Random early stopping is disabled. Predictions are clipped at zero and remain fractional until purchase rounding.

**Metrics:** MAE, pooled WAPE, mean signed bias, absolute seven-day cumulative error, and measured training/inference time. A zero actual denominator produces unavailable WAPE, not infinity. Do not average product WAPEs to obtain the aggregate.

Measured results and three actual error cases are generated into `artifacts/experiment_report.md`. Machine-readable metrics, timing, and all validation/test predictions are in the included database. The baseline is allowed to win.

## Inventory assumptions

```text
Protection days = lead time + review period (maximum seven)
Target stock = sum(forecast over protection days) + user safety buffer
Inventory position = on-hand + inbound available before day one − backorders
Suggested order = ceil(max(0, target stock − inventory position))
```

Defaults: three-day lead time, one-day review period, zero inbound/backorders/buffer. On-hand stock must be entered. Later inbound arrivals are excluded. This is an order-up-to **scenario**, not a service-level guarantee or a real supplier purchasing system.

## Data and attribution

Chen, D. (2015). **Online Retail** [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33. Licensed **CC BY 4.0**. Original data: https://archive.ics.uci.edu/dataset/352/online+retail.

The original contains 541,909 transaction lines from December 2010–December 2011. The raw workbook is not redistributed. The demo contains derived selected-product aggregates, returns, forecasts, and reports with attribution. No customer IDs or customer-level transactions are published.

Unique full same-day reversals remove the original positive sale when customer, product, quantity and price match unambiguously and the cancellation occurs strictly later. Other returns/cancellations remain separate; cross-day and partial returns are not netted into the target. Missing customer IDs do not remove valid sales. Duplicate-looking lines and valid large orders are retained. The last recorded day is excluded under a conservative incomplete-export policy. The fixed non-merchandise policy and actual missingness are recorded in the cleaning audit. Zero records are treated as zero **recorded sales**, not proof of stock availability or store closure.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Tests cover cleaning, deterministic selection, temporal leakage, feature arithmetic, baseline forecasts, model selection, zero-denominator metrics, inventory input validation, SQL/Pandas agreement, bundle checksums, and Streamlit page/form interactions. GitHub Actions runs the suite on Python 3.11. The deployed release passed all 47 tests on Windows and [GitHub Actions on Linux](https://github.com/Tirthpanchori/DemandLens/actions).

`constraints.txt` pins the dependency versions installed in the isolated verification environment. It constrains both runtime and development installation without adding development tools to the app's required packages.

The executed notebook `notebooks/01_sales_analysis.ipynb` uses prepared pipeline outputs. Rebuild it with `python scripts/build_notebook.py` after preparation.

## Deployment

Push this repository, including `demo/` and `sql/`, to GitHub. In Streamlit Community Cloud choose the repository, `app.py`, and Python 3.11. Dependencies are declared in the root `requirements.txt`. No secrets or external database are required. The `.streamlit/config.toml` file supplies the theme and disables usage statistics.

Keep `data/raw/`, `data/processed/`, the virtual environment, intermediate reports, and local runtime logs out of Git. The bundle must pass its schema, checksum, and SQLite integrity checks. Rebuild it locally to update the demo. The public app is hosted at https://demandlens.streamlit.app/.

## Repository layout

| Folder | Purpose |
|---|---|
| `demandlens/` | Data preparation, forecasting, evaluation, and inventory logic |
| `demo/` | Small verified deployment database and metadata; required by the app |
| `sql/` | Named analytical queries |
| `tests/` | Data, forecasting, inventory, SQL, and app checks |
| `notebooks/` | Executed exploratory analysis |
| `docs/` | Decisions, data dictionary, and interview explanations |
| `artifacts/` | Current results, per-product comparison, and original experiment report |
| `scripts/` | Rebuild the executed notebook |

Raw data, intermediate pipeline outputs, duplicate metadata, obsolete database snapshots, screenshots, and local test logs are excluded from the current repository. They can remain locally without being uploaded. A fresh clone can run the included demo immediately after installing dependencies; reproducing training starts with the preparation command.

## Limits and roadmap

This experiment covers one historical gift retailer and established products selected from development data. Unobserved stockouts, promotions, opening calendars, and bulk orders limit interpretation. It does not estimate unconstrained demand, guarantee stock availability, or prove inventory savings. No confidence intervals or causal effects are claimed.

Next steps: calibrated prediction intervals, explicit simulated inventory policy comparisons, intermittent-sales methods, longer/store-level datasets with availability and promotions, validated CSV ingestion, and scheduled offline artifact refreshes. GenAI is intentionally outside this project's scope.

## Interview preparation

See docs/interview-guide.md for plain-language explanations and examples. The generated experiment report includes original-versus-revised results and failure cases; quote current measurements and explicitly disclose retrospective evaluation.
