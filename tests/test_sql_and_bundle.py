import sqlite3

import numpy as np
import pandas as pd
import pytest

from demandlens.config import DEMO
from demandlens.queries import query
from demandlens.storage import load_bundle


def test_sql_metrics_equal_pandas_and_parameterized_filters(tmp_path):
    db = tmp_path / "analytics.sqlite"
    frame = pd.DataFrame({"product_id": ["A", "A", "B"], "model": "m", "split": "test",
                          "actual": [0., 10., 90.], "prediction": [2., 8., 100.]})
    with sqlite3.connect(db) as conn:
        frame.to_sql("forecasts", conn, index=False)
    result = query(db, "model_metrics").iloc[0]
    assert result.mae == pytest.approx(np.abs(frame.prediction - frame.actual).mean())
    assert result.wape == pytest.approx(14.)
    assert query(db, "model_metrics", product_id="A").iloc[0].observations == 2
    assert query(db, "model_metrics", product_id="A' OR 1=1 --").empty


def test_calendar_week_query_handles_zero_week_and_variability(tmp_path):
    db = tmp_path / "analytics.sqlite"
    dates = pd.date_range("2011-01-03", periods=21)
    frame = pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "product_id": "A",
                          "units_sold": [1.] * 7 + [0.] * 7 + [2.] * 7, "gross_sales_value": 1.})
    with sqlite3.connect(db) as conn:
        frame.to_sql("daily_sales", conn, index=False)
    weekly = query(db, "weekly_sales")
    assert weekly.units_sold.tolist() == [7, 0, 14]
    assert pd.isna(weekly.iloc[2].wow_percent)
    assert query(db, "variability").iloc[0].variance_units == pytest.approx(frame.units_sold.var(ddof=0))


def test_missing_bundle_has_rebuild_instruction(tmp_path):
    with pytest.raises(ValueError, match="publish-demo"):
        load_bundle(tmp_path)


@pytest.mark.skipif(not (DEMO / "manifest.json").exists(), reason="Real demo artifacts not yet generated")
def test_real_bundle_integrity_and_unique_forecasts():
    manifest = load_bundle()
    assert manifest["bundle_bytes"] < 10_000_000
    with sqlite3.connect((DEMO / "demandlens.sqlite").resolve().as_uri() + "?mode=ro", uri=True) as conn:
        frame = pd.read_sql_query("SELECT * FROM forecasts", conn)
        assert not frame.duplicated(["run_id", "model", "split", "origin", "product_id", "horizon"]).any()
        assert frame.loc[frame.split.eq("final"), "actual"].isna().all()
        assert frame.loc[frame.split.ne("final"), "actual"].notna().all()
        assert frame.groupby(["model", "split", "origin", "product_id"]).size().eq(7).all()
        assert frame.prediction.ge(0).all()
        metrics = query(DEMO / "demandlens.sqlite", "model_metrics")
        assert len(metrics) == 5
        assert {"trailing_median", "weekday_mean4"}.issubset(set(metrics.model))
        matches = pd.read_sql_query("SELECT * FROM cancellation_matches", conn)
        assert "customer" not in matches.columns
        assert not matches.source_row_purchase.duplicated().any()
        assert not matches.source_row_cancel.duplicated().any()


@pytest.mark.skipif(not (DEMO / "manifest.json").exists(), reason="Real demo artifacts not yet generated")
def test_bundle_tamper_detection(tmp_path):
    import shutil
    for path in DEMO.iterdir():
        shutil.copy(path, tmp_path / path.name)
    with (tmp_path / "cleaning_report.json").open("a") as stream:
        stream.write(" ")
    with pytest.raises(ValueError, match="checksum"):
        load_bundle(tmp_path)
