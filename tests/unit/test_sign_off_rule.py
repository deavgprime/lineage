import pytest
from lineage_api.sign_off import needs_mlro


@pytest.mark.unit
@pytest.mark.parametrize(
    ("drafted", "floor", "rating", "expected"),
    [
        ("low", "low", "low", False),
        ("low", "low", "medium", False),
        ("medium", "low", "medium", False),
        ("high", "low", "high", True),
        ("high", "low", "low", True),
        ("low", "high", "low", True),
        ("medium", "low", "low", True),
        ("low", None, "high", True),
    ],
)
def test_who_needs_a_second_sign_off(
    drafted: str, floor: str | None, rating: str, expected: bool
) -> None:
    assert needs_mlro(drafted, floor, rating) is expected
