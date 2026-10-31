"""Import every module's models so the metadata (and Alembic autogenerate) sees all tables."""

from app.domains.ai import models as ai_models
from app.domains.audit import models as audit_models
from app.domains.catalog import models as catalog_models
from app.domains.exceptions import models as exceptions_models
from app.domains.identity import models as identity_models
from app.domains.imports import models as imports_models
from app.domains.inventory import models as inventory_models
from app.domains.orders import models as orders_models

__all__ = [
    "ai_models",
    "audit_models",
    "catalog_models",
    "exceptions_models",
    "identity_models",
    "imports_models",
    "inventory_models",
    "orders_models",
]
