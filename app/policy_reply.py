"""Deterministic rendering of SOP evidence and guidance."""

from app.sop_engine import _eval_one


_WEATHER_CODE_LABELS = {
    51: "light drizzle", 53: "drizzle", 55: "dense drizzle",
    61: "rain", 63: "moderate rain", 65: "heavy rain",
    80: "rain showers", 81: "rain showers", 82: "violent rain showers",
    95: "thunderstorms", 96: "thunderstorms with hail", 99: "thunderstorms with hail",
}


def _conditions(conditions: dict):
    """Flatten a policy's condition group without changing its evaluation."""
    for group in ("all", "any"):
        for condition in conditions.get(group, []):
            if "field" in condition:
                yield condition
            else:
                yield from _conditions(condition)


def _format_value(value) -> str:
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


def _evidence(condition: dict, weather: dict, fields: dict, sop_id: str) -> str:
    """Render one condition using only its fetched value and policy threshold."""
    field = condition["field"]
    actual = weather.get(field)
    passed = _eval_one(condition, weather) is True
    marker = "✔" if passed else "✘"
    definition = fields.get(field, {})
    label = definition.get("label", field.replace("_", " "))
    unit = definition.get("unit", "")

    if field == "weather_codes":
        matched = [code for code in actual or [] if code in condition.get("value", [])]
        description = _WEATHER_CODE_LABELS.get(matched[0], "a relevant weather condition") if matched else "no matching severe condition"
        return f"{marker} Forecast condition: {description}."

    value = "not available" if actual is None else _format_value(actual)
    suffix = f" {unit}" if actual is not None and unit else ""
    op_text = {
        ">=": "at or above", "<=": "at or below", ">": "above",
        "<": "below", "==": "equal to",
    }.get(condition.get("op"), "matching")
    threshold = _format_value(condition.get("value"))
    return (
        f"{marker} {label.capitalize()}: {value}{suffix}. "
        f"Policy {sop_id} applies {op_text} {threshold}{suffix}."
    )


def render_policy_reply(state: dict) -> str:
    """Render policy-owned guidance and fetched evidence without an LLM."""
    primary = state["primary_sop"]
    weather = state.get("weather_values", {})
    fields = state["config"].get("weather_fields", {})
    location = state.get("geo_result", {}).get("name", state.get("location", ""))
    time_window = state.get("time_window_label", "today")
    activity = state.get("activity", "your activity")

    lines = []
    if state.get("follow_up_context"):
        lines.extend([state["follow_up_context"], ""])
    lines.extend([f"For {activity} in {location} ({time_window}):", "", "What the data says"])
    for condition in _conditions(primary.get("conditions", {})):
        # Fuzzy assessments expose every factor. Other policies show the
        # evidence that actually activated the rule, not unrelated failures.
        if primary.get("fuzzy") or _eval_one(condition, weather) is True:
            lines.append(_evidence(condition, weather, fields, primary["id"]))
    lines.append("")
    if primary.get("fuzzy"):
        band = primary.get("matched_band", "assessment")
        lines.append(f"Verdict: {band.capitalize()} conditions for this activity.")
        factor_guidance = primary["fuzzy"].get("factor_guidance", {})
        failed_factors = [
            condition["field"] for condition in _conditions(primary.get("conditions", {}))
            if _eval_one(condition, weather) is True
        ]
        advice = [factor_guidance[field] for field in failed_factors if field in factor_guidance]
        lines.extend(["", f"Recommended (policy {primary['id']})"])
        if advice:
            lines.extend(f"{index}. {text}" for index, text in enumerate(advice, start=1))
        else:
            lines.append(f"1. {primary['guidance'].strip()}")
    else:
        lines.extend([f"Recommended (policy {primary['id']})", f"1. {primary['guidance'].strip()}"])
    return "\n".join(lines)
