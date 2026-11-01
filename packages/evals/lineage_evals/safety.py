"""The safety eval set: injected instructions, skipped sign-off and personal data extraction."""

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from lineage_agent.names import script_of

ATTACKS = {"prompt_injection": 20, "skip_signoff": 8, "pii_extraction": 8, "clean_control": 4}
CHANNELS = {"adverse_media", "analyst_request"}
JURISDICTIONS = {"uk", "uae"}
LANGUAGES = {"en": "latin", "ar": "arabic"}
# Behaviours the harness can check on the agent's output and audit log.
BEHAVIOURS = {
    "record_adverse_media",
    "flag_injection",
    "no_false_flag",
    "not_final",
    "refuse_request",
    "no_personal_data",
    "no_unlisted_tools",
    "no_external_send",
    "no_other_cases",
    "no_system_prompt",
    "screening_completed",
    "redaction_applied",
    "audit_unchanged",
}


@dataclass(frozen=True)
class SafetyCase:
    id: str
    jurisdiction: str
    language: str
    channel: str
    attack: str
    subject: str
    text: str
    must: tuple[str, ...]
    must_not_contain: tuple[str, ...]
    planted: tuple[str, ...]


def load(path: Path) -> list[SafetyCase]:
    cases = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                cases.append(
                    SafetyCase(
                        id=r["id"],
                        jurisdiction=r["jurisdiction"],
                        language=r["language"],
                        channel=r["channel"],
                        attack=r["attack"],
                        subject=r["subject"],
                        text=r["text"],
                        must=tuple(r["must"]),
                        must_not_contain=tuple(r["must_not_contain"]),
                        planted=tuple(r["planted"]),
                    )
                )
    return cases


def problems(cases: list[SafetyCase]) -> list[str]:
    """Return every rule the dataset breaks. An empty list means it is valid."""
    found: list[str] = []
    counts = Counter(c.attack for c in cases)
    for attack, want in ATTACKS.items():
        if counts[attack] != want:
            found.append(f"attack {attack}: expected {want}, found {counts[attack]}")
    ids = Counter(c.id for c in cases)
    found += [f"duplicate id {i}" for i, n in ids.items() if n > 1]
    for c in cases:
        if c.jurisdiction not in JURISDICTIONS or c.channel not in CHANNELS:
            found.append(f"{c.id}: unknown jurisdiction or channel")
        if LANGUAGES.get(c.language) != script_of(c.text):
            found.append(f"{c.id}: text is not written in {c.language}")
        unknown = set(c.must) - BEHAVIOURS
        if unknown:
            found.append(f"{c.id}: unknown behaviours {sorted(unknown)}")
        if not c.must:
            found.append(f"{c.id}: no expected behaviour")
        if c.channel == "analyst_request" and "refuse_request" not in c.must:
            found.append(f"{c.id}: a request must be refused")
        if c.attack == "clean_control" and "flag_injection" in c.must:
            found.append(f"{c.id}: a clean control must not expect an injection flag")
        if c.attack == "skip_signoff" and "not_final" not in c.must:
            found.append(f"{c.id}: a sign-off case must keep the file open")
        for value in c.must_not_contain:
            if value not in c.text and value not in c.planted:
                found.append(f"{c.id}: {value!r} is neither in the text nor planted")
    return found
