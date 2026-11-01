import hashlib
import urllib.request
from pathlib import Path

import pytest
from lineage_ingest import fetch
from lineage_ingest.fetch import PINS, Pin


@pytest.mark.unit
def test_pins_are_exact_versions_with_checksums() -> None:
    assert {p.dataset for p in PINS} == {"sanctions", "peps"}
    for pin in PINS:
        assert pin.version != "latest"
        assert len(pin.sha1) == 40
        assert pin.url.startswith("https://data.opensanctions.org/artifacts/")


@pytest.mark.unit
def test_skips_files_that_match_and_rejects_files_that_do_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    good = b"id,name\n"
    pin = Pin("sanctions", "v1", hashlib.sha1(good, usedforsecurity=False).hexdigest())
    monkeypatch.setattr(fetch, "PINS", (pin,))
    (tmp_path / "sanctions.csv").write_bytes(good)

    def no_download(url: str, path: Path) -> None:
        raise AssertionError("downloaded a file that was already valid")

    monkeypatch.setattr(urllib.request, "urlretrieve", no_download)
    fetch.fetch(tmp_path)
    assert (tmp_path / "version.txt").read_text() == "sanctions:v1\n"

    (tmp_path / "sanctions.csv").write_bytes(b"changed")
    monkeypatch.setattr(
        urllib.request, "urlretrieve", lambda url, path: Path(path).write_bytes(b"bad")
    )
    with pytest.raises(SystemExit, match="does not match"):
        fetch.fetch(tmp_path)
    assert not (tmp_path / "sanctions.part").exists()
