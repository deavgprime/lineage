from pathlib import Path

import pytest
from lineage_ingest.policy import POLICIES, parse_regulation, read_policy

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "legislation" / "mlr-2017-30A.xml"


@pytest.mark.unit
@pytest.mark.parametrize(("name", "pack", "cite"), [("uk", "uk", "UK"), ("uae", "uae", "UAE")])
def test_each_policy_splits_into_numbered_sections(name: str, pack: str, cite: str) -> None:
    doc = read_policy(POLICIES / f"{name}-kyc-policy.md")
    refs = [s.ref for s in doc.sections]
    assert doc.pack == pack and doc.licence == "Apache-2.0" and doc.version == "1.0"
    assert len(refs) == len(set(refs)) >= 30
    assert refs[0] == f"{cite} KYC policy 1.1"
    beneficial = next(s for s in doc.sections if s.ref.endswith(" 4.1"))
    assert beneficial.heading == "Beneficial ownership"
    assert "25 percent" in beneficial.text


@pytest.mark.unit
def test_a_regulation_splits_into_paragraphs_with_amended_numbers() -> None:
    version, sections = parse_regulation(FIXTURE.read_text(encoding="utf-8"))
    refs = [s.ref for s in sections]
    assert version
    assert refs[:2] == ["Regulation 30A(1)", "Regulation 30A(1A)"]
    assert len(refs) == len(set(refs))
    assert all(s.heading for s in sections)
    assert not any("( " in s.text or " )" in s.text for s in sections)


@pytest.mark.unit
def test_an_empty_corpus_fails_loudly(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import lineage_ingest.policy as policy

    monkeypatch.setattr(policy, "POLICIES", tmp_path)
    with pytest.raises(SystemExit, match="no policy documents"):
        list(policy.documents(include_legislation=False))
