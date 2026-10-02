"""
validator.py — Post-compose reply checker (anti-hallucination enforcement).
"""

import re

class ValidationError(Exception):
    """Raised when the LLM reply violates factual or policy constraints."""
    pass


def _allowed_values(state: dict, config: dict) -> set[float]:
    """Build the set of numbers the reply is allowed to use."""
    allowed = set()
    rounding = config.get("validator", {}).get("rounding_decimals_allowed", [0, 1])

    def add_vals(val):
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            v = float(val)
            allowed.add(v)
            for d in rounding:
                allowed.add(round(v, d))

    # 1. Weather values
    for v in state.get("weather_values", {}).values():
        if isinstance(v, list):
            for item in v:
                add_vals(item)
        else:
            add_vals(v)

    # 2. Primary SOP text and conditions
    primary = state.get("primary_sop")
    if primary:
        def walk(conds):
            for key in ("all", "any"):
                for c in conds.get(key, []):
                    if "field" in c:
                        val = c.get("value")
                        if isinstance(val, list):
                            for item in val:
                                add_vals(item)
                        else:
                            add_vals(val)
                    else:
                        walk(c)
        
        walk(primary.get("conditions", {}))

        sop_text = primary.get("guidance", "") + " "
        for m in re.findall(r"\b\d+(?:\.\d+)?\b", sop_text):
            add_vals(float(m))

    return allowed


def validate_reply(state: dict, config: dict) -> bool:
    """
    Check the LLM reply against fetched data.
    Raises ValidationError if constraints are violated.
    Returns True on success.
    """
    reply = state.get("reply")
    if not reply:
        raise ValidationError(
            "Location: app.validator.validate_reply (Line 59)\n"
            "Cause: Reply string is empty or missing from state.\n"
            "Actionable Fix: Ensure the upstream LLM generation step successfully populates `state['reply']` before validation."
        )

    # 1. Number validation
    reply_nums = {float(m) for m in re.findall(r"\b\d+(?:\.\d+)?\b", reply)}
    if reply_nums:
        allowed_nums = _allowed_values(state, config)
        for num in reply_nums:
            if not any(abs(num - a) < 0.15 for a in allowed_nums):
                raise ValidationError(
                    f"Location: app.validator.validate_reply (Line 71)\n"
                    f"Cause: The number {num} was found in the reply but does not exist in the fetched weather data or primary SOP.\n"
                    f"Actionable Fix: The LLM is hallucinating data. Update the prompt to strictly enforce using only context-provided numbers."
                )

    # 2. SOP ID validation
    cited_ids = re.findall(r"\b[A-Z][A-Z0-9]*-[A-Z0-9]+-\d+\b", reply)
    if cited_ids:
        # Extract directly from matched state (Zero I/O overhead)
        matched_sops = state.get("matched_sops", [])
        allowed_ids = {s.get("id") for s in matched_sops if isinstance(s, dict)}
        
        for sid in cited_ids:
            if sid not in allowed_ids:
                raise ValidationError(
                    f"Location: app.validator.validate_reply (Line 84)\n"
                    f"Cause: The SOP ID '{sid}' cited in the reply was not found in the matched SOPs {allowed_ids}.\n"
                    f"Actionable Fix: The LLM is hallucinating a policy ID. Update prompt to only cite matching SOP IDs."
                )

    return True
