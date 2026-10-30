"""DemandLens dashboard: plain-language views over precomputed artifacts."""
import json
from contextlib import closing
import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st

from demandlens.config import DEMO
from demandlens.inventory import inventory_scenario
from demandlens.queries import query
from demandlens.storage import load_bundle

st.set_page_config(page_title="DemandLens", page_icon="◈", layout="wide")
st.markdown("""<style>
.block-container {padding-top:4.5rem;max-width:1250px;}
[data-testid="stSidebar"] {border-right:1px solid #e2e8f0;}
[data-testid="stMetric"] {background:#f4f7f8;border:1px solid #e1e8eb;border-radius:10px;padding:16px;}
h1 {letter-spacing:-.04em;} h2,h3 {letter-spacing:-.02em;}
div[data-testid="stDownloadButton"] button {border-color:#127567;color:#127567;}
</style>""", unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def checked_manifest(manifest_text, database_mtime):
    return load_bundle()

@st.cache_data(show_spinner=False)
def table(name, bundle_key):
    if name not in {"products", "daily_sales", "forecasts", "timings", "returns_daily"}:
        raise ValueError("Unknown table")
    with closing(sqlite3.connect((DEMO / "demandlens.sqlite").resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        return pd.read_sql_query(f"SELECT * FROM {name}", conn)

MODEL_LABELS = {"seasonal_naive": "Previous week's sales", "trailing_mean": "28-day average",
                "trailing_median": "28-day median", "weekday_mean4": "Four-week weekday average",
                "hgb_15": "Gradient boosting", "hgb_31": "Gradient boosting (larger model)"}
COLUMNS = {"product_id": "Product code", "description": "Product", "date": "Date",
           "week": "Week starting", "units_sold": "Recorded units", "gross_sales_value": "Sales value (£)",
           "previous_units": "Previous week (units)", "wow_percent": "Weekly change (%)",
           "model": "Model", "mae": "Average error (units)", "wape": "Total error (%)",
           "bias": "Average overprediction (units)", "origin": "Forecast starting",
           "target_date": "Date", "actual": "Recorded units", "prediction": "Forecast units",
           "horizon": "Forecast day", "absolute_error": "Error (units)",
           "cumulative_absolute_error": "Weekly total error (units)"}

def readable(frame):
    result = frame.copy()
    if "model" in result:
        result["model"] = result.model.map(MODEL_LABELS).fillna(result.model)
    return result.rename(columns=COLUMNS)

def download(frame, label, filename):
    st.download_button(label, readable(frame).to_csv(index=False).encode("utf-8"), filename, "text/csv")

def chart(fig):
    fig.update_layout(template="plotly_white", font_family="Arial",
                      margin=dict(l=8, r=16, t=15, b=10), legend_title_text="",
                      legend=dict(orientation="h", y=1.1, x=0))
    colors = ["#127567", "#dd8a38", "#617b96", "#b56473"]
    for i, trace in enumerate(fig.data):
        if trace.type == "scatter":
            trace.line.color = colors[i % len(colors)]
            trace.marker.color = colors[i % len(colors)]
        elif trace.type == "bar":
            trace.marker.color = colors[i % len(colors)]
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "displayModeBar": "hover"})

def data_grid(frame):
    display = readable(frame)
    decimals = display.select_dtypes(include="floating").columns
    display[decimals] = display[decimals].round(2)
    st.dataframe(display, width="stretch", hide_index=True)

try:
    manifest = checked_manifest((DEMO / "manifest.json").read_text(encoding="utf-8"),
                                (DEMO / "demandlens.sqlite").stat().st_mtime_ns)
    cleaning = json.loads((DEMO / "cleaning_report.json").read_text(encoding="utf-8"))
    evaluation = json.loads((DEMO / "evaluation.json").read_text(encoding="utf-8"))
except (ValueError, OSError) as exc:
    st.title("DemandLens")
    st.error("The sample data could not be loaded.")
    with st.expander("Setup instructions"):
        st.code("python -m demandlens prepare\npython -m demandlens evaluate\npython -m demandlens publish-demo")
        st.caption(str(exc))
    st.stop()

run_id = manifest["run_id"]
bundle_key = manifest["files"]["demandlens.sqlite"]
db = DEMO / "demandlens.sqlite"
products = table("products", bundle_key)
sales = table("daily_sales", bundle_key)
forecasts = table("forecasts", bundle_key)
champion = manifest["champion"]
names = dict(zip(products.product_id, products.description.str.title()))
duplicate_ids = set(products.loc[products.description.str.title().duplicated(keep=False), "product_id"])

with st.sidebar:
    st.markdown("## DemandLens")
    st.caption("Retail planning")
    page = st.radio("Navigation", ["Sales", "Forecasts", "Inventory", "About the data"],
                    label_visibility="collapsed")
    st.divider()
    product = st.selectbox("Product", products.product_id.tolist(),
                           format_func=lambda p: f"{names[p]} ({p})" if p in duplicate_ids else names[p])
    st.caption("Historical sample · 2010–2011")

selected = sales.loc[sales.product_id.eq(product)].copy()
selected["date"] = pd.to_datetime(selected.date)
future = forecasts.loc[(forecasts.split == "final") & (forecasts.model == champion)
                       & (forecasts.product_id == product)].sort_values("horizon")

if page == "Sales":
    st.title("Sales overview")
    st.write(names[product])
    st.caption("Recorded sales after removing clearly matched same-day cancellations.")
    cols = st.columns(4)
    cols[0].metric("Recorded units", f"{selected.units_sold.sum():,.0f}")
    cols[1].metric("Sales value", f"£{selected.gross_sales_value.sum():,.0f}")
    cols[2].metric("Daily average", f"{selected.units_sold.mean():,.1f}")
    cols[3].metric("Days with no sales", f"{100*selected.units_sold.eq(0).mean():.1f}%")
    st.caption(f"Summary covers {selected.date.min():%d %b %Y} – {selected.date.max():%d %b %Y}.")
    st.subheader("Daily sales")
    period = st.segmented_control("Chart period", ["Last 90 days", "Last 180 days", "All history"],
                                  default="Last 90 days")
    smooth = selected.assign(rolling_28=selected.units_sold.rolling(28).mean())
    if period != "All history":
        days = 180 if period == "Last 180 days" else 90
        smooth = smooth.loc[smooth.date.ge(smooth.date.max() - pd.Timedelta(days=days - 1))]
    display = smooth.rename(columns={"units_sold": "Daily sales", "rolling_28": "28-day average"})
    chart(px.line(display, x="date", y=["Daily sales", "28-day average"],
                  labels={"value": "Units", "date": "Date"}))
    if period == "All history":
        st.caption("Large orders can flatten the chart. Drag to zoom into a shorter period.")
    left, right = st.columns(2)
    with left:
        st.subheader("Sales by weekday")
        weekdays = query(db, "weekday_sales", product_id=product)
        weekdays["day"] = weekdays.weekday.map(dict(enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])))
        chart(px.bar(weekdays, x="day", y="average_units", labels={"day": "", "average_units": "Average units"}))
    with right:
        st.subheader("Top products")
        top = query(db, "top_products").head(10)
        top["name"] = top.description.str.title().map(lambda x: x if len(x) <= 32 else x[:29] + "…")
        chart(px.bar(top, x="units_sold", y="name", orientation="h", hover_data=["description"],
                     labels={"units_sold": "Recorded units", "name": "", "description": "Product"})
              .update_yaxes(autorange="reversed", tickfont_size=11))
    with st.expander("Weekly sales"):
        weekly = query(db, "weekly_sales", product_id=product).drop(columns="product_id")
        data_grid(weekly)
        st.caption("Weeks start on Monday. The first and last weeks may be incomplete.")
        download(weekly, "Download weekly sales", f"{product}-weekly-sales.csv")
    with st.expander("Returns and large orders"):
        returns = table("returns_daily", bundle_key)
        returns = returns.loc[returns.product_id.eq(product)]
        if returns.empty:
            st.write("No return or cancellation records for this product.")
        else:
            chart(px.bar(returns, x="date", y="return_units",
                         labels={"date": "Date", "return_units": "Returned or cancelled units"}))
        st.caption("Dates containing unusually large orders")
        data_grid(selected.loc[selected.large_order_rows.gt(0), ["date", "units_sold"]])

