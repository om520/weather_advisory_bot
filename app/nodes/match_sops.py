"""match_sops.py — Node 4: match SOPs against weather values."""

from app.sop_engine import load_sops, match_sops


def match_sops_node(state: dict) -> dict:
    """
    Evaluate all SOP conditions against the fetched weather values.
    Sets matched_sops (list, may be empty).
    """
    sops = load_sops()
    tags = set()
    if state.get("activity") and state["activity"] != "unknown":
        tags.add(state["activity"])
    if state.get("who"):
        tags.add(state["who"])

    matched = match_sops(sops, state["weather_values"], tags, state["config"])
    return {**state, "matched_sops": matched}
