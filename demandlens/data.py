"""Source acquisition and auditable, training-cutoff-only preparation."""
import hashlib
import json
import shutil
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .config import (ARTIFACTS, NON_MERCHANDISE, PROCESSED, RAW,
                     SELECTION_CUTOFF, SOURCE_PAGE, SOURCE_URL)

REQUIRED = {"InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate",
            "UnitPrice", "CustomerID", "Country"}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False, default=str), encoding="utf-8")


def download():
    RAW.mkdir(parents=True, exist_ok=True)
    target = RAW / "Online Retail.xlsx"
    if target.exists():
        return target
    archive = RAW / "online-retail.zip"
    if not archive.exists():
        print("Downloading original UCI workbook...", flush=True)
        try:
            urllib.request.urlretrieve(SOURCE_URL, archive)
        except Exception as exc:
            archive.unlink(missing_ok=True)
            raise ValueError("UCI download failed. Download the workbook from " + SOURCE_PAGE
                             + " and run: python -m demandlens prepare --input <workbook>") from exc
    with zipfile.ZipFile(archive) as z:
        entries = [n for n in z.namelist() if n.lower().endswith(".xlsx")]
        if len(entries) != 1:
            raise ValueError("Expected exactly one Excel workbook in the UCI archive.")
        with z.open(entries[0]) as source, target.open("wb") as dest:
            shutil.copyfileobj(source, dest)
    write_json(RAW / "retrieval.json", {
        "source_url": SOURCE_URL, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "workbook_sha256": sha256(target),
    })
    return target


def reconcile_same_day(raw):
    """Match only unique full reversals known before the next daily origin.

    Multiple same-key purchases/cancellations are ambiguous and untouched. No
    customer identifiers are retained in the returned audit. Cross-day and
    partial returns are intentionally outside this conservative policy.
    """
    x = pd.DataFrame(index=raw.index)
    x["customer"] = raw.CustomerID.astype("string").str.strip()
    x["product_id"] = raw.StockCode.astype("string").str.strip()
    x["timestamp"] = pd.to_datetime(raw.InvoiceDate, errors="coerce", format="mixed")
    x["date"] = x.timestamp.dt.normalize()
    q = pd.to_numeric(raw.Quantity, errors="coerce")
    x["units"] = q.abs()
    x["price"] = pd.to_numeric(raw.UnitPrice, errors="coerce")
    cancel_invoice = raw.InvoiceNo.astype("string").str.upper().str.startswith("C", na=False)
    valid = (x.customer.notna() & x.customer.ne("") & x.product_id.notna()
             & x.product_id.ne("") & x.timestamp.notna() & np.isfinite(q)
             & q.mod(1).eq(0) & q.ne(0) & np.isfinite(x.price) & x.price.gt(0))
    keys = ["customer", "product_id", "date", "units", "price"]
    purchases = x.loc[valid & q.gt(0) & ~cancel_invoice].copy()
    cancellations = x.loc[valid & q.lt(0) & cancel_invoice].copy()
    purchases["source_row"] = purchases.index
    cancellations["source_row"] = cancellations.index
    # Requiring uniqueness on each side prevents arbitrary choice or double consumption.
    purchases = purchases.loc[~purchases.duplicated(keys, keep=False)]
    cancellations = cancellations.loc[~cancellations.duplicated(keys, keep=False)]
    pairs = purchases.merge(cancellations, on=keys, suffixes=("_purchase", "_cancel"))
    pairs = pairs.loc[pairs.timestamp_cancel.gt(pairs.timestamp_purchase)]
    audit = pairs[["product_id", "date", "units", "price", "timestamp_purchase", "timestamp_cancel",
                   "source_row_purchase", "source_row_cancel"]].copy()
    audit["sales_value"] = audit.units * audit.price
    return audit.reset_index(drop=True)


