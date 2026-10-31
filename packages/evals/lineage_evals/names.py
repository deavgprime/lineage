"""Name normalisation shared by the dataset builder and the screening eval."""

import re
import unicodedata


def _span(first: int, last: int) -> str:
    return f"{chr(first)}-{chr(last)}"


# Arabic points and marks, and the tatweel stretch character.
_ARABIC_MARKS = re.compile(
    "["
    + _span(0x0610, 0x061A)
    + _span(0x064B, 0x065F)
    + chr(0x0670)
    + _span(0x06D6, 0x06ED)
    + chr(0x0640)
    + "]"
)
_ARABIC_RANGE = re.compile(f"[{_span(0x0600, 0x06FF)}]")
_CYRILLIC_RANGE = re.compile(f"[{_span(0x0400, 0x04FF)}]")
# Alef variants become bare alef, alef maksura becomes yeh, teh marbuta becomes heh.
_ARABIC_LETTERS = str.maketrans(
    {0x0623: 0x0627, 0x0625: 0x0627, 0x0622: 0x0627, 0x0649: 0x064A, 0x0629: 0x0647}
)
_NOT_WORD = re.compile(r"[^\w\s]", flags=re.UNICODE)
_SPACES = re.compile(r"\s+")


def normalise(name: str) -> str:
    """Fold case, accents, Arabic marks and punctuation so spelling noise does not matter."""
    text = unicodedata.normalize("NFKD", name)
    text = _ARABIC_MARKS.sub("", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.translate(_ARABIC_LETTERS).casefold()
    text = _NOT_WORD.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def script_of(name: str) -> str:
    """Return "arabic", "cyrillic" or "latin" by the letters the name uses."""
    if _ARABIC_RANGE.search(name):
        return "arabic"
    if _CYRILLIC_RANGE.search(name):
        return "cyrillic"
    return "latin"
