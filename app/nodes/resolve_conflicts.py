"""resolve_conflicts.py — Node 5: pick primary SOP and also-applies list."""

from app.sop_engine import resolve_conflicts


def resolve_conflicts_node(state: dict) -> dict:
    """
    Apply conflict resolution rules to produce one primary SOP
    and a capped also-applies list.
    """
    primary, also = resolve_conflicts(state["matched_sops"], state["config"])
    return {**state, "primary_sop": primary, "also_applies": also}
