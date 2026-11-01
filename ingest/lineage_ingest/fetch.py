"""Download the pinned OpenSanctions files and check them against their published checksums.

    python -m lineage_ingest.fetch <directory>

The eval in CI loads these exact versions, so its result changes only when the pins change. A file
already in the directory with the right checksum is not downloaded again.
"""

import hashlib
import sys
import urllib.request
from pathlib import Path
from typing import NamedTuple

BASE = "https://data.opensanctions.org/artifacts"


class Pin(NamedTuple):
    dataset: str
    version: str
    sha1: str

    @property
    def url(self) -> str:
        return f"{BASE}/{self.dataset}/{self.version}/targets.simple.csv"

    @property
    def filename(self) -> str:
        return f"{self.dataset}.csv"


PINS = (
    Pin("sanctions", "20261101134705-cns", "a551e4d258b880cc68baae62f1c9e90a1d738ca2"),
    Pin("peps", "20261101152847-jqj", "88baa091f39fe6fbdfcfe7edcd56b859087baf93"),
)


def sha1(path: Path) -> str:
    # SHA-1 because it is the checksum OpenSanctions publishes. It checks integrity, not secrecy.
    digest = hashlib.sha1(usedforsecurity=False)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for pin in PINS:
        path = directory / pin.filename
        if path.exists() and sha1(path) == pin.sha1:
            continue
        partial = path.with_suffix(".part")
        urllib.request.urlretrieve(pin.url, partial)  # noqa: S310 - fixed https URL
        if (got := sha1(partial)) != pin.sha1:
            partial.unlink()
            raise SystemExit(f"{pin.dataset}: checksum {got} does not match pin {pin.sha1}")
        partial.replace(path)
    (directory / "version.txt").write_text(
        ",".join(f"{p.dataset}:{p.version}" for p in PINS) + "\n"
    )


def main() -> None:
    fetch(Path(sys.argv[1]))


if __name__ == "__main__":
    main()
