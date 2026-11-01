"""The ``deterministic`` provider: intent router, tool plans and answer templates (AI §7).

No network calls, always available, and the fallback for every live-provider failure. It plugs
into the same turn as the live adapters: its plan's calls run stage by stage through the tool
registry, then a template renders the candidate answer, which passes the same validator.
``generated_by`` is ``deterministic``.
"""

from typing import Any

from app.domains.ai.models import ToolCallOrigin
from app.domains.ai.providers.deterministic.plans import (
    MAX_STAGES,
    PlanContext,
    PlannedCall,
    Results,
    next_calls,
)
from app.domains.ai.providers.deterministic.router import RoutedIntent
from app.domains.ai.tools.registry import TurnTools

NAME = "deterministic"


def gather(
    routed: RoutedIntent, tools: TurnTools, ctx: PlanContext, origin: ToolCallOrigin
) -> tuple[Results, list[tuple[PlannedCall, dict[str, Any]]]]:
    """Run the intent's plan through the registry. Returns the results by key and the executed
    calls in order (the live path injects them as already-executed tool calls)."""
    results: Results = {}
    executed: list[tuple[PlannedCall, dict[str, Any]]] = []
    for _ in range(MAX_STAGES):
        calls = next_calls(routed, results, ctx)
        if not calls:
            break
        for call in calls:
            envelope = tools.execute(call.tool, call.args, origin)
            results[call.key] = envelope
            executed.append((call, envelope))
    return results, executed
