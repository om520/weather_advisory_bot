"""geocode.py — Node 2: resolve location string to coordinates."""

from app.weather import geocode as _geocode


def geocode_node(state: dict) -> dict:
    """Geocode the location string. Sets geo_result or marks geo_failed."""
    geo = _geocode(state["location"])
    return {
        **state,
        "geo_result": geo,
        "geo_failed": geo is None,
    }
