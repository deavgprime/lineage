import pytest
from lineage_evals.readme import END, README, START, render


@pytest.mark.unit
def test_the_readme_results_match_the_baselines() -> None:
    current = README.read_text(encoding="utf-8")
    assert START in current and END in current
    assert current == render(current), "run: python -m lineage_evals.readme"
