"""AnswerValidator: checks a candidate answer against the turn's evidence ledger (§6).

Soft failures are repaired in place and flagged (an unverifiable reference is dropped, an item
left without a source is removed, markup is stripped). Hard failures (schema, action claims,
"loss" wording for exposure, nothing grounded left) reject the answer: the live path gets one
repair round-trip, then falls back to the deterministic provider. Deterministic answers pass the
same checks, which makes the validator a regression test of the templates.

Hard-error strings contain only codes and field paths generated here, never untrusted text, so
they can be sent back to a model in the repair message.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from pydantic import ValidationError

from app.domains.ai.answer import (
    MAX_LIMITATIONS,
    MAX_REFERENCES,
    CandidateAnswer,
    CandidateNoteDraft,
    DataWindow,
    NoteDraft,
    Reference,
    StructuredAnswer,
)
from app.domains.ai.ledger import EvidenceLedger, numbers_in_text, parse_metric_value

UNSUPPORTED_LIMITATION = "{n} statements were removed because their sources could not be verified."
UNGROUNDED_LIMITATION = "Some figures in the summary could not be matched to source records."

_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_HTML = re.compile(r"</?[a-zA-Z][^>]*>")
_ACTION_CLAIM = re.compile(
    r"\bI(?:'ve|\s+have|\s+just|\s+already)?\s+(?:already\s+|just\s+)?"
    r"(?:resolved|assigned|reassigned|unassigned|updated|dismissed|closed|reopened|acknowledged"
    r"|changed|saved|added|created|deleted|removed|imported|applied|marked|fixed|escalated"
    r"|notified|emailed|contacted|cancell?ed|refunded|adjusted)\b"
    r"|\bI(?:'ll|\s+will)\s+(?:now\s+)?(?:resolve|assign|dismiss|update|close|reopen|change|fix"
    r"|delete|import|apply|refund|cancel)\b"
    r"|\bdone,\s+(?:I\s+)?(?:updated|resolved|assigned)\b"
    r"|\bhas\s+been\s+(?:resolved|assigned|dismissed|updated)\s+by\s+me\b",
    re.IGNORECASE,
)
_PROHIBITED = re.compile(r"\b(?:lost\s+revenue|revenue\s+lost|loss|losses)\b", re.IGNORECASE)


@dataclass
class ValidationReport:
    dropped_refs: int = 0
    dropped_items: int = 0
    flags: list[str] = field(default_factory=list)

    def flag(self, code: str) -> None:
        if code not in self.flags:
            self.flags.append(code)

    def as_json(self) -> dict[str, Any]:
        return {
            "dropped_refs": self.dropped_refs,
            "dropped_items": self.dropped_items,
            "flags": list(self.flags),
        }


@dataclass
class AnswerValidation:
    answer: StructuredAnswer | None
    report: ValidationReport
    hard_errors: list[str]

    @property
    def ok(self) -> bool:
        return self.answer is not None and not self.hard_errors


@dataclass
class NoteValidation:
    draft: NoteDraft | None
    report: ValidationReport
    hard_errors: list[str]

    @property
    def ok(self) -> bool:
        return self.draft is not None and not self.hard_errors


def _strip_markup(text: str, report: ValidationReport) -> str:
    cleaned = _IMAGE.sub("", text)
    cleaned = _LINK.sub(r"\1", cleaned)
    cleaned = _URL.sub("", cleaned)
    cleaned = _HTML.sub("", cleaned)
    if cleaned != text:
        report.flag("MARKUP_REMOVED")
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    return cleaned


def _grounded(token: Decimal, numbers: set[Decimal]) -> bool:
    """A number in text matches a ledger number, allowing rounding to the displayed precision."""
    if token in numbers or -token in numbers:
        return True
    exponent = token.as_tuple().exponent
    if not isinstance(exponent, int):  # pragma: no cover - NaN/Infinity never match the pattern
        return False
    quantum = Decimal(1).scaleb(exponent)
    for number in numbers:
        try:
            if abs(number).quantize(quantum, rounding=ROUND_HALF_UP) == abs(token):
                return True
        except InvalidOperation:  # pragma: no cover - quantize overflow on huge values
            continue
    return False


def _ungrounded(texts: list[str], ledger: EvidenceLedger) -> bool:
    numbers = ledger.all_numbers()
    return any(not _grounded(token, numbers) for text in texts for token in numbers_in_text(text))


def _schema_errors(err: ValidationError) -> list[str]:
    return [
        f"SCHEMA_INVALID at {'.'.join(str(p) for p in e['loc']) or 'answer'}: {e['type']}"
        for e in err.errors()[:10]
    ]


def _limitations(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    for group in groups:
        for item in group:
            if item and item not in merged:
                merged.append(item)
    return merged[:MAX_LIMITATIONS]


def _valid_refs(refs: list[str], ledger: EvidenceLedger, report: ValidationReport) -> list[str]:
    valid = list(dict.fromkeys(r for r in refs if ledger.has(r)))
    dropped = len(refs) - sum(1 for r in refs if ledger.has(r))
    if dropped:
        report.dropped_refs += dropped
        report.flag("UNVERIFIED_REF")
    return valid


def _references(
    candidate: list[Reference], used: list[str], ledger: EvidenceLedger, report: ValidationReport
) -> list[Reference]:
    keys: list[str] = []
    for item in candidate:
        key = f"{item.type}:{item.id}"
        if ledger.has(key):
            keys.append(key)
        else:
            report.dropped_refs += 1
            report.flag("UNVERIFIED_REF")
    keys.extend(used)
    out = []
    for key in list(dict.fromkeys(keys))[:MAX_REFERENCES]:
        entry = ledger.entries[key]
        out.append(
            Reference.model_validate(
                {"type": entry.type, "id": entry.id, "label": entry.label[:300]}
            )
        )
    return out


def validate_answer(
    raw: Any,
    ledger: EvidenceLedger,
    *,
    as_of: datetime,
    generated_by: str,
    server_limitations: list[str],
) -> AnswerValidation:
    report = ValidationReport()
    data = dict(raw) if isinstance(raw, dict) else raw
    if isinstance(data, dict):  # set by the server, whatever the model sent
        data.pop("data_window", None)
        data.pop("generated_by", None)
    try:
        candidate = CandidateAnswer.model_validate(data)
    except ValidationError as err:
        return AnswerValidation(None, report, _schema_errors(err))

    def strip(text: str) -> str:
        return _strip_markup(text, report)

    summary = strip(candidate.summary)
    facts = []
    for fact in candidate.facts:
        refs = _valid_refs(fact.refs, ledger, report)
        text = strip(fact.text)
        if not refs or not text:
            report.dropped_items += 1
            report.flag("UNSUPPORTED_ITEM")
            continue
        facts.append(fact.model_copy(update={"text": text, "refs": refs}))
    metrics = []
    for metric in candidate.metrics:
        refs = _valid_refs(metric.refs, ledger, report)
        if not refs:
            report.dropped_items += 1
            report.flag("UNSUPPORTED_ITEM")
            continue
        value = parse_metric_value(metric.value)
        entries = [ledger.entries[r] for r in refs]
        if value is None or not any(value in e.numbers for e in entries):
            report.dropped_items += 1
            in_estimate = value is not None and any(value in e.estimate_numbers for e in entries)
            report.flag("ESTIMATE_AS_METRIC" if in_estimate else "UNVERIFIED_METRIC")
            continue
        metrics.append(
            metric.model_copy(
                update={
                    "label": strip(metric.label),
                    "unit": strip(metric.unit),
                    "formula": strip(metric.formula) if metric.formula else None,
                    "refs": refs,
                }
            )
        )
    estimates = [
        e.model_copy(update={"text": strip(e.text), "basis": strip(e.basis)})
        for e in candidate.estimates
    ]
    if estimates and not ledger.has_estimates:
        report.dropped_items += len(estimates)
        report.flag("UNSUPPORTED_ESTIMATE")
        estimates = []
    recommendations = [
        r.model_copy(update={"text": strip(r.text), "rationale": strip(r.rationale)})
        for r in candidate.recommendations
    ]
    candidate_limitations = [strip(item) for item in candidate.limitations]
    used = [r for fact in facts for r in fact.refs] + [r for m in metrics for r in m.refs]
    references = _references(candidate.references, used, ledger, report)

    hard: list[str] = []
    if not summary:
        hard.append("SUMMARY_EMPTY at summary")
    claim_texts = {
        "summary": [summary],
        "facts": [f.text for f in facts],
        "recommendations": [t for r in recommendations for t in (r.text, r.rationale)],
        "limitations": candidate_limitations,
    }
    for name, texts in claim_texts.items():
        if any(_ACTION_CLAIM.search(t) for t in texts):
            hard.append(f"ACTION_CLAIM at {name}")
    prohibited_texts = {
        **claim_texts,
        "metrics": [t for m in metrics for t in (m.label, m.formula or "")],
        "estimates": [t for e in estimates for t in (e.text, e.basis)],
    }
    for name, texts in prohibited_texts.items():
        if any(_PROHIBITED.search(t) for t in texts):
            hard.append(f"PROHIBITED_TERM at {name}")
    if ledger.returned_records and not facts and not metrics:
        hard.append("NO_GROUNDED_CONTENT at facts")

    validator_limitations = []
    if report.dropped_items:
        validator_limitations.append(UNSUPPORTED_LIMITATION.format(n=report.dropped_items))
    free_text = [summary, *(t for r in recommendations for t in (r.text, r.rationale))]
    free_text += [e.text for e in estimates]
    if _ungrounded(free_text, ledger):
        report.flag("UNGROUNDED_NUMBER")
        validator_limitations.append(UNGROUNDED_LIMITATION)

    answer = StructuredAnswer(
        summary=summary or candidate.summary,
        facts=facts,
        metrics=metrics,
        estimates=estimates,
        recommendations=recommendations,
        limitations=_limitations(server_limitations, validator_limitations, candidate_limitations),
        references=references,
        data_window=DataWindow(from_=ledger.data_window_from, to=as_of),
        generated_by=generated_by,
    )
    return AnswerValidation(answer, report, hard)


def validate_note(
    raw: Any,
    ledger: EvidenceLedger,
    *,
    as_of: datetime,
    generated_by: str,
    user_hint: str | None,
    server_limitations: list[str],
) -> NoteValidation:
    """The note-draft variant: the same reference, number, claim and wording checks on the body.
    The user's own hint (quoted as "Reported: …") is excluded from the claim and number checks."""
    report = ValidationReport()
    try:
        candidate = CandidateNoteDraft.model_validate(raw)
    except ValidationError as err:
        return NoteValidation(None, report, _schema_errors(err))
    body = _strip_markup(candidate.body, report)
    refs = _valid_refs(candidate.refs, ledger, report)
    checked = body.replace(user_hint, " ") if user_hint else body

    hard: list[str] = []
    if not body:
        hard.append("BODY_EMPTY at body")
    if _ACTION_CLAIM.search(checked):
        hard.append("ACTION_CLAIM at body")
    if _PROHIBITED.search(body):
        hard.append("PROHIBITED_TERM at body")
    if ledger.returned_records and not refs:
        hard.append("NO_GROUNDED_CONTENT at refs")
    validator_limitations = []
    if _ungrounded([checked], ledger):
        report.flag("UNGROUNDED_NUMBER")
        validator_limitations.append(UNGROUNDED_LIMITATION)
    candidate_limitations = [_strip_markup(item, report) for item in candidate.limitations]
    draft = NoteDraft(
        body=body or candidate.body,
        refs=refs,
        limitations=_limitations(server_limitations, validator_limitations, candidate_limitations),
        references=_references([], refs, ledger, report),
        data_window=DataWindow(from_=ledger.data_window_from, to=as_of),
        generated_by=generated_by,
    )
    return NoteValidation(draft, report, hard)