elif page == "Forecasts":
    st.title("Sales forecast")
    st.write(names[product])
    st.caption("9–15 December 2011 · Uses sales recorded through 8 December.")
    st.caption("Historical estimates · Revised retrospective evaluation.")
    chart(px.line(future, x="target_date", y="prediction", markers=True,
                  labels={"target_date": "Date", "prediction": "Forecast units"}))
    with st.expander("Daily estimates"):
        export = future[["target_date", "prediction"]]
        data_grid(export)
        download(export, "Download forecast", f"{product}-forecast.csv")
    st.subheader("How the models compare")
    scope = st.radio("Compare results for", ["All products", "This product"], horizontal=True)
    scope_product = product if scope == "This product" else None
    metrics = query(db, "model_metrics", product_id=scope_product)
    data_grid(metrics[["model", "mae", "wape"]])
    st.caption("Lower error is better. Results cover seven-day forecasts made during October–December 2011.")
    st.caption("The selected median method can miss large orders and underestimate total sales. Inventory outputs remain planning scenarios.")
    with st.expander("What do these errors mean?"):
        st.write("Average error is the average number of units each daily forecast missed by. Total error compares all absolute errors with total recorded sales. It is not an accuracy percentage.")
        st.write("The comparison includes average, median, weekday-based, and machine-learning forecasts. The selected method has the lowest validation error. Changes were informed by an earlier audit, so these are retrospective results, not a fresh unseen test.")
    with st.expander("Detailed results"):
        download(metrics, "Download comparison", "model-comparison.csv")
        models = sorted(forecasts.loc[forecasts.split.eq("test"), "model"].unique())
        model = st.selectbox("Model", models, index=models.index(champion),
                             format_func=lambda m: MODEL_LABELS.get(m, m))
        history = forecasts.loc[(forecasts.split == "test") & (forecasts.product_id == product)
                                & (forecasts.model == model)]
        origin = st.selectbox("Week starting", sorted(history.origin.unique()))
        window = history.loc[history.origin.eq(origin)].sort_values("horizon")
        plot = window.rename(columns={"actual": "Recorded sales", "prediction": "Forecast"})
        chart(px.line(plot, x="target_date", y=["Recorded sales", "Forecast"], markers=True,
                      labels={"value": "Units", "target_date": "Date"}))
        data_grid(query(db, "horizon_errors", product_id=scope_product, model=model))
        data_grid(query(db, "window_errors", product_id=scope_product, model=model))
        data_grid(query(db, "worst_predictions", product_id=scope_product, model=model)
                  .drop(columns=["product_id", "model"]))

