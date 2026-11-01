"""Versioned prompts and tool definitions for the live providers (PROMPT_DESIGN.md §8).

Every prompt has an id and an integer version. ``prompts.lock.json`` maps ``id@version`` to the
SHA-256 of the text (and ``tools@N`` to the hash of the rendered tool definitions); a unit test
fails when a text changes without a version bump. Each assistant message records the versions that
produced it in ``ai_message.prompt_version``.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.domains.ai.answer import CandidateAnswer, CandidateNoteDraft
from app.domains.ai.prompts import texts
from app.domains.ai.tools.base import ToolSpec


@dataclass(frozen=True)
class Prompt:
    id: str
    version: int
    text: str

    @property
    def key(self) -> str:
        return f"{self.id}@{self.version}"


SYSTEM = Prompt("copilot.system", 1, texts.SYSTEM_V1)
INVESTIGATION_SUMMARY = Prompt("copilot.investigation_summary", 1, texts.INVESTIGATION_SUMMARY_V1)
NOTE_DRAFT = Prompt("copilot.note_draft", 1, texts.NOTE_DRAFT_V1)
REPAIR = Prompt("copilot.repair", 1, texts.REPAIR_V1)
FINALIZE = Prompt("copilot.finalize", 1, texts.FINALIZE_V1)
PROMPTS = (SYSTEM, INVESTIGATION_SUMMARY, NOTE_DRAFT, REPAIR, FINALIZE)

TOOLS_VERSION = 1
DETERMINISTIC_ROUTER_VERSION = 1
DETERMINISTIC_TEMPLATES_VERSION = 1

SUBMIT_ANSWER = "submit_answer"
SUBMIT_NOTE_DRAFT = "submit_note_draft"


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# --- tool definitions ----------------------------------------------------------------------------

_KEEP = ("type", "enum", "format", "description")


def compact_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Pydantic JSON Schema → a compact, self-contained subset that providers accept: ``$ref``
    inlined, ``Optional[X]`` as ``X`` (absent from ``required``), no titles, defaults, length or
    list caps, and no ``additionalProperties``. Only numeric ranges stay. Pydantic still enforces
    the full schema (unknown fields, lengths, caps) on every call, and the system prompt states
    the answer caps, so the prefix stays within its character budget (PROMPT_DESIGN.md §1)."""
    defs: dict[str, Any] = schema.get("$defs", {})

    def convert(node: dict[str, Any]) -> dict[str, Any]:
        if "$ref" in node:
            node = defs[node["$ref"].rsplit("/", 1)[-1]]
        if "anyOf" in node:
            options = [o for o in node["anyOf"] if o.get("type") != "null"]
            if len(options) == 1:
                merged = convert(options[0])
                if "description" in node:
                    merged["description"] = node["description"]
                return merged
        out: dict[str, Any] = {k: node[k] for k in _KEEP if k in node}
        if "const" in node:
            out["enum"] = [node["const"]]
        if "minimum" in node or "exclusiveMinimum" in node:
            out["minimum"] = node.get("minimum", node.get("exclusiveMinimum"))
        if "maximum" in node or "exclusiveMaximum" in node:
            out["maximum"] = node.get("maximum", node.get("exclusiveMaximum"))
        if "items" in node:
            out["items"] = convert(node["items"])
        if node.get("type") == "object" or "properties" in node:
            out["type"] = "object"
            out["properties"] = {
                name: convert(prop) for name, prop in (node.get("properties") or {}).items()
            }
            required = node.get("required")
            if required:
                out["required"] = list(required)
        return out

    root = convert(schema)
    root.pop("description", None)  # class docstrings are for developers, not the model
    return root


def _definition(name: str, description: str, model: type[BaseModel]) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "parameters": compact_schema(model.model_json_schema()),
    }


def tool_definitions(specs: list[ToolSpec]) -> list[dict[str, Any]]:
    """Provider-neutral definitions, in catalog order, of the tools the caller may use."""
    return [_definition(s.name, s.description, s.args_model) for s in specs]


def output_definition(name: str) -> dict[str, Any]:
    if name == SUBMIT_NOTE_DRAFT:
        return _definition(
            name,
            "Submit the drafted note. A person reviews it before anything is saved.",
            CandidateNoteDraft,
        )
    return _definition(name, "Submit the final structured answer.", CandidateAnswer)


def tools_hash(specs: list[ToolSpec]) -> str:
    return sha256(json.dumps(tool_definitions(specs), sort_keys=True))


def version_string(*prompts: Prompt) -> str:
    """For example ``copilot.system@1;copilot.investigation_summary@1;tools@1``."""
    return ";".join([*(p.key for p in prompts), f"tools@{TOOLS_VERSION}"])


def deterministic_version() -> str:
    return (
        f"deterministic.router@{DETERMINISTIC_ROUTER_VERSION};"
        f"deterministic.templates@{DETERMINISTIC_TEMPLATES_VERSION};tools@{TOOLS_VERSION}"
    )