def clean_transactions(raw):
    missing = REQUIRED - set(raw.columns)
    if missing:
        raise ValueError(f"Workbook is missing required columns: {', '.join(sorted(missing))}")
    d = raw.copy()
    d["product_id"] = d.StockCode.astype("string").str.strip()
    d["date"] = pd.to_datetime(d.InvoiceDate, errors="coerce", format="mixed").dt.normalize()
    d["quantity"] = pd.to_numeric(d.Quantity, errors="coerce")
    d["price"] = pd.to_numeric(d.UnitPrice, errors="coerce")
    invalid = (d.product_id.isna() | d.product_id.eq("") | d.date.isna()
               | ~np.isfinite(d.quantity) | ~np.isfinite(d.price)
               | d.quantity.mod(1).ne(0))
    cancelled = d.InvoiceNo.astype("string").str.upper().str.startswith("C", na=False) | d.quantity.lt(0)
    nonmerch = (d.product_id.str.upper().isin(NON_MERCHANDISE)
                | d.product_id.str.lower().str.startswith("gift_", na=False))
    matches = reconcile_same_day(raw)
    reversed_purchase = d.index.isin(matches.source_row_purchase)
    # One primary exclusion per row; overlapping diagnostic conditions remain separately counted.
    reason = pd.Series("retained", index=d.index)
    for name, mask in [("invalid_required_values", invalid), ("returns_or_cancellations", cancelled),
                       ("matched_same_day_reversal", reversed_purchase),
                       ("zero_quantity_or_nonpositive_price", d.quantity.eq(0) | d.price.le(0)),
                       ("non_merchandise", nonmerch)]:
        reason.loc[mask & reason.eq("retained")] = name
    last_date = d.date.max()
    if pd.isna(last_date):
        raise ValueError("Workbook contains no usable transaction dates.")
    reason.loc[d.date.eq(last_date) & reason.eq("retained")] = "final_recorded_date"
    d["exclusion_reason"] = reason
    sales = d.loc[reason.eq("retained")].copy()
    if sales.empty:
        raise ValueError("No valid sales remain after cleaning.")
    # Threshold is fitted using development data only; flagging never removes valid sales.
    train = sales.loc[sales.date.le(pd.Timestamp(SELECTION_CUTOFF))]
    large_threshold = float(train.quantity.quantile(.995)) if len(train) else None
    sales["large_order_flag"] = sales.quantity.gt(large_threshold) if large_threshold is not None else False
    returns = d.loc[~invalid & cancelled & ~nonmerch & d.date.lt(last_date)].copy()
    returns["return_units"] = returns.quantity.abs()
    returned = returns.groupby(["product_id", "date"], as_index=False).agg(
        return_units=("return_units", "sum"), cancellation_rows=("product_id", "size"))
    counts = reason.value_counts()
    remaining = len(raw)
    rules = []
    for name in ["invalid_required_values", "returns_or_cancellations", "matched_same_day_reversal",
                 "zero_quantity_or_nonpositive_price", "non_merchandise", "final_recorded_date"]:
        n = int(counts.get(name, 0))
        rules.append({"rule": name, "affected_rows": n, "before": remaining, "after": remaining - n})
        remaining -= n
    report = {
        "raw_rows": len(raw), "retained_sales_rows": len(sales),
        "missing_values": {c: int(raw[c].isna().sum()) for c in sorted(REQUIRED)},
        "duplicate_looking_rows_retained_by_policy": int(raw.duplicated().sum()),
        "retained_sales_duplicate_rows": int(raw.loc[sales.index].duplicated().sum()),
        "rules": rules, "source_start": str(d.date.min().date()),
        "source_end": str(last_date.date()), "complete_through_policy": str((last_date - pd.Timedelta(days=1)).date()),
        "large_order_threshold_training_p995": large_threshold,
        "large_sales_rows_retained": int(sales.large_order_flag.sum()),
        "non_merchandise_policy_version": 1,
        "non_merchandise_codes": sorted(NON_MERCHANDISE),
        "non_merchandise_prefixes": ["gift_"],
        "cleaning_policy_version": 2,
        "cancellation_policy": "Unique full same-day reversal; same known customer, product, quantity, price; cancellation strictly later; ambiguous/partial/cross-day returns remain separate.",
        "matched_reversal_pairs": len(matches),
        "matched_reversal_units": float(matches.units.sum()),
        "matched_merchandise_units_removed": float(d.loc[reversed_purchase & ~invalid & ~nonmerch & d.date.lt(last_date), "quantity"].sum()),
    }
    quarantine = d.loc[~reason.eq("retained"), ["product_id", "date", "quantity", "price", "exclusion_reason"]]
    return sales, returned, quarantine, report


