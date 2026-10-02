"""
graph.py — LangGraph definition.

Nodes: parse_intent → geocode → fetch_weather → match_sops →
       resolve_conflicts → compose_reply → validate_reply → END
       (with conditional branches to fallback nodes at each step)

All branching is via conditional edges, not if/else inside nodes.
"""

import yaml
from pathlib import Path
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.nodes.parse_intent    import parse_intent_node
from app.nodes.geocode         import geocode_node
from app.nodes.fetch_weather   import fetch_weather_node
from app.nodes.match_sops      import match_sops_node
from app.nodes.resolve_conflicts import resolve_conflicts_node
from app.nodes.compose_reply   import compose_reply_node
from app.nodes.validate_reply  import validate_reply_node
from app.nodes.fallbacks import (
    ask_clarification_node,
    honest_fallback_node,
    no_guidance_node,
    out_of_scope_node,
    template_reply_node,
)

_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = _ROOT / "sops" / "config.yaml"


def _load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── State type (plain TypedDict-like dict with known keys) ─────────────
# LangGraph requires a schema. We use a flat dict and declare it inline.

from typing import TypedDict, Any, Optional

class AgentState(TypedDict, total=False):
    # Input
    user_message: str
    config: dict
    turn_id: str
    # Parsed intent
    activity: str
    location: str
    time_ref: str
    who: str
    known_tags: Any
    follow_up_context: str
    # Geo
    geo_result: Optional[dict]
    geo_failed: bool
    # Weather
    raw_forecast: Optional[dict]
    weather_values: dict
    time_window_label: str
    weather_failed: bool
    error: Optional[dict]
    # SOP matching
    matched_sops: list
    primary_sop: Optional[dict]
    also_applies: list
    # Reply
    reply: str
    reply_source: str
    # Validation / badge
    validation_passed: bool
    severity: Optional[str]
    badge_label: str
    badge_icon: str


# ── Branch conditions (all return a node name string) ─────────────────

def _after_parse(state: AgentState) -> str:
    missing_location = not state.get("location")
    missing_activity = (
        state.get("activity", "unknown") == "unknown"
        and not state.get("who")
    )
    if missing_location or missing_activity:
        return "ask_clarification" if missing_location else "out_of_scope"
    return "geocode"


def _after_geocode(state: AgentState) -> str:
    return "honest_fallback" if state.get("geo_failed") else "fetch_weather"


def _after_fetch(state: AgentState) -> str:
    return "honest_fallback" if state.get("weather_failed") else "match_sops"


def _after_match(state: AgentState) -> str:
    matched = state.get("matched_sops", [])
    if not matched:
        # No SOPs fired — check if activity was known at all
        known = state.get("known_tags", set())
        activity = state.get("activity", "unknown")
        who = state.get("who", "")
        if activity not in known and not who:
            return "out_of_scope"
        return "no_guidance"
    return "resolve_conflicts"


def _after_validate(state: AgentState) -> str:
    return "end" if state.get("validation_passed") else "template_reply"


# ── Build graph ────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    # Register nodes
    g.add_node("parse_intent",      parse_intent_node)
    g.add_node("ask_clarification", ask_clarification_node)
    g.add_node("geocode",           geocode_node)
    g.add_node("fetch_weather",     fetch_weather_node)
    g.add_node("match_sops",        match_sops_node)
    g.add_node("resolve_conflicts", resolve_conflicts_node)
    g.add_node("compose_reply",     compose_reply_node)
    g.add_node("validate_reply",    validate_reply_node)
    g.add_node("honest_fallback",   honest_fallback_node)
    g.add_node("no_guidance",       no_guidance_node)
    g.add_node("out_of_scope",      out_of_scope_node)
    g.add_node("template_reply",    template_reply_node)

    # Entry point
    g.set_entry_point("parse_intent")

    # Conditional edges (the only branching mechanism used)
    g.add_conditional_edges("parse_intent",   _after_parse,    {
        "ask_clarification": "ask_clarification",
        "out_of_scope":      "out_of_scope",
        "geocode":           "geocode",
    })
    g.add_conditional_edges("geocode",        _after_geocode,  {
        "honest_fallback": "honest_fallback",
        "fetch_weather":   "fetch_weather",
    })
    g.add_conditional_edges("fetch_weather",  _after_fetch,    {
        "honest_fallback": "honest_fallback",
        "match_sops":      "match_sops",
    })
    g.add_conditional_edges("match_sops",     _after_match,    {
        "no_guidance":      "no_guidance",
        "out_of_scope":     "out_of_scope",
        "resolve_conflicts":"resolve_conflicts",
    })
    g.add_conditional_edges("validate_reply", _after_validate, {
        "end":           END,
        "template_reply":"template_reply",
    })

    # Linear edges
    g.add_edge("resolve_conflicts", "compose_reply")
    g.add_edge("compose_reply",     "validate_reply")

    # Terminal nodes → END
    for terminal in ("ask_clarification", "honest_fallback",
                     "no_guidance", "out_of_scope", "template_reply"):
        g.add_edge(terminal, END)

    return g


def compile_graph():
    """Return a compiled, memory-backed graph ready to invoke."""
    return build_graph().compile(checkpointer=MemorySaver())


# ── CLI test (no LLM needed — tests the routing logic) ───────────────

if __name__ == "__main__":
    import json

    cfg = _load_config()
    graph = compile_graph()

    def _run(label: str, user_message: str, activity: str,
             location: str, time_ref: str = "today",
             thread_id: str = "test-1"):
        print(f"\n{'='*55}")
        print(f"TEST: {label}")
        print(f"  msg      : {user_message}")
        init = {
            "user_message": user_message,
            "config": cfg,
            # Pre-fill parsed fields to bypass LLM in CLI test
            "activity": activity,
            "location": location,
            "time_ref": time_ref,
            "who": "",
        }
        result = graph.invoke(init, config={"configurable": {"thread_id": thread_id}})
        print(f"  source   : {result.get('reply_source')}")
        print(f"  severity : {result.get('severity')}")
        badge_icon = result.get('badge_icon', '') or ''
        badge_label = result.get('badge_label', '') or ''
        print(f"  badge    : {badge_icon.encode('ascii','replace').decode()} {badge_label}")
        if result.get("primary_sop"):
            print(f"  SOP      : {result['primary_sop']['id']}")
        also = result.get("also_applies", [])
        if also:
            print(f"  also     : {[s['id'] for s in also]}")
        print(f"  reply    : {result.get('reply', '')[:200]}")
        return result

    # Branch: missing location → ask_clarification
    _run("Missing location", "Is it good to go hiking?", "hiking", "", thread_id="t1")

    # Branch: unknown activity → out_of_scope
    _run("Unknown activity", "Can I do skydiving?", "unknown", "London", thread_id="t2")

    # Branch: unresolvable location → honest_fallback
    _run("Bad location", "Cycling in xyznotacity123?", "cycling", "xyznotacity123", thread_id="t3")

    # Branch: real city, normal conditions → should fetch weather + match SOPs
    _run("Normal run Mumbai", "Is it ok to go running in Mumbai today?",
         "running", "Mumbai", "today", thread_id="t4")

    print("\n[DONE] All CLI branch tests complete.")
