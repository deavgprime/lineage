"""Load the policy corpus (decision 0004): the bank's KYC policies and the Money Laundering
Regulations 2017.

    DATABASE_URL=... python -m lineage_ingest.policy

Each document is split into sections that keep their paragraph number, so a citation names a place
a person can find. Each section is embedded with the pinned local model and stored with its pack,
source, version and licence. A section whose text has not changed keeps its embedding, so reloading
the same version changes nothing.
"""

import argparse
import hashlib
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import psycopg
from defusedxml.ElementTree import fromstring

POLICIES = Path(__file__).resolve().parents[2] / "policies"
MODELS = Path(os.environ.get("LINEAGE_MODELS", Path.home() / ".cache" / "lineage" / "models"))
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIMENSIONS = 384

MLR_ID = "uk-mlr-2017"
MLR_URL = "https://www.legislation.gov.uk/uksi/2017/692"
MLR_TITLE = (
    "The Money Laundering, Terrorist Financing and Transfer of Funds (Information on the Payer) "
    "Regulations 2017"
)
# The regulations on customer due diligence, beneficial ownership, reliance, PEPs, enhanced due
# diligence and record keeping.
MLR_REGULATIONS = (5, 27, 28, 30, "30A", 31, 33, 35, 37, 39, 40)
MLR_LICENCE = (
    "Crown copyright, Open Government Licence v3.0. Contains public sector information licensed "
    "under the Open Government Licence v3.0."
)
CLML = "{http://www.legislation.gov.uk/namespaces/legislation}"


@dataclass(frozen=True)
class Section:
    ref: str
    heading: str
    text: str


@dataclass(frozen=True)
class Document:
    id: str
    pack: str
    title: str
    source: str
    version: str
    licence: str
    url: str | None
    sections: tuple[Section, ...]


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class LocalEmbedder:
    """The pinned multilingual model, run on CPU. Files are cached in LINEAGE_MODELS."""

    def __init__(self) -> None:
        from fastembed import TextEmbedding

        self._model = TextEmbedding(EMBEDDING_MODEL, cache_dir=str(MODELS))

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.embed(list(texts))]


FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)
HEADING = re.compile(r"^## (\d+)\. (.+)$")
PARAGRAPH = re.compile(r"^(\d+\.\d+) (.*)$")


def read_policy(path: Path) -> Document:
    """Split a policy written in Markdown: `## N. Heading`, then paragraphs numbered `N.M`."""
    raw = path.read_text(encoding="utf-8")
    front = FRONT.match(raw)
    if not front:
        raise ValueError(f"{path.name}: no front matter")
    meta = dict(line.split(": ", 1) for line in front.group(1).splitlines())
    meta = {k: v.strip().strip('"') for k, v in meta.items()}
    sections: list[Section] = []
    heading, ref = "", ""
    lines: list[str] = []

    def close() -> None:
        if ref:
            sections.append(Section(f"{ref}", heading, " ".join(lines)))

    for line in raw[front.end() :].splitlines():
        if m := HEADING.match(line):
            close()
            heading, ref, lines = m.group(2), "", []
        elif m := PARAGRAPH.match(line):
            close()
            ref, lines = m.group(1), [m.group(2)]
        elif line.strip() and ref:
            lines.append(line.strip())
    close()
    return Document(
        id=path.stem,
        pack=meta["pack"],
        title=meta["title"],
        source="bank policy",
        version=meta["version"],
        licence=meta["licence"],
        url=None,
        sections=tuple(Section(f"{meta['cite']} {s.ref}", s.heading, s.text) for s in sections),
    )


def _number(element: ET.Element) -> str:
    """A paragraph's number. Numbers added by amendment, such as 7A, sit in a child element."""
    found = element.find(f"{CLML}Pnumber")
    return "".join(found.itertext()).strip() if found is not None else ""


def _text(element: ET.Element) -> str:
    # Item letters such as (a) are separate elements; put their brackets back.
    for number in element.iter(f"{CLML}Pnumber"):
        label = "".join(number.itertext()).strip()
        if label and not label.startswith("("):
            for child in list(number):
                number.remove(child)
            number.text = f"({label})"
    text = re.sub(r"\s+", " ", " ".join(element.itertext())).strip()
    text = re.sub(r"\s+([,.;:)\u201d\u2019])", r"\1", text)
    return re.sub(r"([(\u201c\u2018])\s+", r"\1", text)


