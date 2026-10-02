"""
weather.py — Geocoding + forecast fetch + time-windowed aggregation.
"""
import requests
import yaml
from pathlib import Path
from datetime import datetime, timedelta
from statistics import mean as _mean

_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = _ROOT / "sops" / "config.yaml"

_LOCATION_ALIASES = {
    "hubli": "Hubballi, Karnataka, India",
    "hubali": "Hubballi, Karnataka, India",
    "hubballi": "Hubballi, Karnataka, India",
}

def load_config() -> dict:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        raise RuntimeError(
            "Location: app.weather.load_config\n"
            f"Cause: File read/parse failure for config.yaml. Raw error: {e}\n"
            "Actionable Fix: Ensure sops/config.yaml exists and is valid YAML format."
        )

def geocode(city: str) -> dict:
    query = _LOCATION_ALIASES.get(city.strip().casefold(), city)
    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": query, "count": 10, "language": "en", "format": "json"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        raise ConnectionError(
            "Location: app.weather.geocode\n"
            f"Cause: Open-Meteo Geocoding API network failure. Raw error: {e}\n"
            "Actionable Fix: Check outbound network connectivity or Open-Meteo API status."
        )

    results = data.get("results")
    if not results:
        raise ValueError(
            "Location: app.weather.geocode\n"
            f"Cause: No geolocation found for query '{query}'.\n"
            "Actionable Fix: Provide a more precise or correctly spelled city name."
        )

    requested_names = {p.strip().casefold() for p in query.split(",") if p.strip()}
    h = next((res for res in results if str(res.get("name", "")).casefold() in requested_names), results[0])

    return {
        "name": h["name"],
        "latitude": h["latitude"],
        "longitude": h["longitude"],
        "country": h.get("country", ""),
        "admin1": h.get("admin1", ""),
        "timezone": h.get("timezone", "auto"),
    }

def fetch_forecast(lat: float, lon: float, config: dict) -> dict:
    wf = config.get("weather_fields", {})
    fc = config.get("forecast", {})
    
    hourly_vars = {fd["variable"] for fd in wf.values() if fd["source"] == "hourly"}
    daily_vars = {fd["variable"] for fd in wf.values() if fd["source"] == "daily"}

    params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": fc.get("timezone", "auto"),
        "forecast_days": fc.get("forecast_days", 2),
    }
    if hourly_vars: params["hourly"] = ",".join(sorted(hourly_vars))
    if daily_vars: params["daily"] = ",".join(sorted(daily_vars))

    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=8)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        raise ConnectionError(
            "Location: app.weather.fetch_forecast\n"
            f"Cause: Open-Meteo forecast API network failure. Raw error: {e}\n"
            "Actionable Fix: Verify network routing to Open-Meteo and check request parameters."
        )

def _parse_hour(spec, utc_offset_sec: int) -> int:
    if isinstance(spec, int): return spec
    s = str(spec)
    if "now" not in s: return int(s)
    h = (datetime.utcnow() + timedelta(seconds=utc_offset_sec)).hour
    return min(h + int(s.split("+")[1]), 23) if "+" in s else min(h, 23)

def resolve_time_window(time_ref: str, config: dict, forecast: dict) -> tuple[list[int], int, str]:
    windows = config.get("time_windows", {})
    ref = time_ref if time_ref in windows else config.get("default_time_ref", "today")
    w = windows[ref]
    utc_off = forecast.get("utc_offset_seconds", 0)
    
    start = _parse_hour(w["start_hour"], utc_off)
    end = _parse_hour(w["end_hour"], end_off := utc_off)
    day_off = w.get("day_offset", 0)
    label = w.get("label", ref)
    times = forecast.get("hourly", {}).get("time", [])

    if not times: return [], day_off, label
    target_date = datetime.fromisoformat(times[0]).date() + timedelta(days=day_off)
    
    indices = [
        i for i, ts in enumerate(times)
        if (dt := datetime.fromisoformat(ts)).date() == target_date and start <= dt.hour <= end
    ]
    return indices, day_off, label

def _agg(values: list, method: str, threshold: float = 0.0):
    nums = [v for v in values if v is not None]
    if not nums: return None
    
    match method:
        case "max": return max(nums)
        case "min": return min(nums)
        case "mean": return round(_mean(nums), 1)
        case "sum": return round(sum(nums), 1)
        case "list": return list(dict.fromkeys(nums))
        case "count_gte": return sum(1 for v in nums if v >= threshold)
        case _: return None

def compute_weather_values(forecast: dict, config: dict, time_ref: str = "today") -> tuple[dict, str]:
    wf = config.get("weather_fields", {})
    indices, day_off, label = resolve_time_window(time_ref, config, forecast)
    
    hourly, daily = forecast.get("hourly", {}), forecast.get("daily", {})
    times = hourly.get("time", [])
    result = {}

    for key, fd in wf.items():
        src, var, method = fd["source"], fd["variable"], fd["agg"]
        
        if src == "hourly":
            raw = hourly.get(var)
            if raw is None:
                result[key] = None
                continue
            
            idx = indices
            if fd.get("hours") == "whole_day":
                target = datetime.fromisoformat(times[0]).date() + timedelta(days=day_off)
                idx = [i for i, ts in enumerate(times) if datetime.fromisoformat(ts).date() == target]
            elif "hours_intersect" in fd:
                a, b = fd["hours_intersect"]
                idx = [i for i in indices if a <= datetime.fromisoformat(times[i]).hour <= b]

            vals = [raw[i] for i in idx if i < len(raw)] if idx else []
            result[key] = _agg(vals, method, fd.get("threshold", 0.0))
            
        elif src == "daily":
            raw = daily.get(var)
            if raw is None or day_off >= len(raw):
                result[key] = None
                continue
            
            result[key] = raw[day_off] if method == "value" else _agg([raw[day_off]], method)
        else:
            result[key] = None

    return result, label
