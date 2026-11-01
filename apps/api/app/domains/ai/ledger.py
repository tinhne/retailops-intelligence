"""The per-turn evidence ledger (AI_ARCHITECTURE.md §6).

Every record a tool returns carries a ``ref``; the ledger indexes those refs (with the
server-authoritative label) and every numeric field under the ref it belongs to. The validator
then checks that an answer cites only refs read in this turn and that each metric value is a number
one of its cited records actually contains. The ledger lives in memory for one turn only.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domains.ai.tools.base import REF_TYPES, ref_key

_NUMERIC_STRING = re.compile(r"^-?\d+(?:\.\d+)?$")
# A number inside free text: not part of a date, a time, an identifier (SKU, EXC-1001, P1) or a
# word. Thousands separators and a leading currency sign are allowed.
_DATE_OR_TIME = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)?|\d{1,2}:\d{2}"
)
_TEXT_NUMBER = re.compile(r"(?<![\w.\-/#])[-+]?\$?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?%?(?![\w\-/])")
_REF_FIELDS = ("ref", "source")


def to_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str) and _NUMERIC_STRING.match(value.strip()):
        return Decimal(value.strip())
    return None


def numbers_in_text(text: str) -> list[Decimal]:
    """Numeric tokens of free text, normalised (thousands separators, currency sign, percent)."""
    stripped = _DATE_OR_TIME.sub(" ", text)
    found = []
    for match in _TEXT_NUMBER.finditer(stripped):
        token = match.group(1).replace(",", "") + (match.group(2) or "")
        try:
            found.append(Decimal(token))
        except InvalidOperation:  # pragma: no cover - the pattern only matches digits
            continue
    return found


def parse_metric_value(value: str) -> Decimal | None:
    cleaned = value.strip().replace(",", "").lstrip("$").rstrip("%").strip()
    try:
        return Decimal(cleaned) if _NUMERIC_STRING.match(cleaned) else None
    except InvalidOperation:  # pragma: no cover
        return None


@dataclass
class LedgerEntry:
    type: str
    id: str
    label: str
    numbers: set[Decimal] = field(default_factory=set)  # numeric fields that are facts
    estimate_numbers: set[Decimal] = field(default_factory=set)  # inside an is_estimate object

    @property
    def key(self) -> str:
        return ref_key(self.type, self.id)


@dataclass
class EvidenceLedger:
    entries: dict[str, LedgerEntry] = field(default_factory=dict)
    text_numbers: set[Decimal] = field(default_factory=set)
    has_estimates: bool = False
    returned_records: bool = False
    data_window_from: datetime | None = None

    # --- building ------------------------------------------------------------------------------

    def _register(self, ref: Any) -> str | None:
        if not isinstance(ref, dict):
            return None
        type_, id_ = ref.get("type"), ref.get("id")
        if type_ not in REF_TYPES or not id_:
            return None
        key = ref_key(str(type_), str(id_))
        if key not in self.entries:
            self.entries[key] = LedgerEntry(str(type_), str(id_), str(ref.get("label") or key))
        return key

    def _walk(self, node: Any, owners: tuple[str, ...], estimate: bool) -> None:
        if isinstance(node, dict):
            own = owners
            for name in _REF_FIELDS:
                key = self._register(node.get(name))
                if key is not None and key not in own:
                    own = (*own, key)
            if node.get("is_estimate") is True:
                estimate = True
                self.has_estimates = True
            for name, value in node.items():
                if name in _REF_FIELDS:
                    continue
                self._walk(value, own, estimate)
        elif isinstance(node, list):
            for item in node:
                self._walk(item, owners, estimate)
        else:
            number = to_decimal(node)
            if number is not None:
                for key in owners:
                    entry = self.entries[key]
                    (entry.estimate_numbers if estimate else entry.numbers).add(number)
            elif isinstance(node, str):
                self.text_numbers.update(numbers_in_text(node))

    def add_envelope(self, envelope: dict[str, Any], result_ref: dict[str, str] | None) -> None:
        """Index one SUCCESS envelope. Envelope-level counts (``total_available``, ``row_count``,
        ``total_overdue``) belong to the call's own aggregate ref."""
        records = envelope.get("records") or []
        if records:
            self.returned_records = True
        for record in records:
            self._walk(record, (), False)
        # After the records, so an aggregate record keeps its own label ("Dashboard summary").
        result_key = self._register(result_ref) if result_ref else None
        if result_key is not None:
            for name, value in envelope.items():
                if name in ("records", "data_window", "as_of", "result_ref"):
                    continue
                self._walk(value, (result_key,), False)
        window = envelope.get("data_window") or {}
        start = window.get("from")
        if start:
            moment = datetime.fromisoformat(str(start))
            if self.data_window_from is None or moment < self.data_window_from:
                self.data_window_from = moment

    # --- queries -------------------------------------------------------------------------------

    def has(self, key: str) -> bool:
        return key in self.entries

    def label(self, key: str) -> str:
        return self.entries[key].label

    def all_numbers(self) -> set[Decimal]:
        numbers = set(self.text_numbers)
        for entry in self.entries.values():
            numbers |= entry.numbers | entry.estimate_numbers
        return numbers
