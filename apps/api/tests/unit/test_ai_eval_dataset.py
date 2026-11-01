"""Integrity of the copilot evaluation dataset (EVALUATION_STRATEGY.md §2.3, §2.5)."""

from collections import Counter
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.domains.ai.providers.deterministic.router import Intent, route
from app.domains.ai.tools.registry import TOOLS
from evals.assertions import TYPES
from evals.oracles import ORACLES

DATASET = Path(__file__).resolve().parents[2] / "evals" / "dataset" / "copilot_v1.yaml"
ROLES = {"OWNER", "MANAGER", "STAFF", "ANALYST", "VIEWER", "NO_ORDERS", "NO_COPILOT"}


def cases() -> list[dict[str, Any]]:
    data = yaml.safe_load(DATASET.read_text())
    assert data["dataset"] == "copilot_v1"
    loaded: list[dict[str, Any]] = data["cases"]
    return loaded


def test_dataset_is_well_formed() -> None:
    items = cases()
    ids = [c["id"] for c in items]
    assert len(ids) == len(set(ids))
    assert len(items) >= 60
    for case in items:
        assert case["role"] in ROLES, case["id"]
        if "expected_intent" in case:
            assert case["expected_intent"] in Intent.__members__, case["id"]
        for tool in [t for names in (case.get("tools") or {}).values() for t in names]:
            assert tool in TOOLS, (case["id"], tool)
        for assertion in case.get("assertions", []):
            assert assertion["type"] in TYPES, (case["id"], assertion)
            if "oracle" in assertion:
                assert assertion["oracle"] in ORACLES, (case["id"], assertion)
            for value in (assertion.get("args") or {}).values():
                if assertion.get("args", {}).get("var") == value:
                    assert value in (case.get("select") or {}), (case["id"], value)
        if case.get("endpoint") in ("summary", "note_draft"):
            assert case["target"] in case["select"], case["id"]


def test_planned_coverage() -> None:
    counts = Counter(c["category"] for c in cases())
    seven_questions = (
        "attention_today",
        "top_priority",
        "overdue_orders",
        "oversell_risk",
        "changes_since_yesterday",
        "explain_exception",
        "team_priorities",
    )
    assert all(counts[c] >= 3 for c in seven_questions)
    assert counts["investigation_summary"] == 9  # one per exception type
    assert counts["note_draft"] >= 3
    assert counts["out_of_scope"] >= 6
    assert counts["write_request"] >= 4
    assert counts["permission"] + counts["tenancy"] >= 6
    assert counts["injection"] >= 5
    assert counts["provider_failure"] == 3


@pytest.mark.parametrize(
    "case",
    [
        c
        for c in cases()
        if c.get("question") and "{" not in c["question"] and "expected_intent" in c
    ],
    ids=lambda c: c["id"],
)
def test_literal_questions_route_to_their_expected_intent(case: dict[str, Any]) -> None:
    assert route(case["question"]).intent.value == case["expected_intent"]