def select_products(sales, cutoff=SELECTION_CUTOFF, limit=20):
    train = sales.loc[sales.date.le(pd.Timestamp(cutoff))].copy()
    stats = train.groupby("product_id").agg(
        first_sale=("date", "min"), positive_sales_days=("date", "nunique"),
        training_units=("quantity", "sum"))
    stats["history_days"] = (pd.Timestamp(cutoff) - stats.first_sale).dt.days + 1
    stats = stats.loc[(stats.history_days >= 180) & (stats.positive_sales_days >= 40) & (stats.training_units > 0)]
    stats = stats.reset_index().sort_values(["training_units", "product_id"], ascending=[False, True]).head(limit)
    # Mode over development descriptions, with deterministic lexical tie breaking.
    names = train.assign(description=train.Description.astype("string").str.strip()).dropna(subset=["description"])
    counts = names.loc[names.description.ne("")].groupby(["product_id", "description"]).size().reset_index(name="n")
    counts = counts.sort_values(["product_id", "n", "description"], ascending=[True, False, True]).drop_duplicates("product_id")
    stats = stats.merge(counts[["product_id", "description"]], how="left", on="product_id")
    stats["description"] = stats.description.fillna(stats.product_id)
    if stats.empty:
        raise ValueError("No products meet the frozen training-period eligibility criteria.")
    return stats


def daily_panel(sales, products, end_date):
    chosen = sales.loc[sales.product_id.isin(products.product_id)]
    agg = chosen.groupby(["product_id", "date"]).agg(
        units_sold=("quantity", "sum"),
        gross_sales_value=("line_value", "sum"),
        order_count=("InvoiceNo", "nunique"), large_order_rows=("large_order_flag", "sum"))
    pieces = []
    for row in products.itertuples(index=False):
        index = pd.date_range(row.first_sale, end_date, freq="D")
        part = agg.loc[row.product_id].reindex(index)
        part["inserted_zero"] = part.units_sold.isna().astype(int)
        part = part.fillna(0).rename_axis("date").reset_index()
        part["product_id"] = row.product_id
        pieces.append(part)
    return pd.concat(pieces, ignore_index=True)


def prepare(input_path=None):
    path = Path(input_path).resolve() if input_path else download()
    if not path.is_file():
        raise ValueError(f"Workbook not found: {path}")
    PROCESSED.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    print(f"Reading {path.name}...", flush=True)
    raw = pd.read_excel(path, engine="openpyxl", dtype={"InvoiceNo": "string", "StockCode": "string"})
    sales, returns, quarantine, report = clean_transactions(raw)
    reconciliation = reconcile_same_day(raw)
    sales["line_value"] = sales.quantity * sales.price
    products = select_products(sales)
    end = pd.Timestamp(report["complete_through_policy"])
    panel = daily_panel(sales, products, end)
    checksum = sha256(path)
    retrieved = None
    retrieval_path = RAW / "retrieval.json"
    if retrieval_path.exists():
        metadata = json.loads(retrieval_path.read_text())
        if metadata.get("workbook_sha256") == checksum:
            retrieved = metadata.get("retrieved_at_utc")
    report.update({"source_url": SOURCE_URL, "source_page": SOURCE_PAGE,
                   "doi": "10.24432/C5BW33", "license": "CC BY 4.0",
                   "workbook_sha256": checksum, "retrieved_at_utc": retrieved,
                   "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
                   "selection_cutoff": SELECTION_CUTOFF, "selected_products": len(products),
                   "selected_units_share": float(panel.units_sold.sum() / sales.quantity.sum())})
    overview = sales.groupby("date", as_index=False).agg(
        units_sold=("quantity", "sum"), gross_sales_value=("line_value", "sum"),
        large_order_rows=("large_order_flag", "sum"))
    merchandise_inspection = raw.loc[pd.to_datetime(raw.InvoiceDate, errors="coerce", format="mixed").le(pd.Timestamp(SELECTION_CUTOFF) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1))]
    merchandise_inspection.groupby("StockCode", dropna=False).size().rename("rows").to_csv(ARTIFACTS / "training_code_inspection.csv")
    for name, frame in [("products", products), ("daily_sales", panel), ("returns_daily", returns),
                        ("quarantine", quarantine), ("retail_daily", overview),
                        ("cancellation_matches", reconciliation)]:
        frame.to_parquet(PROCESSED / f"{name}.parquet", index=False)
    write_json(ARTIFACTS / "cleaning_report.json", report)
    print(f"Prepared {len(panel):,} daily rows across {len(products)} products; raw checksum {checksum[:12]}.", flush=True)
    return report
