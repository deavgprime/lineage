import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_FILES = [
    "LICENSE",
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "docs/brief.md",
    "docs/scoping.md",
    "docs/decisions.md",
    "docs/testing.md",
    "docs/security.md",
    ".github/CODEOWNERS",
    ".github/pull_request_template.md",
    ".github/dependabot.yml",
]

LAYOUT_DIRS = [
    "apps/api",
    "apps/console",
    "packages/agent",
    "packages/evals",
    "packages/mcp",
    "ingest",
    "infra/terraform",
    "infra/helm",
    "docs",
]

EM_DASH = chr(0x2014)


def tracked_text_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    skip = {".png", ".pdf", ".lock", ".webm", ".gif"}
    # Third-party text kept verbatim, such as legislation fixtures, is not ours to restyle.
    verbatim = ("tests/fixtures/legislation/",)
    return [
        ROOT / f
        for f in out
        if Path(f).suffix not in skip and not f.startswith(verbatim) and (ROOT / f).is_file()
    ]


@pytest.mark.unit
@pytest.mark.parametrize("name", REQUIRED_FILES)
def test_required_file_exists(name: str) -> None:
    assert (ROOT / name).is_file(), f"{name} is missing"


@pytest.mark.unit
@pytest.mark.parametrize("name", LAYOUT_DIRS)
def test_layout_directory_exists(name: str) -> None:
    assert (ROOT / name).is_dir(), f"{name}/ is missing"


@pytest.mark.unit
def test_text_uses_only_allowed_punctuation() -> None:
    offenders = [
        str(p.relative_to(ROOT)) for p in tracked_text_files() if EM_DASH in p.read_text("utf-8")
    ]
    assert not offenders, f"disallowed punctuation in: {offenders}"


@pytest.mark.unit
def test_readme_images_exist() -> None:
    readme = (ROOT / "README.md").read_text("utf-8")
    images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", readme)
    assert images, "README has no images"
    missing = [i for i in images if not i.startswith("http") and not (ROOT / i).is_file()]
    assert not missing, f"README images not found: {missing}"


@pytest.mark.unit
def test_every_markdown_link_to_a_local_file_resolves() -> None:
    broken: list[str] = []
    for path in tracked_text_files():
        if path.suffix != ".md":
            continue
        for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", path.read_text("utf-8")):
            if target.startswith(("http", "mailto:")):
                continue
            if not (path.parent / target).exists():
                broken.append(f"{path.relative_to(ROOT)} -> {target}")
    assert not broken, f"broken links: {broken}"
