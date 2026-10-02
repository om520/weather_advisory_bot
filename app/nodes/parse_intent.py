"""parse_intent.py — Node 1: extract request facts via LLM."""

from app.llm import parse_intent as llm_parse_intent, IntentParseError
from app.sop_engine import collect_activity_tags, load_sops


def parse_intent_node(state: dict) -> dict:
    """
    Extract structured intent using the Cerebras LLM.
    Merges with session memory: missing fields fall back to last known values.
    On LLM failure, sets activity='unknown' and location='' so the graph
    routes to a safe fallback node instead of crashing.
    """
    sops = load_sops()
    known_tags = collect_activity_tags(sops)

    try:
        parsed = llm_parse_intent(state["user_message"], known_tags)
    except IntentParseError:
        parsed = {"activity": "unknown", "location": "", "time_ref": "today", "who": ""}

    prior_activity = state.get("activity", "unknown")
    prior_location = state.get("location", "")
    prior_time_ref = state.get("time_ref", "today")

    # Session memory: only overwrite fields the LLM actually found
    activity = parsed["activity"] if parsed["activity"] != "unknown" else state.get("activity", "unknown")
    location = parsed["location"] or state.get("location", "")
    time_ref = parsed["time_ref"] or state.get("time_ref", "today")
    who      = parsed["who"]      or state.get("who", "")

    is_follow_up = bool(
        prior_location and prior_activity != "unknown"
        and (not parsed["location"] or parsed["activity"] == "unknown")
    )
    follow_up_context = ""
    if is_follow_up:
        follow_up_context = (
            f"Following on from your earlier question about {prior_activity} "
            f"in {prior_location} ({prior_time_ref}), now for "
            f"{time_ref.replace('_', ' ')}."
        )

    return {
        **state,
        "activity":      activity,
        "location":      location,
        "time_ref":      time_ref,
        "who":           who,
        "known_tags":    known_tags,
        "follow_up_context": follow_up_context,
        "next":          None,
    }
