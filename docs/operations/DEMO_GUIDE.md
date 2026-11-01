# Demo guide

A ten-minute tour of RetailOps Intelligence on the fictional store "Kestrel Home & Kitchen". Every
record in it is generated; nothing describes a real business or person.

## Start

- **Containers:** `docker compose up --build`, then open <http://localhost:3000>.
- **Development:** `make seed`, `make api-dev`, `pnpm web:dev`, then open <http://localhost:3000>.

Choose **Explore the demo** to sign in as the read-only viewer. To try the actions that change data,
seed with `DEMO_STAFF_PASSWORD=<a password you choose> make seed` and sign in as
`manager@kestrel.example` (or `owner@`, `staff@`, `sofia@`, `analyst@kestrel.example`) with it.
`make seed` (or `make stack-demo-reset` for the containers) restores the story at any time.

## Tour as the demo viewer

1. **Overview.** Read the KPIs and the attention list. Note "Value at risk by category" is never
   totalled, and stock health shows a separate *Data issue* row for a product with negative stock.
2. **Open the top exception** from the attention list (a refund owed on a cancelled order, or an
   overdue order). Read *Why this priority* (the score breakdown), *How this was detected* (the
   formula and inputs), the evidence and the affected orders.
3. **Generate the AI investigation** in the side panel. Check that every fact links to a record and
   that the footer says which engine produced it and which read-only tools it used.
4. **Ask a follow-up** from that panel, for example "Why is this exception urgent?".
5. **Copilot.** Start a new conversation from a suggested question such as "Which orders are
   overdue, and why?". References open the orders and exceptions they cite.
6. **Exceptions inbox.** Switch views (Triage, All active, Closed), filter by category or type, and
   open the lifecycle explainer ("How resolution works").
7. **Orders.** Search `KHK-12030` (cancelled but still paid) and read the three status axes and the
   refund callout. Use **Ask the copilot** on the order.
8. **Inventory.** Toggle *Oversold* and *Data issue* in the health bar. Open `KHK-BW-003` to see the
   data-issue explanation and the stock arithmetic.
9. **Movements.** Filter the ledger by product, see shipments linked to their orders and adjustments
   linked to the import that wrote them.
10. **Imports and audit.** Open the two seeded imports, their issues and the analysis each one
    triggered; then the audit log with its actors and targets. Actions that change data are shown
    but disabled with the reason "The public demo is read-only."

## Tour as the manager (local only)

1. On an open exception: **Acknowledge**, **Start work** (it assigns to you), then **Draft with
   copilot**. Review and edit the draft, then **Save note**: the note shows "AI draft, accepted by …".
2. **Resolve…** with a resolution and a note of at least 10 characters. The exception waits for
   verification; the next import or scheduled evaluation confirms it or reopens it with the reason.
3. **Imports → Download template**, edit a few rows (add one invalid row), then **New import**.
   Watch the upload progress, review the preview and the issues, choose *Valid rows only*, confirm
   the skipped count and apply. **View new exceptions** lists what that import's analysis found.
4. **Run analysis** on the Overview to evaluate on demand.
5. As the owner: **Users & roles** (role matrix, add a member, change a role), **Settings**
   (thresholds and priority weights with a confirmation of each change) and the **Audit log**.
