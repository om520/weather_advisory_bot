"""validate_reply.py — Node 7: check LLM reply, set badge, decide route."""

from app.validator import validate_reply


def validate_reply_node(state: dict) -> dict:
    """
    Run the validator. Attach badge from primary SOP severity.
    Sets validation_passed flag; the graph routes on this.
    """
    cfg = state["config"]
    passed = validate_reply(state, cfg)

    # Attach badge from severity
    primary = state.get("primary_sop")
    severity = primary["severity"] if primary else None
    badges = cfg.get("badges", {})
    badge = badges.get(severity, badges.get("no_guidance", {}))

    return {
        **state,
        "validation_passed": passed,
        "severity":          severity,
        "badge_label":       badge.get("label", "No guidance"),
        "badge_icon":        badge.get("icon", "⚪"),
    }
