import json
import math
from typing import Any

FLOAT_TOLERANCE = 1e-6


def _key(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _normalize(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    return value


def _floats_close(actual: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(_floats_close(a, e) for a, e in zip(actual, expected, strict=True))
        )
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return (
            isinstance(actual, (int, float))
            and not isinstance(actual, bool)
            and math.isclose(actual, expected, rel_tol=FLOAT_TOLERANCE, abs_tol=FLOAT_TOLERANCE)
        )
    return bool(actual == expected)


def values_match(actual: Any, expected: Any, mode: str) -> bool:
    actual = _normalize(actual)
    expected = _normalize(expected)
    if mode == "exact":
        # bool is an int subclass in Python; do not let True satisfy 1.
        return _key(actual) == _key(expected)
    if mode == "float":
        return _floats_close(actual, expected)
    if not isinstance(actual, list) or not isinstance(expected, list):
        return False
    if mode == "unordered":
        return sorted(map(_key, actual)) == sorted(map(_key, expected))
    if mode == "nested_unordered":

        def canonical(items: list[Any]) -> list[str]:
            return sorted(
                _key(sorted(item, key=_key)) if isinstance(item, list) else _key(item)
                for item in items
            )

        return canonical(actual) == canonical(expected)
    raise ValueError(f"unknown comparison mode {mode}")
