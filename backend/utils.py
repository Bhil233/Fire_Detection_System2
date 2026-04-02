from __future__ import annotations

import json


def parse_fire_result(text: str) -> bool:
    normalized = text.strip().lower()
    try:
        parsed = json.loads(normalized)
        if isinstance(parsed, dict) and "fire" in parsed:
            return bool(parsed["fire"])
    except json.JSONDecodeError:
        pass

    if '"fire": true' in normalized or "fire:true" in normalized:
        return True
    if '"fire": false' in normalized or "fire:false" in normalized:
        return False
    if "fire" in normalized and "no_fire" not in normalized:
        return True
    return False
