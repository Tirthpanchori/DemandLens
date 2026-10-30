import numpy as np
import pandas as pd
import pytest

from demandlens.evaluation import choose_champion, predict_origin, score
from demandlens.features import FEATURES, make_features


def panel():
    return pd.DataFrame({"date": pd.date_range("2011-01-01", periods=100),
                         "product_id": "A", "units_sold": np.arange(100, dtype=float)})


def test_known_sequence_features_and_horizon_labels():
    features = make_features(panel())
    origin = pd.Timestamp("2011-02-10")  # day index 40
    rows = features.loc[features.origin.eq(origin)]
    first = rows.iloc[0]
    assert first.lag_1 == 39
    assert first.lag_7 == 33
    assert first.lag_28 == 12
    assert first.mean_7 == np.mean(np.arange(33, 40))
    assert first.mean_28 == np.mean(np.arange(12, 40))
    assert first.trend_7 == 7
    assert rows.actual.tolist() == list(range(40, 47))
    assert rows.seasonal_naive.tolist() == list(range(33, 40))


def test_future_mutation_cannot_change_origin_features_or_baselines():
    original = panel()
    origin = pd.Timestamp("2011-02-10")
    changed = original.copy()
    changed.loc[changed.date.ge(origin), "units_sold"] = 1000000.
    a, b = make_features(original), make_features(changed)
    columns = FEATURES + ["seasonal_naive", "median_28", "weekday_mean4"]
    pd.testing.assert_frame_equal(a.loc[a.origin.eq(origin), columns].reset_index(drop=True),
                                  b.loc[b.origin.eq(origin), columns].reset_index(drop=True))


def test_training_labels_do_not_cross_cutoff(monkeypatch):
    features = make_features(panel())
    origin = pd.Timestamp("2011-02-10")
    # Labels at or after origin are poisoned; fitting must never see them.
    features.loc[features.target_date.ge(origin), "actual"] = 1000000.

    class Spy:
        def fit(self, x, y):
            assert y.max() < 1000000
            return self

        def predict(self, x):
            return np.full(len(x), -2.)

    monkeypatch.setattr("demandlens.evaluation.estimator", lambda _: Spy())
    result, _ = predict_origin(features, origin, ["hgb_15"], "test")
    assert len(result) == 7
    assert result.prediction.eq(0).all()


def test_seven_baseline_predictions_and_unknown_final_actuals():
    features = make_features(panel())
    result, _ = predict_origin(features, "2011-04-11", ["seasonal_naive", "trailing_mean"], "final")
    assert len(result) == 14
    assert result.actual.isna().all()
    assert result.loc[result.model.eq("seasonal_naive"), "prediction"].tolist() == list(range(93, 100))


def test_missing_actuals_fail_evaluation():
    with pytest.raises(ValueError, match="Missing actual"):
        predict_origin(make_features(panel()), "2011-04-11", ["seasonal_naive"], "test")


def test_wape_zero_and_pooled_metric():
    assert score([0, 0], [1, 1])["wape"] is None
    assert score([0, 0], [1, 1])["mae"] == 1
    assert score([10, 90], [20, 90])["wape"] == 10
    with pytest.raises(ValueError):
        score([], [])


def test_validation_selects_champion_and_tie_prefers_simple_baseline():
    rows = pd.DataFrame([{"model": m, "actual": 10., "prediction": p}
                         for m, p in [("hgb_15", 12), ("hgb_31", 11),
                                      ("seasonal_naive", 11), ("trailing_mean", 11)]])
    champion, boosting, _ = choose_champion(rows)
    assert champion == "seasonal_naive"
    assert boosting == "hgb_31"


def test_median_and_four_week_weekday_arithmetic():
    features = make_features(panel())
    rows = features.loc[features.origin.eq(pd.Timestamp("2011-02-10"))]
    assert rows.median_28.eq(25.5).all()
    # For day index 40, earlier matching weekdays have indexes 33,26,19,12.
    assert rows.iloc[0].weekday_mean4 == 22.5
    assert rows.iloc[-1].weekday_mean4 == 28.5
    result, _ = predict_origin(features, "2011-02-10", ["trailing_median", "weekday_mean4"], "test")
    assert result.loc[result.model.eq("trailing_median"), "prediction"].eq(25.5).all()
    assert result.groupby("model").size().eq(7).all()


def test_simple_median_can_win_validation_without_ml_override():
    rows = pd.DataFrame([{"model": m, "actual": 10., "prediction": p}
                         for m, p in [("hgb_15", 12), ("hgb_31", 13),
                                      ("seasonal_naive", 14), ("trailing_mean", 11),
                                      ("trailing_median", 10), ("weekday_mean4", 11)]])
    champion, boosting, _ = choose_champion(rows)
    assert champion == "trailing_median"
    assert boosting == "hgb_15"
