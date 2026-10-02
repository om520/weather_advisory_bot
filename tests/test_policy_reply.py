from app.policy_reply import render_policy_reply


def _state(primary, weather):
    return {
        "primary_sop": primary,
        "weather_values": weather,
        "config": {
            "weather_fields": {
                "apparent_temp_max_c": {"label": "highest feels-like temperature", "unit": "C"},
                "precip_day_sum_mm": {"label": "total rainfall for the day", "unit": "mm"},
            }
        },
        "geo_result": {"name": "Delhi"},
        "activity": "running",
        "time_window_label": "today",
    }


def test_heat_reply_shows_fetched_value_and_policy_threshold():
    sop = {
        "id": "HEAT-EXER-01",
        "guidance": "Move the exercise to early morning or late evening.",
        "conditions": {"all": [{"field": "apparent_temp_max_c", "op": ">=", "value": 38.0}]},
    }
    reply = render_policy_reply(_state(sop, {"apparent_temp_max_c": 40.7}))
    assert "40.7 C" in reply
    assert "38.0 C" in reply
    assert "Recommended (policy HEAT-EXER-01)" in reply


def test_rain_evidence_does_not_expose_raw_weather_codes():
    sop = {
        "id": "RAIN-SYS-01",
        "guidance": "Use waterproof footwear.",
        "conditions": {"any": [{"field": "precip_day_sum_mm", "op": ">=", "value": 5.0}]},
    }
    reply = render_policy_reply(_state(sop, {"precip_day_sum_mm": 78.2}))
    assert "78.2 mm" in reply
