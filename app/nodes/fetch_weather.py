"""fetch_weather.py — Node 3: fetch forecast + compute weather values."""

from datetime import datetime
from app.weather import fetch_forecast, compute_weather_values


def fetch_weather_node(state: dict) -> dict:
    """
    Fetch the Open-Meteo forecast and aggregate values for the time window.
    Sets weather_values, time_window_label, raw_forecast, weather_failed.
    """
    geo = state["geo_result"]
    cfg = state["config"]

    raw = fetch_forecast(geo["latitude"], geo["longitude"], cfg)
    if raw is None:
        return {**state, "weather_failed": True, "raw_forecast": None,
                "weather_values": {}, "time_window_label": "today"}

    values, label = compute_weather_values(raw, cfg, state.get("time_ref", "today"))
    
    # Add metadata to snapshot for frontend rendering
    parts = [geo.get("name", ""), geo.get("admin1", ""), geo.get("country", "")]
    values["resolved_location"] = ", ".join(p for p in parts if p) or state.get("location", "")
    values["latitude"] = geo["latitude"]
    values["longitude"] = geo["longitude"]
    values["time_window_label"] = label
    values["fetched_at"] = datetime.utcnow().isoformat() + "Z"
    values["turn_id"] = state.get("turn_id", "")

    return {
        **state,
        "raw_forecast":       raw,
        "weather_values":     values,
        "time_window_label":  label,
        "weather_failed":     False,
    }
