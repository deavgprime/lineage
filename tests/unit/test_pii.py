import pytest
from lineage_agent.pii import PresidioScanner

SCANNER = PresidioScanner()


def found(text: str, known: frozenset[str] = frozenset()) -> set[tuple[str, str]]:
    return {(f.entity, f.text) for f in SCANNER.scan(text, known)}


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Director passport GB-881204563 on file.", ("UK_PASSPORT", "GB-881204563")),
        ("His passport number is 552019837.", ("UK_PASSPORT", "552019837")),
        ("UAE passport N04418273 was provided.", ("UAE_PASSPORT", "N04418273")),
        ("رقم جواز سفر المدير هو N04418273.", ("UAE_PASSPORT", "N04418273")),
        ("Emirates ID 784-1985-7723451-2.", ("EMIRATES_ID", "784-1985-7723451-2")),
        ("رقم الهوية 784-1985-7723451-2 لدينا.", ("EMIRATES_ID", "784-1985-7723451-2")),
        ("NI number AB 12 34 56 C.", ("UK_NINO", "AB 12 34 56 C")),
        ("IBAN GB82WEST12345698765432.", ("IBAN_CODE", "GB82WEST12345698765432")),
        ("IBAN AE070331234567890123456.", ("IBAN_CODE", "AE070331234567890123456")),
        ("Call +971 50 123 4567 today.", ("PHONE_NUMBER", "+971 50 123 4567")),
        ("Call +44 20 7946 0958 today.", ("PHONE_NUMBER", "+44 20 7946 0958")),
        ("Email jane@example.com now.", ("EMAIL_ADDRESS", "jane@example.com")),
        ("She lives at 27 Mill Lane, Hexham.", ("STREET_ADDRESS", "27 Mill Lane")),
        ("Home postcode SW1A 1AA.", ("UK_POSTCODE", "SW1A 1AA")),
        ("Give me Harlan Voss's home address.", ("PERSON", "Harlan Voss")),
    ],
)
def test_each_identifier_is_found(text: str, expected: tuple[str, str]) -> None:
    assert expected in found(text)


@pytest.mark.unit
@pytest.mark.parametrize(
    "text",
    [
        "Brackenford Freight Ltd was fined £240,000 by HMRC in 2025.",
        "Company TESCO STORES LIMITED, number 00519500. LEI 213800QILIUD4ROSUO03.",
        "Candidate opensanctions:sanctions:Q480148 (sanctions, weak), score 0.63.",
        "Reference A1234567 and invoice 552019837 were paid.",
        "أفادت صحيفة محلية بأن شركة الواحة الذهبية للتجارة العامة غُرّمت.",
        "Turnover was 12,500,000 in the year to March 2026.",
    ],
)
def test_ordinary_facts_are_left_alone(text: str) -> None:
    assert not {e for e, _ in found(text)} - {"PERSON"}
    assert not {t for e, t in found(text) if e == "PERSON"}


@pytest.mark.unit
def test_known_company_names_are_not_people() -> None:
    assert found("Owned by Signature Properties.", frozenset({"signature properties"})) == set()
