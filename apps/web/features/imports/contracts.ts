import type { ImportType } from "@/lib/status-maps";

// The column contracts from IMPORT_PIPELINE §5, shown as the "Column reference" on S-12 step 1.
// The API's templates carry exactly these headers in this order.

type Column = { name: string; required: "Yes" | "No" | "Conditional"; rule: string };

export const IMPORT_TYPE_INFO: Record<ImportType, { description: string; hint: string | null; next: ImportType | null }> = {
  products: {
    description: "Create or update products by SKU. Creates suppliers.",
    hint: null,
    next: "inventory_adjustments",
  },
  inventory_adjustments: {
    description: "Counts, receipts, damage and corrections. Each reference applies once.",
    hint: "Opening counts come before orders, so that orders shipped before the count are not deducted twice (BR-130).",
    next: "orders",
  },
  orders: {
    description: "Create or update orders by order number. Status changes must be reachable.",
    hint: "Products should be imported first, so that order items can reference them.",
    next: "order_items",
  },
  order_items: {
    description: "Lines for orders that already exist, by order number and line number.",
    hint: "Order items must reference orders and SKUs that already exist. Import those first.",
    next: null,
  },
};

export const IMPORT_COLUMNS: Record<ImportType, Column[]> = {
  products: [
    { name: "sku", required: "Yes", rule: "Text up to 64, unique in the file, case-sensitive" },
    { name: "name", required: "Yes", rule: "Text up to 200" },
    { name: "category", required: "No", rule: "Text up to 100" },
    { name: "status", required: "Yes", rule: "ACTIVE, DRAFT or ARCHIVED" },
    { name: "unit_price", required: "Yes", rule: "Decimal ≥ 0, at most 2 decimals" },
    { name: "unit_cost", required: "No", rule: "Decimal ≥ 0" },
    { name: "reorder_point", required: "Yes", rule: "Whole number ≥ 0 (0 turns reorder alerts off)" },
    { name: "reorder_quantity", required: "No", rule: "Whole number ≥ 0" },
    { name: "supplier_name", required: "No", rule: "Text up to 200; a new name creates the supplier" },
    { name: "supplier_lead_time_days", required: "No", rule: "Whole number 0–365; needs supplier_name" },
  ],
  inventory_adjustments: [
    { name: "reference", required: "Yes", rule: "Text up to 100, unique per store; applies once" },
    { name: "sku", required: "Yes", rule: "An existing SKU" },
    { name: "adjustment_type", required: "Yes", rule: "CYCLE_COUNT, RECEIPT, INCOMING_EXPECTED, INCOMING_CANCELLED, DAMAGE, SHRINKAGE, RETURN_RESTOCK or CORRECTION" },
    { name: "quantity", required: "Yes", rule: "Whole number. Counts are absolute, corrections signed, others positive" },
    { name: "occurred_at", required: "Yes", rule: "ISO-8601 timestamp" },
    { name: "expected_at", required: "No", rule: "ISO-8601, for INCOMING_EXPECTED" },
    { name: "note", required: "No", rule: "Text up to 500" },
  ],
  orders: [
    { name: "order_number", required: "Yes", rule: "Text up to 64, unique in the file" },
    { name: "channel", required: "No", rule: "WEB, MARKETPLACE, POS or OTHER (default WEB)" },
    { name: "customer_ref", required: "No", rule: "Opaque reference up to 64; no personal data" },
    { name: "placed_at", required: "Yes", rule: "ISO-8601 timestamp" },
    { name: "status", required: "Yes", rule: "An order status, reachable from the stored one" },
    { name: "payment_status", required: "Yes", rule: "PENDING, PAID, FAILED or REFUNDED" },
    { name: "fulfillment_status", required: "No", rule: "UNFULFILLED, IN_PROGRESS, SHIPPED, DELIVERED or RETURNED" },
    { name: "paid_at", required: "Conditional", rule: "ISO-8601; when payment is PAID or REFUNDED" },
    { name: "ship_by", required: "No", rule: "ISO-8601; defaults to paid_at plus the store SLA" },
    { name: "shipped_at", required: "Conditional", rule: "ISO-8601; when shipped, delivered or returned" },
    { name: "delivered_at", required: "Conditional", rule: "ISO-8601; when delivered or a return is requested" },
    { name: "cancelled_at", required: "Conditional", rule: "ISO-8601; when CANCELLED" },
    { name: "currency", required: "Yes", rule: "The store currency" },
    { name: "subtotal", required: "Yes", rule: "Decimal ≥ 0" },
    { name: "discount_total", required: "No", rule: "Decimal ≥ 0 (order-level discount)" },
    { name: "shipping_total", required: "No", rule: "Decimal ≥ 0" },
    { name: "tax_total", required: "No", rule: "Decimal ≥ 0" },
    { name: "total", required: "Yes", rule: "Decimal ≥ 0" },
    { name: "carrier", required: "No", rule: "Text" },
    { name: "tracking_number", required: "No", rule: "Text" },
  ],
  order_items: [
    { name: "order_number", required: "Yes", rule: "An existing order" },
    { name: "line_number", required: "Yes", rule: "Whole number ≥ 1, unique per order in the file" },
    { name: "sku", required: "Yes", rule: "An existing SKU" },
    { name: "quantity", required: "Yes", rule: "Whole number ≥ 1" },
    { name: "unit_price", required: "Yes", rule: "Decimal ≥ 0, the price charged" },
    { name: "line_discount", required: "No", rule: "Decimal ≥ 0, at most quantity × unit_price" },
  ],
};
