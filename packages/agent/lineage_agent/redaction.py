"""Replace known people with placeholders before text reaches an external model.

This is the first pass from decision 0001: the agent knows the people in a case from its tools, so
each gets a stable placeholder such as [PERSON_1] for every spelling it has. The Presidio pass for
addresses and identifiers is added in phase 5.
"""

import re

from lineage_agent.names import normalise

_PLACEHOLDER = re.compile(r"\[PERSON_\d+\]")


class RedactionError(RuntimeError):
    pass


class Redactor:
    def __init__(self) -> None:
        self._tags: dict[str, str] = {}  # normalised spelling -> placeholder
        self._spellings: dict[str, str] = {}  # spelling as written -> placeholder
        self._names: dict[str, str] = {}  # placeholder -> name shown to the analyst

    def add_person(self, *spellings: str) -> str:
        """Register every spelling of one person and return their placeholder."""
        usable = [s.strip() for s in spellings if normalise(s)]
        if not usable:
            raise RedactionError("a person needs at least one name")
        known = [self._tags[normalise(s)] for s in usable if normalise(s) in self._tags]
        tag = known[0] if known else f"[PERSON_{len(self._names) + 1}]"
        self._names.setdefault(tag, usable[0])
        for spelling in usable:
            self._tags[normalise(spelling)] = tag
            self._spellings[spelling] = tag
        return tag

    def redact(self, text: str) -> str:
        # Longest spellings first, so a full name is replaced before any part of it.
        for spelling in sorted(self._spellings, key=len, reverse=True):
            text = re.sub(re.escape(spelling), self._spellings[spelling], text, flags=re.IGNORECASE)
        return text

    def leaks(self, text: str) -> list[str]:
        """Return every known spelling still present in text."""
        return [s for s in self._spellings if re.search(re.escape(s), text, re.IGNORECASE)]

    def restore(self, text: str) -> str:
        unknown = [t for t in _PLACEHOLDER.findall(text) if t not in self._names]
        if unknown:
            raise RedactionError(f"the model returned unknown placeholders {unknown}")
        return _PLACEHOLDER.sub(lambda m: self._names[m.group(0)], text)
