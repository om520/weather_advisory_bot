"""
sop_engine.py — Generic SOP condition evaluator and conflict resolver.
"""
import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "sops" / "config.yaml"
SOPS_PATH = Path(__file__).resolve().parent.parent / "sops" / "sops.yaml"

def load_sops() -> list[dict]:
    try:
        with open(SOPS_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f).get("sops", [])
    except Exception as e:
        raise RuntimeError(
            "Location: app.sop_engine.load_sops\n"
            f"Cause: File read/parse failure for sops.yaml. Raw error: {e}\n"
            "Actionable Fix: Ensure sops/sops.yaml exists and is valid YAML format."
        )

def collect_activity_tags(sops: list[dict]) -> set[str]:
    return {
        tag for sop in sops
        for tag in (sop.get("applies_to", []) if isinstance(sop.get("applies_to"), list) else [sop.get("applies_to")])
        if tag != "any"
    }

def _eval_one(cond: dict, weather: dict) -> bool | None:
    actual = weather.get(cond["field"])
    if actual is None:
        return None

    op, target = cond["op"], cond["value"]
    match op:
        case ">=": return actual >= target
        case "<=": return actual <= target
        case ">":  return actual > target
        case "<":  return actual < target
        case "==": return actual == target
        case "!=": return actual != target
        case "in": return actual in target
        case "contains_any": return bool(set(actual) & set(target)) if isinstance(actual, list) else None
        case _:
            raise ValueError(
                "Location: app.sop_engine._eval_one\n"
                f"Cause: Unknown or unsupported operator '{op}' in SOP condition for field '{cond['field']}'.\n"
                "Actionable Fix: Correct the operator in sops.yaml to a supported one (e.g., '>=', '==', 'contains_any')."
            )

def _eval_group(group: dict, weather: dict) -> bool | None:
    if "all" in group:
        results = [_eval_one(c, weather) for c in group["all"]]
        return False if False in results else (None if None in results else True)

    if "any" in group:
        results = [_eval_one(c, weather) for c in group["any"]]
        return True if True in results else (False if all(r is False for r in results) else None)

    return None

def match_sops(sops: list[dict], weather: dict, tags: set[str], config: dict) -> list[dict]:
    any_needs_known = config.get("matching", {}).get("any_requires_known_tag", True)
    all_known_tags = collect_activity_tags(sops)
    user_has_known_tag = bool(tags & all_known_tags)

    matched = []
    for sop in sops:
        at = sop.get("applies_to", [])
        if at == "any":
            if any_needs_known and not user_has_known_tag:
                continue
        elif not (set(at if isinstance(at, list) else [at]) & tags):
            continue

        if _eval_group(sop["conditions"], weather) is not True:
            continue

        hit = dict(sop)
        if "fuzzy" in sop:
            for band in sop["fuzzy"].get("bands", []):
                if _eval_group(band["conditions"], weather) is True:
                    hit.update({
                        "severity": band.get("severity", sop["severity"]),
                        "guidance": band.get("guidance", sop["guidance"]),
                        "matched_band": band["name"]
                    })
                    break

        matched.append(hit)
    
    return matched

def resolve_conflicts(matched: list[dict], config: dict) -> tuple[dict | None, list[dict]]:
    if not matched: return None, []

    cr = config.get("conflict_resolution", {})
    lead_cats = set(cr.get("lead_categories", []))
    max_also = cr.get("max_also_applies", 3)
    order = config.get("severity_order", [])

    def sort_key(s):
        rank = order.index(s["severity"]) if s["severity"] in order else -1
        return (-rank, -s.get("priority", 0), s["id"])

    leads, others = [], []
    for s in matched:
        (leads if s.get("category") in lead_cats else others).append(s)
    
    leads.sort(key=sort_key)
    others.sort(key=sort_key)

    primary = leads[0] if leads else others[0]
    also = (leads[1:] + others) if leads else others[1:]

    return primary, also[:max_also]
