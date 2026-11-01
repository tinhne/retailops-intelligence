/**
 * CSV files for the end-to-end journey, generated per run (unique SKUs and order numbers) so the
 * suite can run repeatedly against the same stack. Columns follow sample-data/templates.
 *
 * Designed outcome after the four imports (BUSINESS_RULES.md §2):
 * - `${run}-LOW`:   counted 4, reorder point 10 → INVENTORY_BELOW_REORDER_POINT
 * - `${run}-SHORT`: counted 1, a paid order reserves 2 → available −1 → INVENTORY_OVERSOLD
 */
export interface JourneyFile {
  type: "products" | "inventory_adjustments" | "orders" | "order_items";
  label: string;
  filename: string;
  csv: string;
}

const iso = (date: Date) => date.toISOString().replace(/\.\d{3}Z$/, "Z");

export function journeyRunId(now = new Date()): string {
  return `E2E${now.getTime().toString(36).toUpperCase()}`;
}

export function journeyFiles(run: string, now = new Date()): { files: JourneyFile[]; low: string; short: string } {
  const hoursAgo = (h: number) => iso(new Date(now.getTime() - h * 3_600_000));
  const low = `${run}-LOW`;
  const short = `${run}-SHORT`;
  const order = `${run}-1`;
  const files: JourneyFile[] = [
    {
      type: "products",
      label: "1. Products",
      filename: `${run}-products.csv`,
      csv: [
        "sku,name,category,status,unit_price,unit_cost,reorder_point,reorder_quantity,supplier_name,supplier_lead_time_days",
        `${low},E2E Linen Napkin Set,Linens,ACTIVE,24.00,11.00,10,30,E2E Textile Supplier,7`,
        `${short},E2E Stoneware Mug,Tableware,ACTIVE,24.00,9.50,5,20,E2E Textile Supplier,7`,
      ].join("\n"),
    },
    {
      type: "inventory_adjustments",
      label: "2. Inventory adjustments",
      filename: `${run}-adjustments.csv`,
      csv: [
        "reference,sku,adjustment_type,quantity,occurred_at,expected_at,note",
        `${run}-COUNT-LOW,${low},CYCLE_COUNT,4,${hoursAgo(3)},,E2E cycle count`,
        `${run}-COUNT-SHORT,${short},CYCLE_COUNT,1,${hoursAgo(3)},,E2E cycle count`,
      ].join("\n"),
    },
    {
      type: "orders",
      label: "3. Orders",
      filename: `${run}-orders.csv`,
      csv: [
        "order_number,channel,customer_ref,placed_at,status,payment_status,fulfillment_status,paid_at,ship_by,shipped_at,delivered_at,cancelled_at,currency,subtotal,discount_total,shipping_total,tax_total,total,carrier,tracking_number",
        `${order},WEB,CUST-E2E,${hoursAgo(2)},PAID,PAID,UNFULFILLED,${hoursAgo(2)},,,,,USD,48.00,0,0,0,48.00,,`,
      ].join("\n"),
    },
    {
      type: "order_items",
      label: "4. Order items",
      filename: `${run}-order-items.csv`,
      csv: ["order_number,line_number,sku,quantity,unit_price,line_discount", `${order},1,${short},2,24.00,0`].join("\n"),
    },
  ];
  return { files, low, short };
}
