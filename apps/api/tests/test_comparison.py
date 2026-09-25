import pytest

from app.execution.comparison import values_match


@pytest.mark.parametrize(
    ("actual", "expected", "mode", "result"),
    [
        ([1, 2], [1, 2], "exact", True),
        ([2, 1], [1, 2], "exact", False),
        (True, 1, "exact", False),
        ((1, 2), [1, 2], "exact", True),
        ({"a": (1,)}, {"a": [1]}, "exact", True),
        ([2, 1], [1, 2], "unordered", True),
        ([[2, 1], [3]], [[3], [1, 2]], "nested_unordered", True),
        ([[2, 1], [3]], [[3], [1, 3]], "nested_unordered", False),
        ([1, [2, 1]], [[1, 2], 1], "nested_unordered", True),
        (1, [1], "unordered", False),
        (0.1 + 0.2, 0.3, "float", True),
        ([0.1 + 0.2], [0.3], "float", True),
        ([0.1], [0.3], "float", False),
        ([0.1], [0.1, 0.2], "float", False),
        (True, 1.0, "float", False),
        ("a", "a", "float", True),
    ],
)
def test_values_match(actual: object, expected: object, mode: str, result: bool) -> None:
    assert values_match(actual, expected, mode) is result


def test_unknown_mode_is_rejected() -> None:
    with pytest.raises(ValueError):
        values_match([1], [1], "fuzzy")
