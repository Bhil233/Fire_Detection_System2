from __future__ import annotations

import json
import re
from typing import Any


FIRE_CONFIDENCE_THRESHOLD = 0.5


def _clamp_confidence(value: int | float) -> float:
    numeric_value = float(value)
    if numeric_value > 1.0:
        numeric_value = numeric_value / 100.0
    return max(0.0, min(1.0, numeric_value))


def _parse_confidence_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int | float):
        return _clamp_confidence(value)
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value)
        if match:
            return _clamp_confidence(float(match.group(0)))
    return None


def _find_confidence_in_text(text: str) -> float | None:
    patterns = [
        r'"(?:fire_)?confidence"\s*:\s*"?(-?\d+(?:\.\d+)?)%?"?',
        r'\b(?:fire_)?confidence\b\s*[:=]\s*"?(-?\d+(?:\.\d+)?)%?"?',
        r'\b\u7f6e\u4fe1\u5ea6\b\s*[:=]\s*"?(-?\d+(?:\.\d+)?)%?"?',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _clamp_confidence(float(match.group(1)))

    stripped = text.strip()
    if re.fullmatch(r"-?\d+(?:\.\d+)?%?", stripped):
        return _clamp_confidence(float(stripped.rstrip("%")))
    return None


def parse_fire_confidence(text: str) -> float:
    normalized = text.strip().lower()
    try:
        parsed = json.loads(normalized)
        if isinstance(parsed, int | float | str | bool):
            confidence = _parse_confidence_value(parsed)
            if confidence is not None:
                return confidence
        if isinstance(parsed, dict):
            if "confidence" in parsed:
                confidence = _parse_confidence_value(parsed["confidence"])
                if confidence is not None:
                    return confidence
            if "fire_confidence" in parsed:
                confidence = _parse_confidence_value(parsed["fire_confidence"])
                if confidence is not None:
                    return confidence
            if "fire" in parsed:
                return 1.0 if bool(parsed["fire"]) else 0.0
    except (TypeError, ValueError, json.JSONDecodeError):
        pass

    confidence = _find_confidence_in_text(normalized)
    if confidence is not None:
        return confidence

    if '"fire": true' in normalized or "fire:true" in normalized:
        return 1.0
    if '"fire": false' in normalized or "fire:false" in normalized:
        return 0.0
    if "fire" in normalized and "no_fire" not in normalized:
        return 1.0
    return 0.0


def parse_fire_result(text: str) -> bool:
    return parse_fire_confidence(text) >= FIRE_CONFIDENCE_THRESHOLD
