import pytest

from demandlens.inventory import inventory_scenario


def test_hand_calculated_scenario():
    result = inventory_scenario([10.] * 7, on_hand=20, inbound=10, safety_buffer=5)
    assert result["forecast_units"] == 40
    assert result["suggested_order"] == 15


def test_enough_stock_backorders_and_fractional_rounding():
    assert inventory_scenario([10.] * 7, on_hand=100)["suggested_order"] == 0
    assert inventory_scenario([10.] * 7, on_hand=20, backorders=5)["suggested_order"] == 25
    assert inventory_scenario([.1] * 7, on_hand=0)["suggested_order"] == 1


@pytest.mark.parametrize("changes", [{"on_hand": None}, {"on_hand": -1}, {"on_hand": 1.2},
                                    {"on_hand": True}, {"lead_time": 0}, {"lead_time": 6, "review_period": 2},
                                    {"safety_buffer": -1}, {"inbound": -1}, {"backorders": -1}])
def test_invalid_inputs(changes):
    with pytest.raises(ValueError):
        inventory_scenario([1.] * 7, **{"on_hand": 0, **changes})


@pytest.mark.parametrize("values", [[1.] * 6, [float("nan")] * 7, [-1.] * 7])
def test_invalid_forecast(values):
    with pytest.raises(ValueError):
        inventory_scenario(values, on_hand=0)