elif page == "Inventory":
    st.title("Inventory planner")
    st.write(names[product])
    st.caption("Estimate a reorder quantity using the historical forecast and your stock assumptions.")
    with st.form("inventory"):
        left, right = st.columns(2)
        with left:
            stock = st.number_input("Stock available (units)", min_value=0, value=None, step=1,
                                    placeholder="Enter stock")
            lead = st.number_input("Delivery time (days)", min_value=1, max_value=6, value=3, step=1,
                                   help="Days between placing and receiving an order.")
            review = st.number_input("Review stock every (days)", min_value=1, max_value=6, value=1, step=1)
        with right:
            with st.expander("More stock options"):
                inbound = st.number_input("Incoming stock (units)", min_value=0, value=0, step=1,
                                          help="Include only stock available before 9 December 2011.")
                backlog = st.number_input("Unfulfilled orders (units)", min_value=0, value=0, step=1)
                buffer = st.number_input("Extra stock buffer (units)", min_value=0, value=0, step=1)
        submitted = st.form_submit_button("Calculate order", type="primary")
    if submitted:
        st.session_state.pop("inventory_result", None)
        if stock is None:
            st.warning("Enter your available stock first.")
        else:
            try:
                result = inventory_scenario(future.prediction.tolist(), on_hand=stock, lead_time=lead,
                                            review_period=review, inbound=inbound, backorders=backlog,
                                            safety_buffer=buffer)
                st.session_state["inventory_result"] = {"product_id": product, "model": champion,
                                                       "run_id": run_id, **result}
            except ValueError:
                st.error("Delivery time plus the review period must be seven days or less.")
    result = st.session_state.get("inventory_result")
    if result and result["product_id"] == product and result["run_id"] == run_id:
        cols = st.columns(3)
        cols[0].metric("Expected sales", f"{result['forecast_units']:.1f} units")
        cols[1].metric("Stock after commitments", f"{result['inventory_position']:,} units")
        cols[2].metric("Suggested order", f"{result['suggested_order']:,} units")
        with st.expander("How this is calculated"):
            st.write(f"Cover {result['protection_days']} days: {result['lead_time']} for delivery and {result['review_period']} until the next stock review.")
            st.write(f"Stock after commitments: {result['on_hand']} available + {result['inbound']} incoming − {result['backorders']} unfulfilled = {result['inventory_position']} units.")
            st.write(f"Target stock: {result['forecast_units']:.2f} expected sales + {result['safety_buffer']} buffer. Order the shortfall, rounded up to whole units.")
        export = pd.DataFrame([{"Product": names[product], "Forecast period": "From 9 December 2011",
                                "Days covered": result["protection_days"],
                                "Expected units": result["forecast_units"],
                                "Stock after commitments": result["inventory_position"],
                                "Extra buffer": result["safety_buffer"],
                                "Suggested order": result["suggested_order"]}])
        download(export, "Download estimate", f"{product}-inventory.csv")
    st.caption("Planning scenario only. Actual stock and supplier data are not included, and stock availability is not guaranteed.")

