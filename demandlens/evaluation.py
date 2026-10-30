"""Rolling-origin evaluation with validation-only model selection."""
import importlib.metadata
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from .config import ARTIFACTS, FINAL_ORIGIN, PROCESSED, SCHEMA_VERSION
from .data import sha256, write_json
from .features import FEATURES, NUMERIC, make_features

BASELINES = {"seasonal_naive": "seasonal_naive", "trailing_mean": "mean_28",
             "trailing_median": "median_28", "weekday_mean4": "weekday_mean4"}
MODEL_NAMES = list(BASELINES) + ["hgb_15", "hgb_31"]


def score(actual, prediction):
    actual, prediction = np.asarray(actual, dtype=float), np.asarray(prediction, dtype=float)
    if len(actual) == 0 or not np.isfinite(actual).all() or not np.isfinite(prediction).all():
        raise ValueError("Metrics require nonempty, finite actuals and predictions.")
    error = prediction - actual
    denominator = actual.sum()
    return {"mae": float(np.abs(error).mean()),
            "wape": float(100 * np.abs(error).sum() / denominator) if denominator > 0 else None,
            "bias": float(error.mean()), "actual_units": float(denominator), "n": len(actual)}


def choose_champion(validation):
    rows = []
    for model, frame in validation.groupby("model"):
        result = score(frame.actual, frame.prediction)
        rows.append({"model": model, **result})
    ranking = pd.DataFrame(rows)
    if ranking.wape.isna().all():
        raise ValueError("Validation actual sales sum to zero: cannot select by WAPE.")
    ranking["complexity"] = ranking.model.map({name: i for i, name in enumerate(MODEL_NAMES)})
    ranking = ranking.sort_values(["wape", "mae", "complexity"], na_position="last")
    boosting = ranking.loc[ranking.model.str.startswith("hgb_")].iloc[0].model
    eligible = ranking.loc[ranking.model.isin([*BASELINES, boosting])]
    return str(eligible.iloc[0].model), str(boosting), ranking.drop(columns="complexity")


def estimator(leaves):
    transform = ColumnTransformer([
        ("product", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["product_id"]),
        ("numeric", "passthrough", NUMERIC),
    ])
    return Pipeline([("features", transform), ("model", HistGradientBoostingRegressor(
        loss="squared_error", learning_rate=.05, max_iter=150, min_samples_leaf=20,
        l2_regularization=1., random_state=42, early_stopping=False, max_leaf_nodes=leaves))])


def predict_origin(features, origin, models, split):
    origin = pd.Timestamp(origin)
    train = features.loc[features.target_date.lt(origin) & features.actual.notna()]
    target = features.loc[features.origin.eq(origin)].copy()
    expected = features.product_id.nunique() * 7
    if len(target) != expected or train.empty:
        raise ValueError(f"Insufficient history for {origin.date()}: expected {expected} forecast rows.")
    if split != "final" and target.actual.isna().any():
        raise ValueError(f"Missing actual labels in {split} at {origin.date()}; evaluation is incomplete.")
    predictions, timings = [], []
    for model in models:
        trained = time.perf_counter()
        if model.startswith("hgb_"):
            fitted = estimator(int(model.split("_")[1]))
            fitted.fit(train[FEATURES], train.actual)
            training_seconds = time.perf_counter() - trained
            start = time.perf_counter()
            prediction = fitted.predict(target[FEATURES])
        elif model in BASELINES:
            training_seconds = 0.
            start = time.perf_counter()
            prediction = target[BASELINES[model]].to_numpy()
        else:
            raise ValueError(f"Unknown forecast model: {model}")
        prediction_seconds = time.perf_counter() - start
        result = target[["product_id", "origin", "target_date", "horizon", "actual"]].copy()
        if split == "final":
            result["actual"] = np.nan
        result["prediction"] = np.maximum(0., prediction)
        if not np.isfinite(result.prediction).all():
            raise ValueError(f"Non-finite predictions from {model}.")
        result["model"], result["split"] = model, split
        predictions.append(result)
        timings.append({"model": model, "origin": origin, "split": split,
                        "training_seconds": training_seconds, "prediction_seconds": prediction_seconds,
                        "training_rows": len(train), "forecast_rows": len(target)})
    return pd.concat(predictions, ignore_index=True), timings


