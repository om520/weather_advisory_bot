"""
fallbacks.py — All fixed-template nodes (no LLM, no invented text).

These nodes fire on: missing location/activity, geocode failure,
weather API failure, no SOP match, out-of-scope questions.
"""

from app.sop_engine import collect_activity_tags, load_sops


def _activity_examples(n: int = 4) -> str:
    tags = sorted(collect_activity_tags(load_sops()))
    return ", ".join(tags[:n])


def _resolved_location(state: dict) -> str:
    """
    Build 'City, Region, Country' from the geo_result, skipping blank parts.
    Falls back to the raw location string.
    """
    geo = state.get("geo_result") or {}
    parts = [
        geo.get("name", ""),
        geo.get("admin1", ""),
        geo.get("country", ""),
    ]
    joined = ", ".join(p for p in parts if p)
    return joined or state.get("location", "")


def build_weather_summary(snapshot: dict, config: dict) -> str:
    """
    Build a human-readable bullet list from the weather snapshot using
    only the fields listed in config.summary_fields.

    One line per field:
      - <label>: <value> <unit>   or   - <label>: not available for this time window
    """
    field_defs = config.get("weather_fields", {})
    summary_keys = config.get("summary_fields", [])
    
    available = []
    missing = []
    
    for key in summary_keys:
        definition = field_defs.get(key, {})
        label = definition.get("label", key.replace("_", " "))
        unit  = definition.get("unit", "")
        value = snapshot.get(key)
        
        if value is None:
            missing.append(label)
        else:
            if isinstance(value, float):
                formatted = f"{value:.1f}"
            elif isinstance(value, list):
                formatted = ", ".join(str(v) for v in value)
            else:
                formatted = str(value)
            suffix = f" {unit}" if unit else ""
            cap_label = label[0].upper() + label[1:] if label else ""
            available.append(f"{cap_label}: {formatted}{suffix}")
            
    lines = []
    for i in range(0, len(available), 2):
        if i + 1 < len(available):
            lines.append(f"- {available[i]:<36} • {available[i+1]}")
        else:
            lines.append(f"- {available[i]}")
            
    if missing:
        lines.append(f"Not checked for this time window: {', '.join(missing)}.")
        
    return "\n".join(lines)


def _fill(template: str, state: dict, extra: dict = None) -> str:
    mapping = {
        "activity":          state.get("activity", ""),
        "location":          state.get("location", ""),
        "resolved_location": _resolved_location(state),
        "time_window":       state.get("time_window_label", "today"),
        "activity_examples": _activity_examples(),
        "weather_summary":   "",
    }
    if extra:
        mapping.update(extra)
    return template.format(**mapping)


def ask_clarification_node(state: dict) -> dict:
    """Ask for whichever required field (location or activity) is missing."""
    cfg = state["config"]
    templates = cfg.get("templates", {})
    if not state.get("location"):
        msg = templates.get("clarify_location", "Which city should I check?")
    else:
        msg = _fill(templates.get("clarify_activity", "What activity?"), state)
    return {**state, "reply": msg, "reply_source": "template",
            "primary_sop": None, "also_applies": [], "severity": None,
            "weather_values": {}}


def honest_fallback_node(state: dict) -> dict:
    """Used when geocode fails OR weather API fails."""
    cfg = state["config"]
    templates = cfg.get("templates", {})
    if state.get("geo_failed"):
        msg = templates.get("location_unresolved", "Could not find that location.")
        msg = msg.format(location=state.get("location", ""))
        error = None
    else:
        msg = templates.get("weather_unavailable", "Weather data unavailable.")
        error = {
            "code": "E-WX-001",
            "meaning": "Weather service unreachable",
            "what_happened": "The forecast service did not answer within 8 seconds.",
            "what_to_do": "Please try again in a few minutes.",
        }
    return {**state, "reply": msg, "reply_source": "template",
            "primary_sop": None, "also_applies": [], "severity": None,
            "weather_values": {}, "error": error}


def no_guidance_node(state: dict) -> dict:
    """Used when weather is fetched but no SOP conditions are triggered."""
    cfg = state["config"]
    templates = cfg.get("templates", {})
    snapshot = state.get("weather_values", {})
    summary = build_weather_summary(snapshot, cfg)
    template = templates.get("no_sop_triggered", "No guidance for this.")
    msg = _fill(template, state, extra={"weather_summary": summary})
    badges = cfg.get("badges", {})
    badge = badges.get("no_guidance", {})
    return {**state, "reply": msg, "reply_source": "template",
            "primary_sop": None, "also_applies": [],
            "severity": None,
            "badge_label": badge.get("label", "No guidance"),
            "badge_icon":  badge.get("icon", "⚪")}


def out_of_scope_node(state: dict) -> dict:
    """Used when activity is unknown AND no who tag is recognised."""
    cfg = state["config"]
    templates = cfg.get("templates", {})
    msg = _fill(templates.get("out_of_scope", "I can't help with that."), state)
    return {**state, "reply": msg, "reply_source": "template",
            "primary_sop": None, "also_applies": [], "severity": None,
            "weather_values": {}}


def template_reply_node(state: dict) -> dict:
    """
    Validator fallback: build the reply directly from primary SOP guidance
    text with no LLM involved.
    """
    primary = state.get("primary_sop")
    if primary:
        geo = state.get("geo_result") or {}
        geo_name = geo.get("name") or state.get("location", "")
        label = state.get("time_window_label", "today")
        msg = (
            f"For {state.get('activity', 'your activity')} in {geo_name} "
            f"({label}): {primary['guidance'].strip()}"
        )
    else:
        msg = state.get("reply", "")
    return {**state, "reply": msg, "reply_source": "template_fallback"}
