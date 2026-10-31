"""The structured answer contract (AI_ARCHITECTURE.md §5, PROMPT_DESIGN.md §6.2).

Every assistant message, from any provider, is one of these documents. ``CandidateAnswer`` is what
a provider proposes (the parameters of ``submit_answer``); the server validates it against the
turn's evidence ledger and completes it into a ``StructuredAnswer`` by setting ``data_window`` and
``generated_by`` itself.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RefTypeName = Literal["exception", "order", "product", "import", "evaluation_run", "aggregate"]
RefKey = str  # "type:id"

SUMMARY_MAX = 600
ITEM_TEXT_MAX = 300
MAX_FACTS = 12
MAX_METRICS = 12
MAX_ESTIMATES = 5
MAX_RECOMMENDATIONS = 5
MAX_LIMITATIONS = 8
MAX_REFERENCES = 60
NOTE_BODY_MAX = 1500


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Fact(_Strict):
    text: str = Field(min_length=1, max_length=ITEM_TEXT_MAX)
    refs: list[RefKey] = Field(max_length=20, description="Reference keys type:id; at least one.")


class Metric(_Strict):
    label: str = Field(min_length=1, max_length=80)
    value: str = Field(
        min_length=1, max_length=40, description="The number exactly as a tool returned it."
    )
    unit: str = Field(max_length=24, description="Store currency, orders, units, hours, ...")
    formula: str | None = Field(default=None, max_length=200)
    refs: list[RefKey] = Field(max_length=20)


class EstimateItem(_Strict):
    text: str = Field(min_length=1, max_length=ITEM_TEXT_MAX)
    basis: str = Field(min_length=1, max_length=200)


class Recommendation(_Strict):
    text: str = Field(min_length=1, max_length=ITEM_TEXT_MAX)
    rationale: str = Field(min_length=1, max_length=ITEM_TEXT_MAX)


class Reference(_Strict):
    type: RefTypeName
    id: str = Field(min_length=1, max_length=64)
    label: str = Field(max_length=300)


class CandidateAnswer(_Strict):
    """What a provider proposes. Unknown fields fail validation (hard)."""

    summary: str = Field(min_length=1, max_length=SUMMARY_MAX)
    facts: list[Fact] = Field(default_factory=list, max_length=MAX_FACTS)
    metrics: list[Metric] = Field(default_factory=list, max_length=MAX_METRICS)
    estimates: list[EstimateItem] = Field(default_factory=list, max_length=MAX_ESTIMATES)
    recommendations: list[Recommendation] = Field(
        default_factory=list, max_length=MAX_RECOMMENDATIONS
    )
    limitations: list[str] = Field(default_factory=list, max_length=MAX_LIMITATIONS)
    references: list[Reference] = Field(default_factory=list, max_length=MAX_REFERENCES)


class DataWindow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: datetime | None = Field(
        alias="from",
        description="Earliest lower bound of a time-bounded query in the turn; null when only "
        "current-state snapshots were used.",
    )
    to: datetime = Field(description="The turn's as_of.")


class StructuredAnswer(BaseModel):
    """A validated answer as stored and returned. Rendered by the UI as labelled sections."""

    summary: str
    facts: list[Fact]
    metrics: list[Metric]
    estimates: list[EstimateItem]
    recommendations: list[Recommendation]
    limitations: list[str]
    references: list[Reference] = Field(
        description="Every record the answer cites; labels are set by the server, not the model."
    )
    data_window: DataWindow
    generated_by: str = Field(description="'llm:<model id>' or 'deterministic'; set by the server.")


class CandidateNoteDraft(_Strict):
    """Parameters of ``submit_note_draft``."""

    body: str = Field(min_length=1, max_length=NOTE_BODY_MAX)
    refs: list[RefKey] = Field(default_factory=list, max_length=30)
    limitations: list[str] = Field(default_factory=list, max_length=MAX_LIMITATIONS)


class NoteDraft(BaseModel):
    """A validated note draft. Nothing is saved: a person edits it and saves it through the
    exception notes endpoint with ``source = AI_DRAFT_ACCEPTED``."""

    body: str
    refs: list[RefKey]
    limitations: list[str]
    references: list[Reference]
    data_window: DataWindow
    generated_by: str
