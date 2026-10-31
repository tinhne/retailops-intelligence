"""products.csv: upsert by SKU (BR-608), suppliers upserted by name.

Optional columns that are absent from the file keep the stored value; an empty cell in a present
column clears it. A supplier's lead time is only ever set, never cleared, by an import.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.domains.catalog import service as catalog
from app.domains.catalog.models import ProductStatus
from app.domains.imports.parsing import ParsedFile
from app.domains.imports.validation import (
    IssueCollector,
    RowPlan,
    RowReader,
    ValidationContext,
    ValidationResult,
    classify,
    duplicate_check,
)


@dataclass(frozen=True)
class ProductRow:
    data: catalog.ProductData
    supplier_lead_time_days: int | None


def validate(
    db: Session, ctx: ValidationContext, parsed: ParsedFile
) -> ValidationResult[ProductRow]:
    collector = IssueCollector(ctx.timezone)
    existing_products = catalog.find_products_by_sku(
        db, ctx.store_id, (row.values.get("sku", "") for row in parsed.rows)
    )
    existing_suppliers = catalog.find_suppliers_by_name(
        db, ctx.store_id, (row.values.get("supplier_name", "") for row in parsed.rows)
    )
    seen_skus: dict[str, int] = {}
    # supplier name -> (first row, lead time given there) for conflict detection within the file
    lead_times: dict[str, tuple[int, int]] = {}
    plans: list[RowPlan[ProductRow]] = []

    for parsed_row in parsed.rows:
        row = RowReader(parsed_row, ctx, collector)
        sku = row.text("sku", max_length=64, required=True)
        duplicate_check(row, seen_skus, sku, "sku", "SKU")
        name = row.text("name", max_length=200, required=True)
        category = row.text("category", max_length=100)
        status = row.enum("status", ProductStatus, required=True)
        unit_price = row.money("unit_price", required=True)
        unit_cost = row.money("unit_cost")
        reorder_point = row.integer("reorder_point", required=True)
        reorder_quantity = row.integer("reorder_quantity")
        supplier_name = row.text("supplier_name", max_length=200)
        lead_time = row.integer("supplier_lead_time_days", maximum=365)

        if lead_time is not None and supplier_name is None:
            row.error(
                "supplier_name",
                "REQUIRED",
                "supplier_name is required when supplier_lead_time_days is given.",
            )
        if supplier_name is not None and lead_time is not None:
            first = lead_times.setdefault(supplier_name, (parsed_row.row_number, lead_time))
            if first[1] != lead_time:
                row.error(
                    "supplier_lead_time_days",
                    "CONFLICTING_VALUE_IN_FILE",
                    f"Supplier {supplier_name} has lead time {first[1]} in row {first[0]}; one "
                    "file must give one lead time per supplier.",
                    str(lead_time),
                )

        if status is ProductStatus.ACTIVE and unit_price is not None and unit_price == 0:
            row.warning("unit_price", "PRICE_ZERO", "An ACTIVE product has a unit price of 0.")
        if unit_cost is not None and unit_price is not None and unit_cost > unit_price:
            row.warning(
                "unit_cost",
                "NEGATIVE_MARGIN",
                f"unit_cost {unit_cost} is higher than unit_price {unit_price}.",
                str(unit_cost),
            )

        existing = existing_products.get(sku) if sku else None
        if (
            row.has_errors
            or sku is None
            or name is None
            or status is None
            or unit_price is None
            or reorder_point is None
        ):
            plans.append(RowPlan(parsed_row.row_number, sku or "", *classify(row, None, [])))
            continue

        data = catalog.ProductData(
            sku=sku,
            name=name,
            category=_stored(parsed, "category", category, existing.category if existing else None),
            status=status,
            unit_price=unit_price,
            unit_cost=_stored(
                parsed, "unit_cost", unit_cost, existing.unit_cost if existing else None
            ),
            reorder_point=reorder_point,
            reorder_quantity=_stored(
                parsed,
                "reorder_quantity",
                reorder_quantity,
                existing.reorder_quantity if existing else None,
            ),
            supplier_name=_stored(
                parsed,
                "supplier_name",
                supplier_name,
                existing.supplier.name if existing and existing.supplier else None,
            ),
        )
        changed = catalog.product_changes(existing, data) if existing is not None else []
        if supplier_name is not None and lead_time is not None:
            known = existing_suppliers.get(supplier_name)
            first_row = lead_times[supplier_name][0] == parsed_row.row_number
            if first_row and (known is None or known.lead_time_days != lead_time):
                changed.append("supplier_lead_time_days")
        action, fields = classify(row, existing, changed)
        plans.append(
            RowPlan(
                parsed_row.row_number,
                sku,
                action,
                fields,
                ProductRow(data=data, supplier_lead_time_days=lead_time),
            )
        )
    return ValidationResult(plans=plans, issues=collector.finalize())


def _stored[T](parsed: ParsedFile, column: str, value: T, current: T) -> T:
    """An optional column absent from the file keeps the stored value (new rows: empty)."""
    return value if parsed.has_column(column) else current
