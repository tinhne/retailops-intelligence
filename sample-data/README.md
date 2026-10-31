# Sample import data

Fictional CSV files for **Kestrel Home & Kitchen**, the demo store (currency USD, time zone
America/New_York). They exercise the four import types described in
`docs/domain/BUSINESS_RULES.md` §6 (BR-601 to BR-609). Every name, SKU, order number, customer
reference and tracking number is invented. Customer references are opaque ids (BR-505).

The files are UTF-8 without a BOM and use `\n` line endings. Timestamps carry an explicit UTC
offset, so none of them triggers the `TIMEZONE_ASSUMED` warning.

## templates/

The header plus two example rows for each import type. These files are identical to the
download from `GET /api/v1/stores/{store_id}/imports/templates/{import_type}`. A unit test
(`tests/unit/test_import_parsing.py`) keeps them in sync with `app/domains/imports/templates.py`.

| File | Key | Required columns |
|---|---|---|
| `products.csv` | `sku` | sku, name, status, unit_price, reorder_point |
| `orders.csv` | `order_number` | order_number, placed_at, status, payment_status, currency, subtotal, total |
| `order_items.csv` | `order_number` + `line_number` | order_number, line_number, sku, quantity, unit_price |
| `inventory_adjustments.csv` | `reference` | reference, sku, adjustment_type, quantity, occurred_at |

## examples/valid/

A small, coherent data set. Import the files in this order. Each one validates with no errors
and applies as `COMPLETED`.

| Order | File | Content |
|---|---|---|
| 1 | `products.csv` | 10 products from 6 suppliers (with lead times). Nine are `ACTIVE`; the enamel kettle is `DRAFT` |
| 2 | `inventory_adjustments.csv` | Cycle counts for nine SKUs on 2026-10-20, an expected purchase order and its receipt, an incoming PO for knives, a damage write-off, a return restock and a signed correction |
| 3 | `orders.csv` | 8 orders placed 2026-10-24 to 2026-10-30, covering `DELIVERED`, `SHIPPED`, `PROCESSING`, `READY_TO_SHIP`, `PAYMENT_PENDING`, `CANCELLED` (paid, so a refund is pending) and two `PAID` orders. Two rows leave `fulfillment_status` empty so it is derived (STATE_MACHINES §1.3) |
| 4 | `order_items.csv` | 11 lines for those orders. Totals reconcile with BR-205 |

After step 4 the reservation sync (BR-120..123) has reserved stock for the `PAID`,
`PROCESSING` and `READY_TO_SHIP` orders. The two shipped orders were shipped after the
2026-10-20 count, so each of their lines wrote one `SHIPMENT` movement (BR-130). Examples:

| SKU | On hand | Reserved | Available |
|---|---|---|---|
| KHK-MUG-12OZ-SAGE | 48 − 2 shipped = 46 | 2 | 44 |
| KHK-MUG-12OZ-CHAR | 30 − 2 corrected = 28 | 3 | 25 |
| KHK-PAN-CI-10 | 2 + 12 received = 14 | 1 | 13 |
| KHK-TWL-LIN-2PK | 40 + 1 restocked − 1 shipped = 40 | 2 | 38 |

## examples/invalid/

Each file demonstrates failure cases. File-level failures reject the whole file (status
`REJECTED`). Row-level errors leave the import `VALIDATED`; it can then only be applied in
`VALID_ROWS_ONLY` mode with the skipped-row count confirmed. The row-level files that reference
existing data assume the valid set above was imported first.

| File | Import type | Expected result |
|---|---|---|
| `empty.csv` | any | Rejected: `FILE_EMPTY` (0 bytes) |
| `orders_header_only.csv` | orders | Rejected: `FILE_EMPTY` (header but no data rows) |
| `products_wrong_extension.txt` | products | Rejected: `FILE_TYPE` (only `.csv` is accepted) |
| `products_cp1252.csv` | products | Rejected: `FILE_ENCODING` (saved as Windows-1252; the `é` in "Café" is byte 0xE9) |
| `products_missing_columns.csv` | products | Rejected: `MISSING_COLUMNS` (`unit_price` is missing) |
| `products_row_errors.csv` | products | Rows 3–7 are errors: `DUPLICATE_KEY_IN_FILE` (row 3), `NEGATIVE_VALUE` price (4), `INVALID_ENUM` status (5), `INVALID_NUMBER` with three decimals (6), `NEGATIVE_VALUE` reorder point (7). Warnings: `PRICE_ZERO` (8), `NEGATIVE_MARGIN` (9) |
| `orders_row_errors.csv` | orders | One error per row: `CURRENCY_MISMATCH` (2), `ORDER_INVALID_STATUS_COMBINATION` (3), `ORDER_MISSING_TIMESTAMP` (4), `INVALID_DATETIME` (5), `ORDER_TIMESTAMP_SEQUENCE` (6), `INVALID_ENUM` channel (7), `REQUIRED` fulfillment_status for `REFUNDED` (8) |
| `orders_unreachable_transition.csv` | orders | `ORDER_TRANSITION_NOT_ALLOWED`: KHK-100190 is `DELIVERED` and cannot move back to `PAID` (STATE_MACHINES §1.2) |
| `order_items_row_errors.csv` | order_items | `UNKNOWN_ORDER` (2), `UNKNOWN_SKU` (3), `INVALID_INTEGER` quantity 0 (4), `NEGATIVE_VALUE` (5), `LINE_DISCOUNT_EXCEEDS_LINE` (6), `ORDER_LINE_LOCKED` (7, the order was delivered), row 8 unchanged, `DUPLICATE_KEY_IN_FILE` (9) |
| `inventory_adjustments_row_errors.csv` | inventory_adjustments | `ALREADY_APPLIED` warning (2, a no-op), `NEGATIVE_VALUE` (3), `INVALID_INTEGER` zero correction (4), `STALE_CYCLE_COUNT` (5), `UNKNOWN_SKU` (6), `INVALID_ENUM` for `SHIPMENT` (7), `RESERVED_REFERENCE` (8), `INVALID_DATETIME` (9) |

Row numbers are spreadsheet line numbers: the header is row 1 and the first data row is row 2.
An integration test (`tests/integration/test_imports_sample_data.py`) imports these files and
checks the results listed here.
