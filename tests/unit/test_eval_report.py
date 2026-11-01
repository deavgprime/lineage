import json
from pathlib import Path

import pytest
from lineage_evals.report import MARKER, report


def write(directory: Path, name: str, body: object) -> None:
    directory.mkdir(exist_ok=True)
    (directory / f"{name}.json").write_text(json.dumps(body))


def screening(recall: float) -> list[dict[str, object]]:
    row: dict[str, object] = {"recall": recall, "false_positives": 1, "unlisted_recall": 0.9}
    return [{"pack": "uk", **row}, {"pack": "uae", **row}]


@pytest.mark.unit
def test_shows_each_measure_next_to_the_base_branch(tmp_path: Path) -> None:
    now, base = tmp_path / "now", tmp_path / "base"
    write(now, "screening", screening(0.99))
    write(base, "screening", screening(1.0))
    write(now, "ownership", {"rate": 0.9})
    text = report(now, base)
    assert text.startswith(MARKER)
    assert "| screening | UK recall | 99.0% | 100.0% | at least 98% |" in text
    assert "| ownership | Exact chains | 90.0% | - | at least 90% |" in text
    assert "| safety | Failed runs | - | - | 0 |" in text
    assert "unchanged from the base branch" in text


@pytest.mark.unit
def test_names_model_evals_committed_with_the_change(tmp_path: Path) -> None:
    now, base = tmp_path / "now", tmp_path / "base"
    write(now, "safety", {"summary": {"failed_runs": 0}})
    write(base, "safety", {"summary": {"failed_runs": 2}})
    text = report(now, base)
    assert "| safety | Failed runs | 0 | 2 | 0 |" in text
    assert "New model eval results in this pull request: safety." in text
