"""Sanitisation of untrusted free text before it reaches a model (PROMPT_DESIGN.md §4.3).

Product, category and supplier names, exception titles, notes, file names, references and raw
import values come from imported files or from people. Every such value passes through
``TextGuard`` in the tool that returns it: normalised, stripped of invisible and control
characters, delimiter-neutralised and length-limited. Text that looks like an instruction is
*marked*, never blocked, because ordinary product names and notes can trip the heuristics.
"""

import re
import unicodedata
from typing import Any

# Length limits per kind of untrusted text (PROMPT_DESIGN.md §4.3).
NAME_MAX = 200
TITLE_MAX = 200
NOTE_MAX = 1000
MOVEMENT_NOTE_MAX = 200
REFERENCE_MAX = 100
RAW_VALUE_MAX = 100
FILENAME_MAX = 255
QUESTION_MAX = 2000

_REMOVE = {
    *(chr(c) for c in range(0x200B, 0x200E)),  # zero-width space / non-joiner / joiner
    "⁠",  # word joiner
    "﻿",  # zero-width no-break space
    *(chr(c) for c in range(0x202A, 0x202F)),  # bidi embeddings and overrides
    *(chr(c) for c in range(0x2066, 0x206A)),  # bidi isolates
}
_BLANK_LINES = re.compile(r"\n(?:[ \t]*\n){2,}")
_SUSPICIOUS = re.compile(
    r"ignore (?:all |any |the )?(?:previous|prior|above|earlier)"
    r"|disregard (?:all |any |the )?(?:previous|prior|above|earlier|instructions)"
    r"|system prompt|you are now|new instructions|developer mode"
    r"|(?:^|\n)\s*(?:assistant|system|user|tool)\s*:"
    r"|‹/?\s*(?:context|question|system|user_hint|tool)",
    re.IGNORECASE,
)


def is_suspicious(text: str) -> bool:
    """Injection heuristics: instruction-like phrases, role labels, delimiter look-alikes."""
    return bool(_SUSPICIOUS.search(text))


def clean(value: str, limit: int) -> str:
    """Normalise, strip invisible/control characters, neutralise ``<``/``>`` and truncate."""
    text = unicodedata.normalize("NFC", value)
    text = "".join(
        ch
        for ch in text
        if ch not in _REMOVE and (ch in "\n\t" or unicodedata.category(ch) != "Cc")
    )
    text = text.replace("<", "‹").replace(">", "›")
    text = _BLANK_LINES.sub("\n\n", text)
    if len(text) > limit:
        text = text[: max(limit - 1, 0)].rstrip() + "…"
    return text


class TextGuard:
    """Cleans the untrusted values of one record and remembers whether any looked suspicious."""

    def __init__(self) -> None:
        self.suspicious = False

    def __call__(self, value: str | None, limit: int) -> str | None:
        if value is None:
            return None
        text = clean(value, limit)
        if is_suspicious(text):
            self.suspicious = True
        return text

    def mark(self, record: dict[str, Any]) -> dict[str, Any]:
        """Add ``suspicious_text: true`` to the record when any of its values tripped a check."""
        if self.suspicious:
            record["suspicious_text"] = True
        return record
