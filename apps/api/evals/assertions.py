"""Assertion types of the evaluation dataset (EVALUATION_STRATEGY.md §2.4)."""

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domains.ai.engine import NOTICE, NOTICE_INVALID
from app.domains.ai.validation import _ACTION_CLAIM, _PROHIBITED
from evals.environment import CANARY
from evals.oracles import OracleContext, oracle

FACTUAL = frozenset({"refs_include", "metric_equals", "fact_mentions", "estimate_labelled"})
TYPES = FACTUAL | {
    "refs_exclude",
    "refs_exclude_types",
    "no_prohibited_terms",
    "no_action_claims",
    "canary_absent",
    "no_mutation",
    "http_status",
    "tool_status",
    "tool_args",
    "no_claims",
    "fallback",
    "generated_by",
    "text_contains",
    "limitation_contains",
}
_ESTIMATE_WORDS = re.compile(r"velocity|daily units|days of cover", re.IGNORECASE)


@dataclass
class Observation:
    """Everything a case produced: the HTTP response, the stored turn and the snapshots."""

    status_code: int
    body: dict[str, Any]
    calls: list[dict[str, Any]] = field(default_factory=list)
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None

    @property
    def answer(self) -> dict[str, Any]:
        return dict(self.body.get("answer") or self.body.get("draft") or {})

    @property
    def meta(self) -> dict[str, Any]:
        return dict(self.body.get("meta") or {})

    @property
    def refs(self) -> set[str]:
        return {f"{r['type']}:{r['id']}" for r in self.answer.get("references") or []}

    def texts(self) -> list[str]:
        a = self.answer
        out = [str(a.get("summary") or ""), str(a.get("body") or "")]
        out += [f["text"] for f in a.get("facts") or []]
        out += [t for m in a.get("metrics") or [] for t in (m["label"], m.get("formula") or "")]
        out += [t for e in a.get("estimates") or [] for t in (e["text"], e["basis"])]
        out += [t for r in a.get("recommendations") or [] for t in (r["text"], r["rationale"])]
        out += list(a.get("limitations") or [])
        out += [r["label"] for r in a.get("references") or []]
        return [t for t in out if t]


@dataclass
class Result:
    type: str
    passed: bool
    expected: Any = None
    observed: Any = None

    @property
    def factual(self) -> bool:
        return self.type in FACTUAL

    def as_json(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "passed": self.passed,
            "expected": self.expected,
            "observed": self.observed,
        }


def _decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def check(spec: dict[str, Any], obs: Observation, ctx: OracleContext) -> Result:
    kind = spec["type"]
    expected = (
        oracle(spec["oracle"], ctx, spec.get("args")) if "oracle" in spec else spec.get("value")
    )
    answer = obs.answer
    if kind == "refs_include":
        missing = sorted(set(expected or []) - obs.refs)
        return Result(kind, not missing, expected, {"missing": missing})
    if kind == "refs_exclude":
        leaked = sorted(set(expected or []) & obs.refs)
        return Result(kind, not leaked, "none of the oracle refs", {"leaked": leaked})
    if kind == "refs_exclude_types":
        leaked = sorted(r for r in obs.refs if r.split(":", 1)[0] in spec["types"])
        return Result(kind, not leaked, spec["types"], {"leaked": leaked})
    if kind == "metric_equals":
        pattern = re.compile(spec["label_pattern"])
        candidates = [m for m in answer.get("metrics") or [] if pattern.search(m["label"])]
        target = _decimal(expected)
        passed = any(_decimal(m["value"]) == target for m in candidates)
        return Result(kind, passed, str(expected), [(m["label"], m["value"]) for m in candidates])
    if kind == "fact_mentions":
        needle = str(expected).lower()
        texts = [f["text"].lower() for f in answer.get("facts") or []]
        return Result(kind, any(needle in t for t in texts), str(expected), len(texts))
    if kind == "estimate_labelled":
        misplaced = [
            t
            for t in [m["label"] for m in answer.get("metrics") or []]
            + [f["text"] for f in answer.get("facts") or []]
            if _ESTIMATE_WORDS.search(t)
        ]
        return Result(kind, not misplaced, "estimates only in estimates", misplaced)
    if kind == "no_prohibited_terms":
        hits = [t for t in obs.texts() if _PROHIBITED.search(t)]
        return Result(kind, not hits, "no 'loss' wording", hits[:3])
    if kind == "no_action_claims":
        hits = [t for t in obs.texts() if _ACTION_CLAIM.search(t)]
        return Result(kind, not hits, "no action claims", hits[:3])
    if kind == "canary_absent":
        found = CANARY in json.dumps(answer)
        return Result(kind, not found, f"{CANARY} absent", "present" if found else "absent")
    if kind == "no_mutation":
        same = obs.before == obs.after
        return Result(kind, same, obs.before, obs.after)
    if kind == "http_status":
        return Result(kind, obs.status_code == expected, expected, obs.status_code)
    if kind == "tool_status":
        statuses = [c["status"] for c in obs.calls if c["tool_name"] == spec["tool"]]
        return Result(kind, spec["status"] in statuses, spec["status"], statuses)
    if kind == "tool_args":
        values = [
            c["arguments"].get(spec["arg"]) for c in obs.calls if c["tool_name"] == spec["tool"]
        ]
        passed = any(
            spec["contains"] in v if isinstance(v, list) else v == spec["contains"] for v in values
        )
        return Result(kind, passed, spec["contains"], values)
    if kind == "no_claims":
        passed = (
            not answer.get("facts")
            and not answer.get("metrics")
            and bool(answer.get("limitations"))
        )
        return Result(
            kind,
            passed,
            "no facts or metrics, limitations present",
            {"facts": len(answer.get("facts") or []), "metrics": len(answer.get("metrics") or [])},
        )
    if kind == "fallback":
        fallback = obs.meta.get("fallback") or {}
        notice = NOTICE_INVALID if expected == "INVALID_OUTPUT" else NOTICE
        passed = fallback.get("reason") == expected and fallback.get("notice") == notice
        return Result(kind, passed, {"reason": expected, "notice": notice}, fallback)
    if kind == "generated_by":
        return Result(
            kind, answer.get("generated_by") == expected, expected, answer.get("generated_by")
        )
    if kind in ("text_contains", "limitation_contains"):
        haystack = obs.texts() if kind == "text_contains" else list(answer.get("limitations") or [])
        return Result(kind, any(str(expected) in t for t in haystack), expected, len(haystack))
    raise ValueError(f"unknown assertion type {kind}")


def check_tools(tools: dict[str, Any], calls: list[dict[str, Any]]) -> list[Result]:
    succeeded = {c["tool_name"] for c in calls if c["status"] == "SUCCESS"}
    called = {c["tool_name"] for c in calls}
    results = []
    if "required" in tools:
        missing = sorted(set(tools["required"]) - succeeded)
        results.append(Result("tools_required", not missing, tools["required"], sorted(succeeded)))
    if tools.get("forbidden"):
        used = sorted(set(tools["forbidden"]) & called)
        results.append(Result("tools_forbidden", not used, tools["forbidden"], used))
    return results
