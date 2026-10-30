from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
ARTIFACTS = ROOT / "artifacts"
DEMO = ROOT / "demo"
SELECTION_CUTOFF = "2011-08-31"
FINAL_ORIGIN = "2011-12-09"
SOURCE_URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
SOURCE_PAGE = "https://archive.ics.uci.edu/dataset/352/online+retail"
SCHEMA_VERSION = 1
HORIZON = 7
# Version 1: known service, adjustment, and test codes, inspected in training only.
NON_MERCHANDISE = frozenset({
    "POST", "DOT", "M", "D", "C2", "BANK CHARGES", "AMAZONFEE", "CRUK",
    "S", "B", "PADS", "ADJUST", "ADJUST2", "TEST001", "TEST002",
})
