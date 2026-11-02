"""The Presidio pass from decision 0001: find personal data the tools did not tell the agent about.

Known people from the registers are replaced first by the Redactor. This pass reads everything else
that is about to leave for an external model, such as adverse media, onboarding documents and
analyst requests, and reports:

- people's names, which become [PERSON_n] and are restored for the analyst afterwards
- identifiers such as passport numbers, Emirates IDs, National Insurance numbers, IBANs, phone
  numbers, email addresses and street addresses, which become [ID_n] and are never restored

Recognisers for identifiers are patterns, so they work on English and Arabic text alike. Names are
found by spaCy's English model only; Arabic names in free text rely on the known-entity pass.
"""

import re
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING, Literal

from lineage_agent.names import script_of

if TYPE_CHECKING:
    from presidio_analyzer import EntityRecognizer

Kind = Literal["person", "identifier"]

# Presidio entity types this pass acts on, and how each is treated.
ENTITIES: dict[str, Kind] = {
    "PERSON": "person",
    "EMAIL_ADDRESS": "identifier",
    "PHONE_NUMBER": "identifier",
    "IBAN_CODE": "identifier",
    "CREDIT_CARD": "identifier",
    "UK_NINO": "identifier",
    "UK_PASSPORT": "identifier",
    "UAE_PASSPORT": "identifier",
    "EMIRATES_ID": "identifier",
    "STREET_ADDRESS": "identifier",
    "UK_POSTCODE": "identifier",
}
THRESHOLD = 0.5

# Shapes that are common outside personal data count only when one of these words comes shortly
# before them. Presidio's own context window is a few tokens, too short for Arabic word order.
CONTEXT: dict[str, tuple[str, ...]] = {
    "UK_PASSPORT": ("passport", "جواز"),
    "UAE_PASSPORT": ("passport", "جواز"),
    "UK_POSTCODE": ("postcode", "address", "home", "lives", "resides", "عنوان"),
}
CONTEXT_CHARS = 80

# Spans that look like names but are organisations, so they stay readable for the model.
COMPANY_WORDS = re.compile(
    r"\b(limited|ltd|plc|llp|llc|lp|inc|corp|holdings?|group|bank|trust|fze|fzco|partners|"
    r"company|co|services|trading|capital)\b\.?",
    re.IGNORECASE,
)

STREET_TYPES = (
    "Street|St|Road|Rd|Lane|Ln|Avenue|Ave|Close|Drive|Way|Court|Place|Gardens|Crescent|Terrace|"
    "Rise|Hill|Grove|Square|Mews|Row|Walk|Park|Parade"
)


# A trailing possessive, with a straight or typographic apostrophe.
POSSESSIVE = re.compile("['\u2019]s?$")


@dataclass(frozen=True)
class Finding:
    kind: Kind
    entity: str
    text: str


def _recognisers() -> list["EntityRecognizer"]:
    from presidio_analyzer import Pattern, PatternRecognizer
    from presidio_analyzer.predefined_recognizers import PhoneRecognizer

    # Presidio scores a valid phone number at 0.4 and relies on context words to lift it. A number
    # that parses as valid for the UK or the UAE is enough here.
    phone = PhoneRecognizer(supported_regions=("GB", "AE"), context=[])
    phone.SCORE = 0.6
    return [
        phone,
        PatternRecognizer(
            supported_entity="UK_NINO",
            patterns=[
                Pattern(
                    "nino",
                    r"\b(?!BG|GB|NK|KN|TN|NT|ZZ)[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z]"
                    r"\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b",
                    0.6,
                )
            ],
            context=["national insurance", "nino", "ni number"],
        ),
        PatternRecognizer(
            supported_entity="UK_PASSPORT",
            patterns=[
                Pattern("gb prefixed", r"\bGB-?\d{9}\b", 0.6),
                Pattern("nine digits", r"\b\d{9}\b", 0.6),
            ],
        ),
        PatternRecognizer(
            # UAE passports are a letter and seven or eight digits. The same shape is common for
            # other references, so it only counts next to the word passport.
            supported_entity="UAE_PASSPORT",
            patterns=[Pattern("letter and digits", r"\b[A-Z]\d{7,8}\b", 0.6)],
        ),
        PatternRecognizer(
            supported_entity="EMIRATES_ID",
            patterns=[Pattern("784", r"\b784-?\d{4}-?\d{7}-?\d\b", 0.8)],
        ),
        PatternRecognizer(
            supported_entity="STREET_ADDRESS",
            patterns=[
                Pattern(
                    "number and street",
                    rf"\b\d{{1,4}}[A-Za-z]?,?\s+(?:[A-Z][a-z]+\s+){{1,3}}(?:{STREET_TYPES})\b",
                    0.6,
                )
            ],
        ),
        PatternRecognizer(
            supported_entity="UK_POSTCODE",
            patterns=[Pattern("postcode", r"\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b", 0.6)],
        ),
    ]


class PresidioScanner:
    """Finds personal data with Presidio. Loading the English model takes a second, so one scanner
    is built per process and reused."""

    @cached_property
    def _analyzer(self):  # type: ignore[no-untyped-def]
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider

        engine = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
            }
        ).create_engine()
        analyzer = AnalyzerEngine(nlp_engine=engine, supported_languages=["en"])
        analyzer.registry.remove_recognizer("PhoneRecognizer")
        for recogniser in _recognisers():
            analyzer.registry.add_recognizer(recogniser)
        return analyzer

    def scan(self, text: str, known: frozenset[str] = frozenset()) -> list[Finding]:
        """Return what to redact in text. `known` holds names that must stay readable, such as
        the companies under review."""
        results = self._analyzer.analyze(
            text=text, language="en", entities=list(ENTITIES), score_threshold=THRESHOLD
        )
        identifiers = []
        for r in results:
            words = CONTEXT.get(r.entity_type)
            if words:
                before = text[max(0, r.start - CONTEXT_CHARS) : r.start].casefold()
                if not any(w in before for w in words):
                    continue
            if ENTITIES[r.entity_type] == "identifier":
                identifiers.append(r)
        findings = [
            Finding("identifier", r.entity_type, text[r.start : r.end].strip(" ,.;:"))
            for r in sorted(identifiers, key=lambda r: r.start)
        ]
        for r in sorted(results, key=lambda r: r.start):
            if ENTITIES[r.entity_type] != "person":
                continue
            if any(r.start < i.end and i.start < r.end for i in identifiers):
                continue
            span = POSSESSIVE.sub("", text[r.start : r.end]).strip(" ,.;:'\"")
            if (
                len(span) < 3
                or any(c.isdigit() for c in span)
                or script_of(span) != "latin"
                or COMPANY_WORDS.search(span)
                or span.casefold() in known
            ):
                continue
            findings.append(Finding("person", "PERSON", span))
        return findings
