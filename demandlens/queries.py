"""Named read-only SQL, used by both the dashboard and reproducible reports."""
from pathlib import Path
import sqlite3
from contextlib import closing

import pandas as pd

QUERY_FILE = Path(__file__).resolve().parent.parent / "sql" / "analytics.sql"


def load_queries():
    text = QUERY_FILE.read_text(encoding="utf-8")
    queries = {}
    for section in text.split("-- name: ")[1:]:
        name, sql = section.split("\n", 1)
        queries[name.strip()] = sql.strip()
    return queries


def query(db, name, **parameters):
    parameters = {"product_id": None, "model": None, "split": "test", **parameters}
    with closing(sqlite3.connect(Path(db).resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        return pd.read_sql_query(load_queries()[name], conn, params=parameters)
