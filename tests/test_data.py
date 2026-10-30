import numpy as np
import pandas as pd
import pytest

from demandlens.data import clean_transactions, daily_panel, reconcile_same_day, select_products


def transaction(**changes):
    row = {"InvoiceNo": "100001", "StockCode": "12345", "Description": "A product",
           "Quantity": 2, "InvoiceDate": "2011-01-01", "UnitPrice": 3.,
           "CustomerID": None, "Country": "United Kingdom"}
    return {**row, **changes}


def test_cleaning_retains_missing_customer_duplicates_and_large_orders():
    rows = [transaction(), transaction(), transaction(Quantity=100000),
            transaction(InvoiceNo="C100002", Quantity=-2), transaction(StockCode="POST"),
            transaction(Quantity=0), transaction(UnitPrice=-1), transaction(InvoiceDate="bad"),
            transaction(StockCode=None), transaction(Quantity=1.5),
            transaction(InvoiceDate="2011-12-09")]
    sales, returns, quarantine, report = clean_transactions(pd.DataFrame(rows))
    assert len(sales) == 3
    assert sales.quantity.max() == 100000
    assert sales.CustomerID.isna().all()
    assert returns.return_units.sum() == 2
    assert report["retained_sales_duplicate_rows"] == 1
    assert len(quarantine) + len(sales) == len(rows)
    assert sum(x["affected_rows"] for x in report["rules"]) + len(sales) == len(rows)
    assert report["rules"][-1]["after"] == len(sales)


def test_schema_and_all_invalid_dates_fail():
    with pytest.raises(ValueError, match="required columns"):
        clean_transactions(pd.DataFrame({"Quantity": [1]}))
    with pytest.raises(ValueError, match="no usable"):
        clean_transactions(pd.DataFrame([transaction(InvoiceDate="bad")]))


def test_infinite_quantity_is_quarantined():
    sales, _, _, _ = clean_transactions(pd.DataFrame([
        transaction(Quantity=np.inf), transaction(), transaction(InvoiceDate="2011-12-09")]))
    assert len(sales) == 1


def selection_sales():
    dates = pd.date_range("2011-01-01", "2011-08-31", freq="3D")
    return pd.DataFrame([{"product_id": p, "date": d, "quantity": q, "Description": desc}
                         for p, q, desc in [("B", 1, "Beta"), ("A", 2, "Alpha")]
                         for d in dates])


def test_selection_names_and_order_ignore_future():
    sales = selection_sales()
    before = select_products(sales, limit=1)
    future = pd.DataFrame([{"product_id": "B", "date": pd.Timestamp("2011-10-01"),
                            "quantity": 10**9, "Description": "Future name"}])
    after = select_products(pd.concat([sales, future]), limit=1)
    pd.testing.assert_frame_equal(before, after)
    assert before.iloc[0].product_id == "A"
    assert before.iloc[0].description == "Alpha"


def test_calendar_insertion_and_determinism():
    sales = selection_sales()
    sales["line_value"], sales["InvoiceNo"], sales["large_order_flag"] = 10., "I", False
    products = select_products(sales)
    panel = daily_panel(sales, products, pd.Timestamp("2011-09-02"))
    assert panel.groupby("product_id").size().nunique() == 1
    assert panel.loc[panel.inserted_zero.eq(1), "units_sold"].eq(0).all()
    assert panel.loc[panel.inserted_zero.eq(0), "units_sold"].gt(0).all()
    assert not panel.duplicated(["product_id", "date"]).any()
    pd.testing.assert_frame_equal(panel, daily_panel(sales, products, pd.Timestamp("2011-09-02")))


def reversal_rows(**cancel_changes):
    return [transaction(InvoiceNo="541431", CustomerID=123, Quantity=74215,
                        InvoiceDate="2011-01-18 10:01:00", UnitPrice=1.04),
            transaction(InvoiceNo="C541433", CustomerID=123, Quantity=-74215,
                        InvoiceDate="2011-01-18 10:17:00", UnitPrice=1.04, **cancel_changes)]


def test_unique_same_day_reversal_removes_purchase_and_preserves_audit():
    raw = pd.DataFrame(reversal_rows() + [transaction(), transaction(InvoiceDate="2011-12-09")])
    audit = reconcile_same_day(raw)
    assert len(audit) == 1
    assert audit.iloc[0].units == 74215
    assert "customer" not in audit.columns
    sales, returns, quarantine, report = clean_transactions(raw)
    assert sales.quantity.sum() == 2
    assert returns.return_units.sum() == 74215
    assert report["matched_reversal_pairs"] == 1
    assert quarantine.exclusion_reason.eq("matched_same_day_reversal").sum() == 1
    assert sum(r["affected_rows"] for r in report["rules"]) + len(sales) == len(raw)


@pytest.mark.parametrize("column,value", [
    ("CustomerID", None), ("CustomerID", 999), ("Quantity", -10), ("UnitPrice", 1.05),
    ("StockCode", "99999"), ("InvoiceDate", "2011-01-19 10:17"),
    ("InvoiceDate", "2011-01-18 10:00"), ("InvoiceDate", "2011-01-18 10:01"),
    ("InvoiceNo", "123456"),
])
def test_ambiguous_partial_or_unavailable_reversals_are_not_matched(column, value):
    raw = pd.DataFrame(reversal_rows())
    raw.loc[1, column] = value
    assert reconcile_same_day(raw).empty


@pytest.mark.parametrize("duplicate_row", [0, 1])
def test_reversal_cannot_consume_duplicate_purchases_or_cancellations(duplicate_row):
    rows = reversal_rows()
    rows.append(rows[duplicate_row].copy())
    assert reconcile_same_day(pd.DataFrame(rows)).empty


def test_next_day_cancellation_cannot_revise_prior_day_sales():
    rows = reversal_rows()
    a = reconcile_same_day(pd.DataFrame(rows[:1]))
    rows[1]["InvoiceDate"] = "2011-01-19 00:01"
    b = reconcile_same_day(pd.DataFrame(rows))
    assert a.empty and b.empty
