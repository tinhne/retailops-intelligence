"""CSV column contracts and downloadable templates for each import type (BR-601).

The contracts are the single source for header validation, the template endpoint and the files in
``sample-data/templates`` (a unit test keeps those files identical to ``render_template``).
"""

import csv
import io
from dataclasses import dataclass

from app.domains.imports.models import ImportType


@dataclass(frozen=True)
class Column:
    name: str
    required: bool


@dataclass(frozen=True)
class ImportContract:
    import_type: ImportType
    key_description: str
    columns: tuple[Column, ...]
    examples: tuple[tuple[str, ...], ...]

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(column.name for column in self.columns)

    @property
    def required_columns(self) -> tuple[str, ...]:
        return tuple(column.name for column in self.columns if column.required)


def _req(name: str) -> Column:
    return Column(name, required=True)


def _opt(name: str) -> Column:
    return Column(name, required=False)


PRODUCTS = ImportContract(
    import_type=ImportType.PRODUCTS,
    key_description="sku",
    columns=(
        _req("sku"),
        _req("name"),
        _opt("category"),
        _req("status"),
        _req("unit_price"),
        _opt("unit_cost"),
        _req("reorder_point"),
        _opt("reorder_quantity"),
        _opt("supplier_name"),
        _opt("supplier_lead_time_days"),
    ),
    examples=(
        (
            "KHK-MUG-12OZ-SAGE",
            "Stoneware Mug 12 oz, Sage",
            "Drinkware",
            "ACTIVE",
            "16.00",
            "5.40",
            "24",
            "72",
            "Harbor Ceramics Co.",
            "21",
        ),
        (
            "KHK-KNF-CHEF-8",
            "Chef's Knife 8 in, Carbon Steel",
            "Cutlery",
            "ACTIVE",
            "89.00",
            "34.50",
            "6",
            "18",
            "Northfield Blades",
            "35",
        ),
    ),
)

ORDERS = ImportContract(
    import_type=ImportType.ORDERS,
    key_description="order_number",
    columns=(
        _req("order_number"),
        _opt("channel"),
        _opt("customer_ref"),
        _req("placed_at"),
        _req("status"),
        _req("payment_status"),
        _opt("fulfillment_status"),
        _opt("paid_at"),
        _opt("ship_by"),
        _opt("shipped_at"),
        _opt("delivered_at"),
        _opt("cancelled_at"),
        _req("currency"),
        _req("subtotal"),
        _opt("discount_total"),
        _opt("shipping_total"),
        _opt("tax_total"),
        _req("total"),
        _opt("carrier"),
        _opt("tracking_number"),
    ),
    examples=(
        (
            "KHK-100231",
            "WEB",
            "CUST-20417",
            "2026-10-28T14:05:00-04:00",
            "PAID",
            "PAID",
            "",
            "2026-10-28T14:06:12-04:00",
            "",
            "",
            "",
            "",
            "USD",
            "32.00",
            "0.00",
            "6.95",
            "2.56",
            "41.51",
            "",
            "",
        ),
        (
            "KHK-100198",
            "MARKETPLACE",
            "CUST-19880",
            "2026-10-24T09:12:00-04:00",
            "SHIPPED",
            "PAID",
            "SHIPPED",
            "2026-10-24T09:13:40-04:00",
            "2026-10-26T17:00:00-04:00",
            "2026-10-25T15:30:00-04:00",
            "",
            "",
            "USD",
            "80.10",
            "0.00",
            "0.00",
            "6.41",
            "86.51",
            "UPS",
            "1Z999AA10123456784",
        ),
    ),
)

ORDER_ITEMS = ImportContract(
    import_type=ImportType.ORDER_ITEMS,
    key_description="order_number + line_number",
    columns=(
        _req("order_number"),
        _req("line_number"),
        _req("sku"),
        _req("quantity"),
        _req("unit_price"),
        _opt("line_discount"),
    ),
    examples=(
        ("KHK-100231", "1", "KHK-MUG-12OZ-SAGE", "2", "16.00", "0.00"),
        ("KHK-100198", "1", "KHK-KNF-CHEF-8", "1", "89.00", "8.90"),
    ),
)

INVENTORY_ADJUSTMENTS = ImportContract(
    import_type=ImportType.INVENTORY_ADJUSTMENTS,
    key_description="reference",
    columns=(
        _req("reference"),
        _req("sku"),
        _req("adjustment_type"),
        _req("quantity"),
        _req("occurred_at"),
        _opt("expected_at"),
        _opt("note"),
    ),
    examples=(
        (
            "CC-2026-10-20-MUG-SAGE",
            "KHK-MUG-12OZ-SAGE",
            "CYCLE_COUNT",
            "48",
            "2026-10-20T08:00:00-04:00",
            "",
            "Monthly cycle count, aisle B",
        ),
        (
            "PO-7781-ETA",
            "KHK-KNF-CHEF-8",
            "INCOMING_EXPECTED",
            "24",
            "2026-10-22T10:00:00-04:00",
            "2026-11-05T12:00:00-05:00",
            "PO 7781 from Northfield Blades",
        ),
    ),
)

CONTRACTS: dict[ImportType, ImportContract] = {
    contract.import_type: contract
    for contract in (PRODUCTS, ORDERS, ORDER_ITEMS, INVENTORY_ADJUSTMENTS)
}


def contract_for(import_type: ImportType) -> ImportContract:
    return CONTRACTS[import_type]


def render_template(import_type: ImportType) -> str:
    """Header plus example rows, as a CSV document with ``\\n`` line endings."""
    contract = contract_for(import_type)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(contract.column_names)
    writer.writerows(contract.examples)
    return buffer.getvalue()
