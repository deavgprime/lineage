import re
from pathlib import Path

import pytest

WORKFLOWS = sorted((Path(__file__).resolve().parents[2] / ".github" / "workflows").glob("*.yml"))
PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")


@pytest.mark.unit
@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_actions_are_pinned_to_a_commit_sha(path: Path) -> None:
    uses = re.findall(r"^\s*-?\s*uses:\s*(\S+)", path.read_text("utf-8"), flags=re.M)
    local = ("./", "$/")
    unpinned = [u for u in uses if not u.startswith(local) and not PINNED.match(u)]
    assert not unpinned, f"{path.name} uses actions not pinned to a commit SHA: {unpinned}"


@pytest.mark.unit
@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_declares_permissions(path: Path) -> None:
    text = path.read_text("utf-8")
    assert re.search(r"^permissions:", text, flags=re.M), (
        f"{path.name} has no top-level permissions"
    )


@pytest.mark.unit
@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_job_has_a_timeout(path: Path) -> None:
    text = path.read_text("utf-8")
    jobs = re.findall(r"^  [\w-]+:\n(?:    .*\n|\n)+", text.split("\njobs:\n", 1)[1], flags=re.M)
    # A job that calls a reusable workflow cannot set a timeout; the called jobs set their own.
    missing = [
        j.splitlines()[0].strip()
        for j in jobs
        if "timeout-minutes:" not in j and not re.search(r"^    uses:", j, flags=re.M)
    ]
    assert not missing, f"{path.name}: jobs without timeout-minutes: {missing}"


@pytest.mark.unit
@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_pull_request_text_is_not_interpolated_into_scripts(path: Path) -> None:
    text = path.read_text("utf-8")
    for block in re.findall(r"run:\s*[|>]?-?\n?((?:\s{10,}.*\n?)+)", text):
        assert "github.head_ref" not in block, f"{path.name}: pass head_ref through env"
        assert "github.event.pull_request.title" not in block
