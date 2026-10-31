"""Reusable column types."""

import enum
from typing import Any

from sqlalchemy import Enum as SAEnum


def str_enum(enum_cls: type[enum.Enum], length: int = 40, *, name: str | None = None) -> SAEnum:
    """Store a Python enum as VARCHAR with a CHECK constraint on its values.

    Non-native enums keep migrations simple: adding a value is a constraint change, not an
    ``ALTER TYPE`` that cannot run inside a transaction. ``name`` names the CHECK constraint and
    is required when one table has two columns of the same enum.
    """

    def _values(cls: Any) -> list[str]:
        return [member.value for member in cls]

    return SAEnum(
        enum_cls,
        name=name or enum_cls.__name__.lower(),
        native_enum=False,
        create_constraint=True,
        length=length,
        values_callable=_values,
        validate_strings=True,
    )
