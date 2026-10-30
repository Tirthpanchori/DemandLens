"""Build and verify a compact, source-free, read-only deployment bundle."""
import json
import os
from contextlib import closing
from pathlib import Path
import sqlite3

import pandas as pd

from .config import ARTIFACTS, DEMO, PROCESSED, SCHEMA_VERSION
from .data import sha256, write_json
from .queries import query


def load_bundle(directory=DEMO):
    directory = Path(directory)
    try:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        if manifest["schema_version"] != SCHEMA_VERSION:
            raise ValueError("Unsupported artifact schema version.")
        for name, checksum in manifest["files"].items():
            if Path(name).name != name or sha256(directory / name) != checksum:
                raise ValueError(f"Artifact checksum mismatch: {name}")
        db = directory / "demandlens.sqlite"
        with closing(sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
            if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Database integrity check failed.")
            run = conn.execute("SELECT run_id FROM runs").fetchone()[0]
            if run != manifest["run_id"]:
                raise ValueError("Database and manifest refer to different runs.")
        return manifest
    except (OSError, KeyError, json.JSONDecodeError, sqlite3.Error) as exc:
        raise ValueError("Demo artifacts are missing or incompatible. Run: python -m demandlens publish-demo") from exc


def sql_frame(frame):
    result = frame.copy()
    for col in result.select_dtypes(include=["datetime", "datetimetz"]).columns:
        result[col] = result[col].dt.strftime("%Y-%m-%d")
    return result


def publish_demo():
    try:
        evaluation = json.loads((ARTIFACTS / "evaluation.json").read_text())
        report = json.loads((ARTIFACTS / "cleaning_report.json").read_text())
    except FileNotFoundError as exc:
        raise ValueError("Run prepare and evaluate before publish-demo.") from exc
    if evaluation["source_sha256"] != report["workbook_sha256"]:
        raise ValueError("Preparation and evaluation source checksums differ. Run evaluate again.")
    for name in ["daily_sales", "products"]:
        if evaluation[f"{name}_sha256"] != sha256(PROCESSED / f"{name}.parquet"):
            raise ValueError(f"Prepared {name} changed after evaluation. Run evaluate again.")
    DEMO.mkdir(parents=True, exist_ok=True)
    temporary = DEMO / "demandlens.build.sqlite"
    temporary.unlink(missing_ok=True)
    products = pd.read_parquet(PROCESSED / "products.parquet")
    with closing(sqlite3.connect(temporary)) as conn:
        for table in ["products", "daily_sales", "forecasts", "metrics", "timings", "returns_daily", "retail_daily", "cancellation_matches"]:
            frame = pd.read_parquet(PROCESSED / f"{table}.parquet")
            if table == "returns_daily":
                frame = frame.loc[frame.product_id.isin(products.product_id)]
            sql_frame(frame).to_sql(table, conn, index=False, if_exists="replace")
        pd.DataFrame([{"run_id": evaluation["run_id"], "source_sha256": evaluation["source_sha256"],
                       "configuration": json.dumps(evaluation)}]).to_sql("runs", conn, index=False)
        pd.DataFrame(report["rules"]).to_sql("cleaning_report", conn, index=False)
        conn.executescript("""
        CREATE UNIQUE INDEX products_pk ON products(product_id);
        CREATE UNIQUE INDEX sales_pk ON daily_sales(product_id,date);
        CREATE UNIQUE INDEX forecast_pk ON forecasts(run_id,model,split,origin,product_id,horizon);
        CREATE UNIQUE INDEX metrics_pk ON metrics(split,model,level,group_value,metric);
        CREATE INDEX forecasts_selection ON forecasts(split,model,product_id);
        CREATE INDEX sales_date ON daily_sales(date);
        """)
    os.replace(temporary, DEMO / "demandlens.sqlite")
    write_json(DEMO / "cleaning_report.json", report)
    write_json(DEMO / "evaluation.json", evaluation)
    manifest = {"schema_version": SCHEMA_VERSION, "run_id": evaluation["run_id"],
                "champion": evaluation["champion"], "final_origin": evaluation["final_origin"],
                "files": {name: sha256(DEMO / name) for name in
                          ["demandlens.sqlite", "cleaning_report.json", "evaluation.json"]}}
    manifest["bundle_bytes"] = sum((DEMO / f).stat().st_size for f in manifest["files"])
    write_json(DEMO / "manifest.json", manifest)
    load_bundle()
    write_experiment_report(evaluation, report)
    print(f"Demo published locally: {manifest['bundle_bytes']/1_000_000:.2f} MB. Champion: {evaluation['champion']}.", flush=True)
    return manifest


def write_experiment_report(evaluation, report):
    db = DEMO / "demandlens.sqlite"
    scores = query(db, "model_metrics")
    worst = query(db, "worst_predictions", model=evaluation["champion"]).head(3)
    cumulative = query(db, "cumulative_errors", model=evaluation["champion"])
    windows = query(db, "window_errors", model=evaluation["champion"])
    lines = ["# DemandLens experiment report", "", f"Run: `{evaluation['run_id']}`",
             f"Source SHA-256: `{evaluation['source_sha256']}`", "",
             "## Protocol", "",
             "**Retrospective revision.** Cancellation handling and added baselines were motivated by inspecting "
             "the original test period. The revised October–December results are a retrospective comparison, "
             "not a fresh untouched holdout. Candidate settings remain fixed during this run.", "",
             "20-product maximum, selected using sales through 31 August 2011. Five weekly validation origins "
             "(1–29 September) select the model; nine weekly test origins (6 October–1 December) evaluate it. "
             "Each origin predicts seven days using only history before that origin. Models refit on expanding history.",
             "", f"Validation-selected champion: **{evaluation['champion']}**. "
             "The October–December outcomes do not reselect the serving model within this revised run.",
             "", "## Cancellation reconciliation", "",
             f"Unique same-day full reversals identified: **{report['matched_reversal_pairs']}**. "
             f"Merchandise units removed from positive sales before the final excluded day: "
             f"**{report['matched_merchandise_units_removed']:,.0f}**. "
             "Matching requires a known customer, product, exact quantity and price, and strictly later same-day cancellation. "
             "Ambiguous, partial, and cross-day returns are left separate. The source is unchanged; a row-index audit is retained without customer IDs.",
             "", "## Revised retrospective metrics", "",
             "| Model | MAE (units) | WAPE (%) | Bias (units) |", "|---|---:|---:|---:|"]
    for r in scores.itertuples():
        lines.append(f"| {r.model} | {r.mae:.3f} | {r.wape:.3f} | {r.bias:.3f} |")
    champion = scores.loc[scores.model.eq(evaluation["champion"])].iloc[0]
    lines += ["", "## Baseline comparisons", ""]
    for r in scores.loc[~scores.model.str.startswith("hgb_")].itertuples():
        improvement = 100 * (r.wape - champion.wape) / r.wape if r.wape else 0
        lines.append(f"- Champion WAPE improvement relative to {r.model}: {improvement:.2f}% "
                     "(negative means worse; zero can mean the champion is this baseline).")
    lines += ["", f"Mean seven-day cumulative absolute error: {cumulative.cumulative_absolute_error.mean():.3f} units.",
              "", "## Three observed failure cases", ""]
    for n, row in enumerate(worst.itertuples(), 1):
        history = query_history(db, row.product_id, row.origin)
        recent = float(history.units_sold.tail(28).mean())
        if row.actual > row.prediction:
            observation = "Underprediction: the recorded sales exceeded the forecast."
        else:
            observation = "Overprediction: the forecast exceeded recorded sales."
        lines.append(f"{n}. Product **{row.product_id}**, {row.target_date}, horizon {row.horizon}: "
                     f"actual {row.actual:.0f}, predicted {row.prediction:.2f}, absolute error {row.absolute_error:.2f}. "
                     f"The pre-origin 28-day mean was {recent:.2f} units/day. {observation} "
                     "The data does not identify promotions, stock availability, or customer intent, so the cause is unconfirmed.")
    window_lines = ["| Origin | MAE | WAPE (%) |", "|---|---:|---:|"]
    window_lines += [f"| {r.origin} | {r.mae:.3f} | {r.wape:.3f} |" for r in windows.itertuples()]
    # Capture wins at product and window grain, not just an aggregate percentage.
    product_scores = query(db, "product_errors")
    by_product = product_scores.pivot(index="product_id", columns="model", values="wape")
    all_windows = query(db, "window_errors").pivot(index="origin", columns="model", values="wape")
    lines += ["", "## Product and window consistency", ""]
    for rival in scores.model:
        if rival != evaluation["champion"]:
            lines.append(f"- Champion strictly beats {rival} on WAPE for "
                         f"{int((by_product[evaluation['champion']] < by_product[rival]).sum())}/{len(by_product)} products and "
                         f"{int((all_windows[evaluation['champion']] < all_windows[rival]).sum())}/{len(all_windows)} windows.")
    product_scores.to_csv(ARTIFACTS / "product_comparison.csv", index=False)
    lines += ["", "## Window stability", "", *window_lines,
              "", "## Limits and interpretation", "",
              "- Recorded sales are not uncensored demand; zero records do not establish availability or closure.",
              "- One historical gift retailer, about one year, and a development-selected established-product cohort limit generalization.",
              "- The last recorded date is excluded by conservative policy; inventory is a user-input scenario with no real stock validation.",
              "- Unmatched duplicate-looking lines and large orders remain; only unambiguous same-day reversals are removed.",
              "- No calibrated prediction intervals, causal claims, service guarantees, or measured inventory savings.",
              "", "## Source", "", "Chen, D. (2015). Online Retail. UCI Machine Learning Repository. "
              "https://doi.org/10.24432/C5BW33. CC BY 4.0."]
    old_dir = ARTIFACTS / "history" / "v1"
    if (old_dir / "demandlens.sqlite").exists():
        old_scores = query(old_dir / "demandlens.sqlite", "model_metrics")
        with closing(sqlite3.connect((old_dir / "demandlens.sqlite").resolve().as_uri() + "?mode=ro", uri=True)) as conn:
            old_ids = {r[0] for r in conn.execute("SELECT product_id FROM products")}
        with closing(sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
            new_ids = {r[0] for r in conn.execute("SELECT product_id FROM products")}
        lines += ["", "## Original versus revised experiment", "",
                  "The original source bundle and report are archived in artifacts/history/v1. "
                  "The sales target and selected products changed after cancellation reconciliation. "
                  "Cross-version score differences cannot be attributed solely to a better model or compared as controlled improvement.",
                  "", f"Products removed from cohort: {', '.join(sorted(old_ids - new_ids)) or 'none'}.",
                  f"Products added to cohort: {', '.join(sorted(new_ids - old_ids)) or 'none'}.", "",
                  "| Original model | Original MAE | Original WAPE (%) |", "|---|---:|---:|"]
        lines += [f"| {r.model} | {r.mae:.3f} | {r.wape:.3f} |" for r in old_scores.itertuples()]
    (ARTIFACTS / "experiment_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def query_history(db, product, origin):
    with closing(sqlite3.connect(Path(db).resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        return pd.read_sql_query("SELECT date,units_sold FROM daily_sales WHERE product_id=? AND date<? ORDER BY date",
                                 conn, params=(product, origin))
