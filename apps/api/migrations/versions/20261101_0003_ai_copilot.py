"""ai copilot: session-scoped demo conversations, message metadata, tool-call refs

Revision ID: 0003_ai_copilot
Revises: 0002
Create Date: 2026-11-01 09:00:00.000000

Adds what the copilot (T-071..T-074) needs on the three ``ai_*`` tables from 0002:

- ``ai_conversation.session_id``: conversations of the shared public demo viewer are private to
  the browser session that started them (ADR-0011).
- ``ai_message``: ``kind``, ``as_of``, ``fallback_reason``, ``cache_key`` (investigation summary
  cache, AI_ARCHITECTURE.md §8.3), ``cache_generated_at``, ``validation`` flags, and a wider
  ``prompt_version``.
- ``ai_tool_call``: ``sequence``, ``origin``, ``result_refs`` (reference keys a result contained)
  and the final status vocabulary of TOOL_CATALOG.md §1.2.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_ai_copilot"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_STATUSES = (
    "SUCCESS",
    "INVALID_ARGUMENTS",
    "PERMISSION_DENIED",
    "NOT_FOUND",
    "TIMEOUT",
    "REJECTED_LIMIT",
    "UNKNOWN_TOOL",
    "ERROR",
)
_OLD_STATUSES = ("SUCCEEDED", "DENIED", "INVALID_ARGUMENTS", "FAILED")
_KINDS = ("CHAT", "INVESTIGATION_SUMMARY", "NOTE_DRAFT")
_ORIGINS = ("MODEL", "ROUTER", "CONTEXT_BUILDER")
_FALLBACK_REASONS = (
    "PROVIDER_RATE_LIMITED",
    "PROVIDER_TIMEOUT",
    "PROVIDER_ERROR",
    "BUDGET_EXCEEDED",
    "CIRCUIT_OPEN",
    "PROVIDER_NOT_CONFIGURED",
    "INVALID_OUTPUT",
)


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    """Upgrade schema."""
    # --- ai_conversation ------------------------------------------------------------------------
    op.add_column("ai_conversation", sa.Column("session_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_ai_conversation_session_id_user_session"),
        "ai_conversation",
        "user_session",
        ["session_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_ai_conversation_session_id"), "ai_conversation", ["session_id"], unique=False
    )

    # --- ai_message -----------------------------------------------------------------------------
    op.add_column(
        "ai_message",
        sa.Column("kind", sa.String(length=32), server_default="CHAT", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_ai_message_messagekind"), "ai_message", _in("kind", _KINDS)
    )
    op.add_column("ai_message", sa.Column("as_of", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ai_message", sa.Column("fallback_reason", sa.String(length=32), nullable=True))
    op.create_check_constraint(
        op.f("ck_ai_message_fallbackreason"),
        "ai_message",
        _in("fallback_reason", _FALLBACK_REASONS),
    )
    op.add_column("ai_message", sa.Column("cache_key", sa.String(length=64), nullable=True))
    op.add_column(
        "ai_message",
        sa.Column("cache_generated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "ai_message",
        sa.Column(
            "validation",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.alter_column(
        "ai_message",
        "prompt_version",
        existing_type=sa.String(length=40),
        type_=sa.String(length=200),
        existing_nullable=True,
    )
    op.create_index(
        "ix_ai_message_cache_key",
        "ai_message",
        ["cache_key", "created_at"],
        unique=False,
        postgresql_where=sa.text("cache_key IS NOT NULL"),
    )

    # --- ai_tool_call ---------------------------------------------------------------------------
    op.add_column(
        "ai_tool_call",
        sa.Column("sequence", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "ai_tool_call",
        sa.Column("origin", sa.String(length=24), server_default="MODEL", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_ai_tool_call_toolcallorigin"), "ai_tool_call", _in("origin", _ORIGINS)
    )
    op.add_column(
        "ai_tool_call",
        sa.Column(
            "result_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.drop_constraint(op.f("ck_ai_tool_call_toolcallstatus"), "ai_tool_call", type_="check")
    op.execute(
        "UPDATE ai_tool_call SET status = CASE status "
        "WHEN 'SUCCEEDED' THEN 'SUCCESS' WHEN 'DENIED' THEN 'PERMISSION_DENIED' "
        "WHEN 'FAILED' THEN 'ERROR' ELSE status END"
    )
    op.create_check_constraint(
        op.f("ck_ai_tool_call_toolcallstatus"), "ai_tool_call", _in("status", _NEW_STATUSES)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("ck_ai_tool_call_toolcallstatus"), "ai_tool_call", type_="check")
    op.execute(
        "UPDATE ai_tool_call SET status = CASE status "
        "WHEN 'SUCCESS' THEN 'SUCCEEDED' WHEN 'PERMISSION_DENIED' THEN 'DENIED' "
        "WHEN 'INVALID_ARGUMENTS' THEN 'INVALID_ARGUMENTS' ELSE 'FAILED' END"
    )
    op.create_check_constraint(
        op.f("ck_ai_tool_call_toolcallstatus"), "ai_tool_call", _in("status", _OLD_STATUSES)
    )
    op.drop_column("ai_tool_call", "result_refs")
    op.drop_constraint(op.f("ck_ai_tool_call_toolcallorigin"), "ai_tool_call", type_="check")
    op.drop_column("ai_tool_call", "origin")
    op.drop_column("ai_tool_call", "sequence")

    op.drop_index(
        "ix_ai_message_cache_key",
        table_name="ai_message",
        postgresql_where=sa.text("cache_key IS NOT NULL"),
    )
    op.alter_column(
        "ai_message",
        "prompt_version",
        existing_type=sa.String(length=200),
        type_=sa.String(length=40),
        existing_nullable=True,
        postgresql_using="left(prompt_version, 40)",
    )
    op.drop_column("ai_message", "validation")
    op.drop_column("ai_message", "cache_generated_at")
    op.drop_column("ai_message", "cache_key")
    op.drop_constraint(op.f("ck_ai_message_fallbackreason"), "ai_message", type_="check")
    op.drop_column("ai_message", "fallback_reason")
    op.drop_column("ai_message", "as_of")
    op.drop_constraint(op.f("ck_ai_message_messagekind"), "ai_message", type_="check")
    op.drop_column("ai_message", "kind")

    op.drop_index(op.f("ix_ai_conversation_session_id"), table_name="ai_conversation")
    op.drop_constraint(
        op.f("fk_ai_conversation_session_id_user_session"), "ai_conversation", type_="foreignkey"
    )
    op.drop_column("ai_conversation", "session_id")
