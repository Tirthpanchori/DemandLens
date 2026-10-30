import math
from numbers import Integral, Real


def inventory_scenario(forecast, *, on_hand, lead_time=3, review_period=1,
                       inbound=0, backorders=0, safety_buffer=0):
    """Order-up-to scenario; inbound must be available before protection day one."""
    inputs = {"on_hand": on_hand, "lead_time": lead_time, "review_period": review_period,
              "inbound": inbound, "backorders": backorders, "safety_buffer": safety_buffer}
    for name, value in inputs.items():
        if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
            raise ValueError(f"{name.replace('_', ' ')} must be a nonnegative integer.")
    if lead_time < 1 or review_period < 1 or lead_time + review_period > 7:
        raise ValueError("Lead time and review period must each be at least 1; their sum cannot exceed 7 days.")
    values = list(forecast)
    if len(values) != 7 or any(isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("Supply exactly seven finite, nonnegative daily sales forecasts.")
    expected = float(sum(values[:lead_time + review_period]))
    position = on_hand + inbound - backorders
    target = expected + safety_buffer
    return {**inputs, "protection_days": lead_time + review_period,
            "forecast_units": expected, "inventory_position": position,
            "target_stock": target, "suggested_order": math.ceil(max(0., target - position))}
