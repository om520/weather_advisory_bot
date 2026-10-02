from app.llm import IntentParseError
from app.nodes import parse_intent as parse_intent_module
from app.graph import _after_parse


def test_model_failure_routes_to_ai_unavailable(monkeypatch):
    monkeypatch.setattr(
        parse_intent_module,
        "_llm_parse",
        lambda *_: (_ for _ in ()).throw(IntentParseError("temporary outage")),
    )

    state = parse_intent_module.parse_intent_node({"user_message": "Hiking in Mumbai"})

    assert state["intent_parse_failed"] is True
    assert _after_parse(state) == "ai_unavailable"


def test_real_missing_location_still_asks_for_location():
    assert _after_parse({"activity": "hiking", "location": ""}) == "ask_clarification"


def test_unsupported_activity_routes_to_no_guidance_response():
    assert _after_parse({"activity": "unknown", "location": "Delhi"}) == "out_of_scope"
