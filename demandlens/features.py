"""Direct seven-horizon features. Origin D uses observed data only before D."""
import numpy as np
import pandas as pd

NUMERIC = ["horizon", "lag_1", "lag_7", "lag_14", "lag_28", "mean_7", "mean_14",
           "mean_28", "std_28", "positive_fraction_28", "trend_7",
           "weekday_sin", "weekday_cos", "month_sin", "month_cos"]
FEATURES = ["product_id"] + NUMERIC


def make_features(panel):
    pieces = []
    for product, frame in panel.groupby("product_id", sort=True):
        series = frame.set_index("date").units_sold.sort_index()
        # Append one unknown day to create the final forecast origin.
        series = series.reindex(pd.date_range(series.index.min(), series.index.max() + pd.Timedelta(days=1)))
        past = series.shift(1)
        base = pd.DataFrame(index=series.index)
        for lag in [1, 7, 14, 28]:
            base[f"lag_{lag}"] = series.shift(lag)
        for window in [7, 14, 28]:
            base[f"mean_{window}"] = past.rolling(window, min_periods=window).mean()
        base["median_28"] = past.rolling(28, min_periods=28).median()
        base["std_28"] = past.rolling(28, min_periods=28).std(ddof=0)
        base["positive_fraction_28"] = past.gt(0).astype(float).rolling(28).mean()
        base["trend_7"] = base.mean_7 - series.shift(8).rolling(7).mean()
        base = base.dropna().rename_axis("origin").reset_index()
        base["product_id"] = str(product)
        for horizon in range(1, 8):
            part = base.copy()
            part["horizon"] = horizon
            part["target_date"] = part.origin + pd.Timedelta(days=horizon - 1)
            weekday = part.target_date.dt.dayofweek
            month = part.target_date.dt.month - 1
            part["weekday_sin"] = np.sin(2 * np.pi * weekday / 7)
            part["weekday_cos"] = np.cos(2 * np.pi * weekday / 7)
            part["month_sin"] = np.sin(2 * np.pi * month / 12)
            part["month_cos"] = np.cos(2 * np.pi * month / 12)
            part["actual"] = series.reindex(part.target_date).to_numpy()
            part["seasonal_naive"] = series.reindex(part.target_date - pd.Timedelta(days=7)).to_numpy()
            part["weekday_mean4"] = np.column_stack([
                series.reindex(part.target_date - pd.Timedelta(days=7 * week)).to_numpy()
                for week in range(1, 5)
            ]).mean(axis=1)
            pieces.append(part)
    return pd.concat(pieces, ignore_index=True).sort_values(["origin", "product_id", "horizon"]).reset_index(drop=True)