def metric_table(predictions):
    rows = []
    known = predictions.loc[predictions.actual.notna()]
    levels = {"overall": [], "product": ["product_id"], "horizon": ["horizon"], "window": ["origin"]}
    for level, extra in levels.items():
        for keys, frame in known.groupby(["split", "model"] + extra):
            split, model, *value = keys
            measured = score(frame.actual, frame.prediction)
            for metric in ["mae", "wape", "bias"]:
                rows.append({"split": split, "model": model, "level": level,
                             "group_value": str(value[0]) if value else "all",
                             "metric": metric, "value": measured[metric]})
    for (split, model, product, origin), frame in known.groupby(["split", "model", "product_id", "origin"]):
        rows.append({"split": split, "model": model, "level": "product_window",
                     "group_value": f"{product}|{origin.date()}", "metric": "cumulative_absolute_error",
                     "value": float(abs(frame.prediction.sum() - frame.actual.sum()))})
    return pd.DataFrame(rows)


def evaluate():
    if not (PROCESSED / "daily_sales.parquet").exists():
        raise ValueError("Prepared data missing. Run: python -m demandlens prepare --input <workbook>")
    panel = pd.read_parquet(PROCESSED / "daily_sales.parquet")
    features = make_features(panel)
    report = json.loads((ARTIFACTS / "cleaning_report.json").read_text())
    if panel.date.max() != pd.Timestamp(FINAL_ORIGIN) - pd.Timedelta(days=1):
        raise ValueError("This MVP expects UCI history through 2011-12-08 after excluding the final date.")
    outputs, timings = [], []
    for split, origins in [
        ("validation", pd.date_range("2011-09-01", "2011-09-29", freq="7D")),
        ("test", pd.date_range("2011-10-06", "2011-12-01", freq="7D")),
        ("final", [pd.Timestamp(FINAL_ORIGIN)]),
    ]:
        models = MODEL_NAMES if split == "validation" else [*BASELINES, boosting]
        for origin in origins:
            print(f"{split}: forecasting {origin.date()} with {', '.join(models)}", flush=True)
            prediction, timing = predict_origin(features, origin, models, split)
            outputs.append(prediction)
            timings.extend(timing)
        if split == "validation":
            validation = pd.concat(outputs, ignore_index=True)
            champion, boosting, ranking = choose_champion(validation)
            selection = {"champion": champion, "boosting_model": boosting,
                         "selection_metric": "validation WAPE, then MAE, then baseline simplicity",
                         "validation_ranking": ranking.to_dict(orient="records"),
                         "selected_before_test": True}
            print(f"Frozen selection: champion={champion}, boosting={boosting}", flush=True)
    predictions = pd.concat(outputs, ignore_index=True)
    # Stable run identity binds predictions to source and code, not only the workbook.
    code_hash = hashlib.sha256("".join(sha256(p) for p in sorted(Path(__file__).parent.glob("*.py"))).encode()).hexdigest()
    run_id = report["workbook_sha256"][:12] + "-" + code_hash[:12]
    predictions["run_id"] = run_id
    predictions.to_parquet(PROCESSED / "forecasts.parquet", index=False)
    metric_table(predictions).to_parquet(PROCESSED / "metrics.parquet", index=False)
    pd.DataFrame(timings).to_parquet(PROCESSED / "timings.parquet", index=False)
    write_json(ARTIFACTS / "evaluation.json", {
        "schema_version": SCHEMA_VERSION, "run_id": run_id,
        "source_sha256": report["workbook_sha256"], "code_sha256": code_hash,
        "daily_sales_sha256": sha256(PROCESSED / "daily_sales.parquet"),
        "products_sha256": sha256(PROCESSED / "products.parquet"),
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "final_origin": FINAL_ORIGIN, **selection,
        "evaluation_status": "retrospective_revision",
        "revision_note": "Baseline additions and cancellation policy were motivated by inspecting the original test results. This is a retrospective benchmark, not a fresh untouched holdout.",
        "baseline_models": list(BASELINES),
        "model_parameters": estimator(int(boosting.split("_")[1])).named_steps["model"].get_params(),
        "compared_leaf_nodes": [15, 31],
        "packages": {p: importlib.metadata.version(p) for p in ["pandas", "numpy", "scikit-learn"]},
    })
    print(f"Evaluation complete. Champion: {champion}. Run: {run_id}", flush=True)
    return predictions
