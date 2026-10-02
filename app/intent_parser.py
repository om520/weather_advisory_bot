"""Deterministic extraction of activity, location, audience, and time."""

import re


def _contains_phrase(message: str, phrase: str) -> bool:
    return re.search(r"(?<!\\w)" + re.escape(phrase.lower()) + r"(?!\\w)", message) is not None


def _first_matching_tag(message: str, tags: set[str], aliases: dict) -> str:
    matches = []
    for tag in tags:
        phrases = [tag.replace("_", " "), *aliases.get(tag, [])]
        for phrase in phrases:
            position = message.find(phrase.lower())
            if position >= 0 and _contains_phrase(message, phrase):
                matches.append((position, tag))
                break
    return min(matches)[1] if matches else "unknown"


def _extract_time_ref(message: str, time_phrases: dict) -> str:
    matches = []
    for time_ref, phrases in time_phrases.items():
        for phrase in phrases:
            position = message.find(phrase.lower())
            if position >= 0 and _contains_phrase(message, phrase):
                matches.append((position, time_ref))
                break
    return min(matches)[1] if matches else ""


def _extract_location(message: str, stop_words: list[str]) -> str:
    """Extract a city phrase after a location preposition without guessing."""
    pattern = re.compile(r"\b(?:in|at|near|around|from)\s+([a-z][a-z .'-]{0,80})", re.IGNORECASE)
    match = pattern.search(message)
    if not match:
        return ""

    candidate = match.group(1).strip(" .?!,")
    lower_candidate = candidate.lower()
    for stop_word in stop_words:
        marker = re.search(r"\b" + re.escape(stop_word.lower()) + r"\b", lower_candidate)
        if marker:
            candidate = candidate[:marker.start()].strip(" .?!,")
            break

    return candidate.title() if candidate else ""


def parse_intent(message: str, known_tags: set[str], intent_config: dict) -> dict:
    """Return structured facts using only configured aliases and regex rules."""
    normalized = " ".join(message.lower().split())
    activity = _first_matching_tag(
        normalized, known_tags, intent_config.get("activity_aliases", {})
    )
    who = _first_matching_tag(
        normalized, set(intent_config.get("who_aliases", {})), intent_config.get("who_aliases", {})
    )
    return {
        "activity": activity,
        "location": _extract_location(normalized, intent_config.get("location_stop_words", [])),
        "time_ref": _extract_time_ref(normalized, intent_config.get("time_phrases", {})),
        "who": "" if who == "unknown" else who,
    }