else:
    st.title("About the data")
    st.write("A historical retail forecasting project using transactions from a UK online retailer.")
    st.markdown("**Source:** [UCI Online Retail](https://doi.org/10.24432/C5BW33) · December 2010–December 2011 · CC BY 4.0")
    st.write("Clearly matched same-day cancellations are removed from sales. Other returns remain separate. Missing transaction dates mean zero recorded sales; actual stock availability is unknown.")
    with st.expander("Data cleaning"):
        audit = pd.DataFrame(cleaning["rules"])
        audit["rule"] = audit.rule.map({"invalid_required_values": "Invalid required values",
                                       "returns_or_cancellations": "Returns and cancellations",
                                       "matched_same_day_reversal": "Matched same-day reversed purchases",
                                       "zero_quantity_or_nonpositive_price": "Zero quantity or invalid price",
                                       "non_merchandise": "Non-product transactions",
                                       "final_recorded_date": "Final date (possibly incomplete)"})
        data_grid(audit.rename(columns={"rule": "Exclusion", "affected_rows": "Rows",
                                        "before": "Before", "after": "After"}))
        st.write("A cancellation removes a purchase only when the customer, product, quantity, and price match uniquely, and it occurs later on the same day. Partial, ambiguous, and later-day returns stay separate. Missing customer IDs do not remove valid sales. Unmatched large orders remain. The final recorded date is excluded because it may be incomplete.")
        st.caption(f"{cleaning.get('matched_reversal_pairs', 0):,} unique same-day reversal pairs identified in the source workbook.")
        download(audit.rename(columns={"rule": "Exclusion", "affected_rows": "Rows",
                                       "before": "Before", "after": "After"}),
                 "Download cleaning report", "cleaning-report.csv")
    with st.expander("How forecasts are evaluated"):
        st.write("Products are selected using data through August 2011. September forecasts select the model. October–December forecasts measure its performance. Each forecast uses only earlier recorded sales.")
        st.write("We compare the previous week's sales, 28-day average and median, four-week weekday average, and gradient boosting. Validation selects the serving method, even if a simple baseline wins.")
        st.write("This revision followed inspection of the original test results. October–December comparisons are retrospective; they are not a fresh untouched holdout.")
        st.write("One retailer, unknown stockouts, promotions, and large wholesale orders limit the conclusions. Inventory estimates use your assumptions rather than real warehouse records.")
    with st.expander("Technical details"):
        st.write(f"Selected product code: {product}")
        st.write(f"Forecast model: {MODEL_LABELS.get(champion, champion)}")
        st.caption(f"Experiment: {run_id}")
        st.json({"source_rows": cleaning["raw_rows"], "products": cleaning["selected_products"],
                 "source_sha256": cleaning["workbook_sha256"], "configuration": evaluation}, expanded=False)

st.divider()
st.caption("UCI Online Retail · CC BY 4.0")

