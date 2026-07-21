from __future__ import annotations

import json


def test_json_module_preserves_float_precision() -> None:
    payload = {
        "cmp": 0.0048092317,
        "entry": 4.89321761,
        "risk_reward": 2.123456789,
    }

    encoded = json.dumps(payload, indent=2, default=str)
    decoded = json.loads(encoded)

    assert decoded == payload


def test_text_price_formatting_does_not_mutate_json_values() -> None:
    payload = {
        "price": 153.428191,
        "nested": {"price": 0.000047819123},
    }

    encoded = json.dumps(payload, indent=2, default=str)
    decoded = json.loads(encoded)

    assert decoded["price"] == 153.428191
    assert decoded["nested"]["price"] == 0.000047819123
