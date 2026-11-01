"""Prompt versioning and compactness (PROMPT_DESIGN.md §1, §8)."""

import json
from pathlib import Path

from app.domains.ai import prompts
from app.domains.ai.providers.deterministic.router import table_text
from app.domains.ai.tools.registry import TOOLS

LOCK = Path(prompts.__file__).parent / "prompts.lock.json"
PREFIX_BUDGET = 14_000


def test_prompt_texts_match_the_lock_file() -> None:
    """A text change without a version bump fails here: bump the version, update the lock file,
    PROMPT_DESIGN.md and the changelog in the same commit."""
    lock = json.loads(LOCK.read_text())
    for prompt in prompts.PROMPTS:
        assert lock[prompt.key] == prompts.sha256(prompt.text), prompt.key
    assert lock[f"tools@{prompts.TOOLS_VERSION}"] == prompts.tools_hash(list(TOOLS.values()))
    router_key = f"deterministic.router@{prompts.DETERMINISTIC_ROUTER_VERSION}"
    assert lock[router_key] == prompts.sha256(table_text())


def test_static_prefix_stays_within_its_character_budget() -> None:
    """System prompt + largest task block + all tool definitions + the output function, rendered
    as the adapters send them."""
    definitions = prompts.tool_definitions(list(TOOLS.values()))
    task = max(len(prompts.INVESTIGATION_SUMMARY.text), len(prompts.NOTE_DRAFT.text))
    size = (
        len(prompts.SYSTEM.text)
        + task
        + len(
            json.dumps(
                [*definitions, prompts.output_definition(prompts.SUBMIT_ANSWER)],
                separators=(",", ":"),
            )
        )
    )
    assert size <= PREFIX_BUDGET, size


def test_tool_definitions_are_self_contained_and_scope_free() -> None:
    for definition in prompts.tool_definitions(list(TOOLS.values())):
        encoded = json.dumps(definition)
        assert "$ref" not in encoded
        assert "$defs" not in encoded
        assert "store_id" not in definition["parameters"].get("properties", {})
        assert definition["description"].endswith(".")


def test_prompt_version_strings() -> None:
    assert prompts.version_string(prompts.SYSTEM) == "copilot.system@1;tools@1"
    assert prompts.version_string(prompts.SYSTEM, prompts.INVESTIGATION_SUMMARY) == (
        "copilot.system@1;copilot.investigation_summary@1;tools@1"
    )
    assert prompts.deterministic_version() == (
        "deterministic.router@1;deterministic.templates@1;tools@1"
    )
