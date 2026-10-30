from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from demandlens.config import DEMO, ROOT


@pytest.mark.skipif(not (DEMO / "manifest.json").exists(), reason="Real demo artifacts not yet generated")
def test_pages_and_inventory_form():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    assert not app.exception
    for page in ["Forecasts", "Inventory", "About the data", "Sales"]:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, str(app.exception)
    app.sidebar.radio[0].set_value("Inventory").run()
    assert app.number_input[0].value is None
    app.button[0].click().run()
    assert len(app.warning) >= 1
    app.number_input[0].set_value(20)
    app.button[0].click().run()
    assert not app.exception
    assert any(x.label == "Suggested order" for x in app.metric)
    app.number_input[1].set_value(6)
    app.number_input[2].set_value(2)
    app.button[0].click().run()
    assert len(app.error) == 1
