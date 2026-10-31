"""Import every module's models so the metadata (and Alembic autogenerate) sees all tables."""

from app.domains.audit import models as audit_models
from app.domains.identity import models as identity_models

__all__ = ["audit_models", "identity_models"]
