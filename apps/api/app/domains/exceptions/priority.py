"""Priority score, band, breakdown and due date (PRIORITY_MODEL.md). Pure functions, no I/O.

``priority_score = min(100, S + A + E + D + T)``. The breakdown returned with every score is what
the UI shows as "Why this priority". The score is a ranking aid, not a measure of money lost.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any

from app.domains.exceptions.models import PriorityBand, Severity
from app.domains.identity.models import DEFAULT_PRIORITY_WEIGHTS

FORMULA_VERSION = "priority/v1"
MAX_SCORE = 100

# Expected response per severity, used for due_at (PRIORITY_MODEL.md "Exception due date").
RESPONSE_HOURS: dict[Severity, int] = {
    Severity.CRITICAL: 4,
    Severity.HIGH: 24,
    Severity.MEDIUM: 72,
    Severity.LOW: 168,
}
_BANDS: tuple[tuple[int, PriorityBand], ...] = (
    (70, PriorityBand.P1),
    (50, PriorityBand.P2),
    (30, PriorityBand.P3),
)


def _int(value: Any, default: int) -> int:
    """Non-negative integer weight, falling back to the default for malformed values."""
    if isinstance(value, bool) or not isinstance(value, int | float | Decimal | str):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(number, 0)


@dataclass(frozen=True)
class PriorityWeights:
    severity: Mapping[Severity, int]
    affected_orders_per_order: int
    affected_orders_cap: int
    exposure_cap_points: int
    deadline_overdue: int
    deadline_within_24h: int
    deadline_within_72h: int
    age_points_per_day: int
    age_cap: int

    @classmethod
    def from_settings(cls, raw: Mapping[str, Any] | None) -> "PriorityWeights":
        """Build weights from ``store_settings.priority_weights`` merged over the defaults."""
        defaults = DEFAULT_PRIORITY_WEIGHTS
        data: Mapping[str, Any] = raw or {}
        sev_raw = data.get("severity")
        sev: Mapping[str, Any] = sev_raw if isinstance(sev_raw, Mapping) else {}
        dl_raw = data.get("deadline")
        dl: Mapping[str, Any] = dl_raw if isinstance(dl_raw, Mapping) else {}

        def top(key: str) -> int:
            return _int(data.get(key), int(defaults[key]))

        return cls(
            severity={
                s: _int(sev.get(s.value), int(defaults["severity"][s.value])) for s in Severity
            },
            affected_orders_per_order=top("affected_orders_per_order"),
            affected_orders_cap=top("affected_orders_cap"),
            exposure_cap_points=top("exposure_cap_points"),
            deadline_overdue=_int(dl.get("overdue"), int(defaults["deadline"]["overdue"])),
            deadline_within_24h=_int(dl.get("within_24h"), int(defaults["deadline"]["within_24h"])),
            deadline_within_72h=_int(dl.get("within_72h"), int(defaults["deadline"]["within_72h"])),
            age_points_per_day=top("age_points_per_day"),
            age_cap=top("age_cap"),
        )


DEFAULT_WEIGHTS = PriorityWeights.from_settings(DEFAULT_PRIORITY_WEIGHTS)


@dataclass(frozen=True)
class PriorityInputs:
    severity: Severity
    affected_order_count: int
    exposure_amount: Decimal
    deadline_at: datetime | None
    first_detected_at: datetime


@dataclass(frozen=True)
class PriorityResult:
    score: int
    band: PriorityBand
    breakdown: dict[str, Any]


def band_for(score: int) -> PriorityBand:
    """P1 ≥ 70, P2 50–69, P3 30–49, P4 < 30."""
    for threshold, band in _BANDS:
        if score >= threshold:
            return band
    return PriorityBand.P4


def exposure_points(value: Decimal, exposure_cap: Decimal, cap_points: int) -> int:
    """E = round(cap_E × log10(1 + v) / log10(1 + exposure_cap)), clamped to cap_E; 0 if v ≤ 0.

    Computed with Decimal logarithms (no float) and rounded half up.
    """
    if value <= 0 or cap_points <= 0:
        return 0
    if exposure_cap <= 0:
        return cap_points
    with localcontext() as ctx:
        ctx.prec = 28
        ratio = (Decimal(1) + value).log10() / (Decimal(1) + exposure_cap).log10()
        points = int((Decimal(cap_points) * ratio).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return min(points, cap_points)


def _deadline(
    deadline_at: datetime | None, as_of: datetime, weights: PriorityWeights
) -> tuple[int, str]:
    """D: passed (deadline_at ≤ as_of) → overdue points; 0 < Δ ≤ 24 h; 24 h < Δ ≤ 72 h; else 0."""
    if deadline_at is None:
        return 0, "No business deadline applies."
    remaining = deadline_at - as_of
    hours_left = _hours_text(abs(remaining))
    if remaining <= timedelta(0):
        return weights.deadline_overdue, f"The business deadline passed {hours_left} ago."
    if remaining <= timedelta(hours=24):
        return weights.deadline_within_24h, f"The business deadline is in {hours_left} (≤ 24 h)."
    if remaining <= timedelta(hours=72):
        return weights.deadline_within_72h, f"The business deadline is in {hours_left} (≤ 72 h)."
    return 0, f"The business deadline is more than 72 h away ({hours_left})."


def _hours_text(delta: timedelta) -> str:
    total_hours = int(delta.total_seconds() // 3600)
    if total_hours >= 48:
        return f"{total_hours // 24} d {total_hours % 24} h"
    minutes = int(delta.total_seconds() // 60)
    if total_hours == 0:
        return f"{minutes} min"
    return f"{total_hours} h"


def compute_priority(
    inputs: PriorityInputs,
    *,
    weights: PriorityWeights,
    exposure_cap: Decimal,
    as_of: datetime,
) -> PriorityResult:
    s_points = weights.severity[inputs.severity]
    s_max = max(weights.severity.values())

    n = max(inputs.affected_order_count, 0)
    a_points = min(weights.affected_orders_cap, weights.affected_orders_per_order * n)

    exposure = inputs.exposure_amount
    e_points = exposure_points(exposure, exposure_cap, weights.exposure_cap_points)

    d_points, d_text = _deadline(inputs.deadline_at, as_of, weights)
    d_max = max(weights.deadline_overdue, weights.deadline_within_24h, weights.deadline_within_72h)

    days = max((as_of - inputs.first_detected_at) // timedelta(days=1), 0)
    t_points = min(weights.age_cap, weights.age_points_per_day * days)

    raw = s_points + a_points + e_points + d_points + t_points
    score = min(MAX_SCORE, raw)
    band = band_for(score)
    components = [
        {
            "key": "severity",
            "label": "Severity",
            "points": s_points,
            "max_points": s_max,
            "explanation": f"{inputs.severity.value} severity scores {s_points} points.",
        },
        {
            "key": "affected_orders",
            "label": "Affected orders",
            "points": a_points,
            "max_points": weights.affected_orders_cap,
            "explanation": (
                f"{n} affected order{'s' if n != 1 else ''} × "
                f"{weights.affected_orders_per_order} points, capped at "
                f"{weights.affected_orders_cap}."
            ),
        },
        {
            "key": "exposure",
            "label": "Value at risk",
            "points": e_points,
            "max_points": weights.exposure_cap_points,
            "explanation": (
                f"Gross order-line value at risk {exposure:.2f} on a logarithmic scale up to "
                f"{exposure_cap:.2f} (not a measured loss)."
                if exposure > 0
                else "No order-line value is at risk."
            ),
        },
        {
            "key": "deadline",
            "label": "Deadline",
            "points": d_points,
            "max_points": d_max,
            "explanation": d_text,
        },
        {
            "key": "age",
            "label": "Time unresolved",
            "points": t_points,
            "max_points": weights.age_cap,
            "explanation": (
                f"Unresolved for {days} whole day{'s' if days != 1 else ''} × "
                f"{weights.age_points_per_day} points, capped at {weights.age_cap}."
            ),
        },
    ]
    breakdown: dict[str, Any] = {
        "components": components,
        "total": score,
        "uncapped_total": raw,
        "band": band.value,
        "formula_version": FORMULA_VERSION,
        "as_of": as_of.isoformat(),
    }
    return PriorityResult(score=score, band=band, breakdown=breakdown)


@dataclass(frozen=True)
class DueDate:
    due_at: datetime
    basis: str  # "SEVERITY" | "DEADLINE"
    anchor_at: datetime
    response_hours: int

    def as_json(self) -> dict[str, Any]:
        explanation = (
            f"Business deadline, earlier than the {self.response_hours} h response target."
            if self.basis == "DEADLINE"
            else f"{self.response_hours} h response target for this severity."
        )
        return {
            "due_at": self.due_at.isoformat(),
            "basis": self.basis,
            "anchor_at": self.anchor_at.isoformat(),
            "response_hours": self.response_hours,
            "explanation": explanation,
        }


def compute_due_at(
    severity: Severity, anchor_at: datetime, deadline_at: datetime | None
) -> DueDate:
    """``due_at = anchor + response_hours(severity)``; an earlier future deadline wins.

    ``anchor_at`` is ``first_detected_at`` (or the reopen time for a reopened exception). The
    deadline counts when ``anchor_at < deadline_at < anchor_at + response_hours``.
    """
    response = RESPONSE_HOURS[severity]
    base = anchor_at + timedelta(hours=response)
    if deadline_at is not None and anchor_at < deadline_at < base:
        return DueDate(deadline_at, "DEADLINE", anchor_at, response)
    return DueDate(base, "SEVERITY", anchor_at, response)