def parse_regulation(xml: str) -> tuple[str, list[Section]]:
    """One section per numbered paragraph of a regulation, as legislation.gov.uk publishes it."""
    # Downloaded XML is parsed with entity expansion and external references turned off.
    root = fromstring(xml)
    valid = root.find(".//{http://purl.org/dc/terms/}valid")
    version = valid.text if valid is not None and valid.text else ""
    sections: list[Section] = []
    for p1 in root.iter(f"{CLML}P1"):
        number = _number(p1)
        title_el = root.find(f".//{CLML}P1group/{CLML}Title")
        heading = _text(title_el) if title_el is not None else ""
        paragraphs = list(p1.iter(f"{CLML}P2"))
        if not paragraphs:
            body = p1.find(f"{CLML}P1para")
            if body is not None:
                sections.append(Section(f"Regulation {number}", heading, _text(body)))
            continue
        for p2 in paragraphs:
            sub = _number(p2)
            body = p2.find(f"{CLML}P2para")
            if body is not None:
                sections.append(Section(f"Regulation {number}({sub})", heading, _text(body)))
    return version, sections


def fetch_mlr(cache: Path = MODELS.parent / "legislation") -> Document:
    cache.mkdir(parents=True, exist_ok=True)
    sections: list[Section] = []
    versions = set()
    for number in MLR_REGULATIONS:
        path = cache / f"mlr-2017-{number}.xml"
        if not path.exists():
            url = f"{MLR_URL}/regulation/{number}/data.xml"
            with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - fixed https URL
                path.write_bytes(response.read())
        version, found = parse_regulation(path.read_text(encoding="utf-8"))
        versions.add(version)
        sections += found
    return Document(
        id=MLR_ID,
        pack="uk",
        title=MLR_TITLE,
        source="legislation.gov.uk",
        version=max(versions),
        licence=MLR_LICENCE,
        url=MLR_URL,
        sections=tuple(sections),
    )


def _checksum(section: Section) -> str:
    return hashlib.sha256(f"{section.ref}\n{section.heading}\n{section.text}".encode()).hexdigest()


def load(conn: psycopg.Connection[Any], document: Document, embedder: Embedder) -> dict[str, int]:
    """Store a document and its sections. Unchanged sections are not embedded again."""
    counts = {"written": 0, "unchanged": 0, "removed": 0}
    with conn.transaction():
        conn.execute(
            "INSERT INTO policy_documents (id, pack, title, source, version, licence, url) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET "
            "pack = EXCLUDED.pack, title = EXCLUDED.title, source = EXCLUDED.source, "
            "version = EXCLUDED.version, licence = EXCLUDED.licence, url = EXCLUDED.url",
            (
                document.id,
                document.pack,
                document.title,
                document.source,
                document.version,
                document.licence,
                document.url,
            ),
        )
        existing = dict(
            conn.execute(
                "SELECT id, checksum FROM policy_sections WHERE document_id = %s", (document.id,)
            ).fetchall()
        )
        keep = {f"{document.id}:{s.ref}" for s in document.sections}
        gone = [k for k in existing if k not in keep]
        if gone:
            conn.execute("DELETE FROM policy_sections WHERE id = ANY(%s)", (gone,))
            counts["removed"] = len(gone)
        changed = [
            (i, s)
            for i, s in enumerate(document.sections)
            if existing.get(f"{document.id}:{s.ref}") != _checksum(s)
        ]
        vectors = embedder.embed([f"{s.heading}. {s.text}" for _, s in changed]) if changed else []
        for (position, s), vector in zip(changed, vectors, strict=True):
            conn.execute(
                "INSERT INTO policy_sections (id, document_id, pack, ref, heading, text, position, "
                "checksum, embedding) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector) "
                "ON CONFLICT (id) DO UPDATE SET ref = EXCLUDED.ref, heading = EXCLUDED.heading, "
                "text = EXCLUDED.text, position = EXCLUDED.position, "
                "checksum = EXCLUDED.checksum, embedding = EXCLUDED.embedding",
                (
                    f"{document.id}:{s.ref}",
                    document.id,
                    document.pack,
                    s.ref,
                    s.heading,
                    s.text,
                    position,
                    _checksum(s),
                    str(vector),
                ),
            )
        counts["written"] = len(changed)
        counts["unchanged"] = len(document.sections) - len(changed)
    return counts


def documents(include_legislation: bool = True) -> Iterable[Document]:
    for path in sorted(POLICIES.glob("*.md")):
        yield read_policy(path)
    if include_legislation:
        yield fetch_mlr()


class FlatEmbedder:
    """The same vector for every text. Only for end-to-end tests, whose fixture answers use keyword
    search, so they need neither the model download nor real embeddings."""

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * (DIMENSIONS - 1) for _ in texts]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-legislation", action="store_true", help="load the bank policies only")
    ap.add_argument(
        "--flat-embeddings", action="store_true", help="end-to-end tests only: skip the model"
    )
    args = ap.parse_args()
    embedder: Embedder = FlatEmbedder() if args.flat_embeddings else LocalEmbedder()
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        for document in documents(include_legislation=not args.no_legislation):
            print(document.id, load(conn, document, embedder))


if __name__ == "__main__":
    main()
