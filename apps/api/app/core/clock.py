"""The single place that reads the wall clock.

Domain rules never call this; they receive ``as_of`` explicitly (BR-504). Request handlers and
services that need "now" call ``utcnow()`` so tests can substitute it.
"""

from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)
