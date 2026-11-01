"""Evidence records the agent can cite, each with a stable id and a plain-text body."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Evidence:
    source_id: str
    title: str
    text: str


class EvidenceStore:
    def __init__(self) -> None:
        self._items: dict[str, Evidence] = {}

    def add(self, source_id: str, title: str, text: str) -> None:
        self._items[source_id] = Evidence(source_id, title, text)

    def get(self, source_id: str) -> Evidence | None:
        return self._items.get(source_id)

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self._items.values())

    def __len__(self) -> int:
        return len(self._items)
