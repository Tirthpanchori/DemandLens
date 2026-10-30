"""Build an executed, standard Jupyter notebook without requiring a notebook server.

Cells use the reusable prepared data and SQL bundle. Plotly figures are embedded
with their native MIME representation, and printed results are captured per cell.
"""
import contextlib
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def build():
    from plotly.utils import PlotlyJSONEncoder

    cells = []
    namespace = {"__name__": "__main__", "PROJECT_ROOT": ROOT}

    def markdown(text):
        cells.append({"cell_type": "markdown", "id": f"cell-{len(cells)}", "metadata": {}, "source": text.splitlines(keepends=True)})

    def code(source, figure=None):
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            exec(compile(source, "<notebook>", "exec"), namespace)
        outputs = []
        if capture.getvalue():
            outputs.append({"output_type": "stream", "name": "stdout", "text": capture.getvalue().splitlines(keepends=True)})
        if figure:
            fig = namespace[figure]
            fig.update_layout(template="plotly_white", colorway=["#127567", "#dd8a38"])
            payload = json.loads(json.dumps(fig.to_plotly_json(), cls=PlotlyJSONEncoder))
            outputs.append({"output_type": "display_data", "data": {
                "application/vnd.plotly.v1+json": payload, "text/plain": ["Plotly figure"]}, "metadata": {}})
        cells.append({"cell_type": "code", "id": f"cell-{len(cells)}", "metadata": {},
                      "execution_count": sum(c["cell_type"] == "code" for c in cells) + 1,
                      "source": source.splitlines(keepends=True), "outputs": outputs})

    markdown("# DemandLens sales analysis\n\nAn executed analysis of real UCI Online Retail transactions using the shared preparation pipeline. "
             "Forecast target: positive recorded units after unambiguous same-day reversals, not unconstrained demand. Source: Chen (2015), "
             "https://doi.org/10.24432/C5BW33, CC BY 4.0.\n\nRun prepare, evaluate, and publish-demo before rerunning this notebook.")
    code('''from pathlib import Path
import json
import sys
import pandas as pd
import plotly.express as px
ROOT = Path.cwd() if (Path.cwd() / 'demandlens').exists() else Path.cwd().parent
sys.path.insert(0, str(ROOT))
from demandlens.config import PROCESSED, DEMO, ARTIFACTS
from demandlens.queries import query
from demandlens.storage import load_bundle
manifest = load_bundle()
audit = json.loads((ARTIFACTS / 'cleaning_report.json').read_text())
sales = pd.read_parquet(PROCESSED / 'daily_sales.parquet')
retail = pd.read_parquet(PROCESSED / 'retail_daily.parquet')
products = pd.read_parquet(PROCESSED / 'products.parquet')
print(f"Source rows: {audit['raw_rows']:,}; retained positive sales rows: {audit['retained_sales_rows']:,}")
print(f"Products: {len(products)}; daily rows: {len(sales):,}; history: {sales.date.min().date()} to {sales.date.max().date()}")
''')
    markdown("## Missingness and exclusions\n\nMissing customer IDs do not remove valid sales. Counts below are measured, not copied from repository metadata. Exclusions reconcile sequentially.")
    code('''print(pd.Series(audit['missing_values'], name='missing').to_string())
print(pd.DataFrame(audit['rules']).to_string(index=False))
print('Duplicate-looking source rows (retained unless another rule excludes them):', audit['duplicate_looking_rows_retained_by_policy'])
print('Training-only 99.5th-percentile quantity threshold:', audit['large_order_threshold_training_p995'])
print('Flagged large-order lines retained:', audit['large_sales_rows_retained'])
print('Unique full same-day reversal pairs:', audit['matched_reversal_pairs'])
print('Merchandise units removed before final boundary:', audit['matched_merchandise_units_removed'])
''')
    markdown("## Retail sales and returns\n\nThe chart uses all cleaned merchandise sales. Unique same-day full reversals remove the original purchase; other return quantities remain separate.")
    code('''fig = px.line(retail, x='date', y='units_sold', title='All cleaned retail recorded units')
returns = pd.read_parquet(PROCESSED / 'returns_daily.parquet')
print('Absolute returned/cancelled units:', returns.return_units.sum())
print('Selected cohort share of cleaned units:', round(audit['selected_units_share'], 4))
fig
''', figure="fig")
    markdown("## Cohort and concentration\n\nEligibility and names are frozen through 31 August 2011. This is an established-product cohort, not all products.")
    code('''print(products[['product_id','description','training_units','positive_sales_days','history_days']].to_string(index=False))
top = query(DEMO / 'demandlens.sqlite', 'top_products')
fig = px.bar(top.head(10), x='product_id', y='units_sold', title='Top ten products within selected cohort')
fig
''', figure="fig")
    markdown("## Weekday patterns, zero-sales days, and variability\n\nInserted calendar dates are zero recorded sales. The data does not establish store closures or stock availability.")
    code('''weekday = query(DEMO / 'demandlens.sqlite', 'weekday_sales')
fig = px.bar(weekday, x='weekday', y='average_units', title='Average recorded units; Monday = 0')
print(query(DEMO / 'demandlens.sqlite', 'zero_sales').to_string(index=False))
print(query(DEMO / 'demandlens.sqlite', 'variability').to_string(index=False))
fig
''', figure="fig")
    markdown("## Period changes and large-order spikes\n\nDifferences are descriptive associations. Price changes, promotions, and stockouts are not identified as causes.")
    code('''period = sales.assign(period=sales.date.map(lambda d: 'development' if d <= pd.Timestamp('2011-08-31') else 'validation' if d <= pd.Timestamp('2011-10-05') else 'test_and_final_history'))
print(period.groupby('period').agg(days=('date','nunique'), units=('units_sold','sum'), mean_daily_product_units=('units_sold','mean')).to_string())
print(sales.loc[sales.large_order_rows.gt(0)].nlargest(10, 'units_sold')[['product_id','date','units_sold','large_order_rows']].to_string(index=False))
''')
    markdown("## Revised retrospective results\n\nValidation selects the model within this revision. Changes were informed by the earlier test audit, so these results are not a fresh untouched holdout. Zero actual totals produce unavailable WAPE.")
    code('''print('Validation-selected champion:', manifest['champion'])
print(query(DEMO / 'demandlens.sqlite', 'model_metrics').to_string(index=False))
print(query(DEMO / 'demandlens.sqlite', 'worst_predictions', model=manifest['champion']).head(3).to_string(index=False))
''')
    markdown("## Interpretation\n\nOne historical gift retailer and a development-selected cohort limit generalization. "
             "Valid large orders remain and can drive large errors. Forecasts are not calibrated intervals. "
             "Inventory scenarios use supplied stock and lead-time assumptions, with no measured savings claims. "
             "See the generated experiment report for the measured comparison and three observed failure cases.")
    notebook = {"nbformat": 4, "nbformat_minor": 5, "metadata": {
        "kernelspec": {"display_name": "Python 3.11", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11.9"}}, "cells": cells}
    destination = ROOT / "notebooks" / "01_sales_analysis.ipynb"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(notebook, indent=1), encoding="utf-8")
    print(f"Built executed notebook: {destination.name} ({len(cells)} cells)")


if __name__ == "__main__":
    build()
