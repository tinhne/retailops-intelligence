# Component Inventory

> **Status:** v1 design specification (task T-030, milestone M3).
> Tokens and rules: `DESIGN_SYSTEM.md`. Screens: `SCREEN_SPECIFICATIONS.md` (`S-xx`).
> Location: shadcn/ui primitives in `apps/web/components/ui/`, product components in
> `apps/web/components/<group>/`, feature-specific composites in `apps/web/features/<area>/`.

Every product component has a vitest + Testing Library test covering its states and its
accessible name/role. Components never call `fetch` directly. Data comes from feature hooks
(TanStack Query), so components stay testable with plain props.

---

## 1. Build order

Build top to bottom. Each phase unblocks the frontend tasks listed.

| Phase | Contents | Unblocks |
|---|---|---|
| **0. Foundations** | `tokens.css`, `globals.css` theme mapping, Inter via `next/font`, formatters (`lib/format`), `status-maps.ts`, API client + `ApiError`, QueryClient defaults, `StoreProvider` / `useStore`, `usePermission`, `useListParams` | everything |
| **1. Primitives** (shadcn/ui, restyled) | Button, Input, Textarea, Label, Form, Select, Checkbox, RadioGroup, Switch, ToggleGroup, Dialog, AlertDialog, Sheet, Popover, DropdownMenu, Tooltip, Tabs, Table, Card, Alert, Skeleton, Separator, ScrollArea, Command, Calendar, Avatar, Breadcrumb, Collapsible, Sonner | T-060 |
| **2. Formatting and status atoms** | C-01 Money · C-02 Quantity/Delta · C-03 Percent · C-04 DateTime · C-05 RelativeTime/DueLabel · C-06 ExceptionRef · C-07 CopyButton · C-08 EstimateLabel · C-09 StatusPill · C-10 SeverityBadge · C-11 ExceptionStatusPill · C-12 PriorityIndicator · C-13 HealthBadge · C-14 OrderStatusPill · C-15 ImportStatusPill · C-16 CountBadge | T-061..T-065 |
| **3. Shell and guards** | C-20 AppShell · C-21 DemoBanner · C-22 TopBar · C-23 SidebarNav + MobileNavDrawer · C-24 StoreSwitcher · C-25 UserMenu · C-26 GlobalSearch · C-27 PermissionGate · C-28 ActionButton · C-29 PageHeader | T-060 |
| **4. Data display and states** | C-30 DataTable · C-31 FilterBar · C-32 SearchInput · C-33 Pagination · C-34 EmptyState · C-35 ErrorState · C-36 PermissionDenied · C-37 NotFoundState · C-38 Skeletons · C-39 KpiCard · C-40 StatTile · C-41 DescriptionList · C-42 ConfirmDialog · C-43 ChartFrame · C-44 TimeSeriesChart · C-45 BarBreakdown | T-061, T-063, T-064 |
| **5. Exceptions** | C-50 PriorityBreakdown · C-51 CalculationBlock · C-52 EvidenceTable · C-53 AffectedOrdersTable · C-54 Timeline · C-55 NoteComposer · C-56 ExceptionActionBar (+ `getExceptionActions`) · C-57 Resolve/Dismiss/Reopen dialogs · C-58 AssigneeControl · C-59 DueDateControl · C-60 ExceptionLifecycleBanner · C-61 RunAnalysisButton · C-62 ExceptionListItem · C-63 LifecycleExplainer | T-062 |
| **6. Imports** | C-70 ImportTypePicker · C-71 ImportDropzone · C-72 ImportStepper · C-73 ImportStatusPanel · C-74 ImportSummaryTiles · C-75 IssueTable · C-76 ApplyPanel | T-065 |
| **7. Copilot** | C-80 CopilotAnswer · C-81 ReferenceChip · C-82 ToolCallDisclosure · C-83 CopilotComposer · C-84 ConversationList · C-85 SuggestedQuestions · C-86 AIInvestigationPanel | T-073 |
| **8. Admin and P1** | C-90 SettingsField + SettingsSaveBar · C-91 RoleMatrix · C-92 ChangeRoleDialog (P1) · C-93 DemoTourPanel (P1) | T-066, T-094 |

---

## 2. Shared types

These aliases are **re-exports** from `@retailops/contracts` (generated from OpenAPI, ADR-0013).
They are shown here for readability and must not be redeclared by hand (AGENTS.md §4).

```ts
import type { components } from "@retailops/contracts";
type S = components["schemas"];

export type Severity = S["Severity"];              // "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
export type ExceptionStatus = S["ExceptionStatus"];// "OPEN" | "ACKNOWLEDGED" | "IN_PROGRESS" | "REOPENED" | "RESOLVED" | "DISMISSED"
export type PriorityBand = S["PriorityBand"];      // "P1" | "P2" | "P3" | "P4"
export type StockHealth = S["StockHealth"];        // "OVERSOLD" | "OUT_OF_STOCK" | "BELOW_REORDER_POINT" | "APPROACHING_REORDER_POINT" | "HEALTHY"
export type EvaluationStatus = S["EvaluationStatus"]; // "RUNNING" | "SUCCEEDED" | "FAILED" | "SKIPPED"
export type OrderStatus = S["OrderStatus"];        // 12 values, STATE_MACHINES §1.1
export type ImportStatus = S["ImportStatus"];      // UPLOADED … DISCARDED
export type Permission = S["Permission"];          // "dashboard.read" | … | "users.manage"
export type DecimalString = string;                // NUMERIC as string (BR-503). Never parseFloat for arithmetic.
export type IsoDateTime = string;                  // UTC ISO-8601 from the API

// UI-only types (these are not API types, so they live in apps/web)
export type Tone = "neutral" | "outline" | "muted" | "primary" | "info" | "success"
  | "warning" | "caution" | "attention" | "danger" | "danger-solid";
export type Gate = { allowed: true } | { allowed: false; reason: string };
// What HealthBadge shows: API health (DATA_ISSUE included, BR-402a), or "Not tracked" when it is null
export type DisplayHealth = StockHealth | "NOT_TRACKED" /* health null */;
export type ApiError = { status: number; code: string; message: string;
  details?: Array<{ field?: string; message: string }>; requestId?: string; retryAfterSeconds?: number };
export type LoadStatus = "loading" | "error" | "success";
```

---

## 3. Foundations (phase 0)

| Item | Signature | Notes |
|---|---|---|
| `useStore()` | `() => { id; name; code; currency; timezone; organization: { id; name; slug; isDemo }; role; permissions: Set<Permission> }` | From the `storeId` segment plus `/me`. Throws outside `StoreProvider`. |
| `usePermission()` | `(p: Permission \| Permission[], extra?: () => Gate) => Gate` | `isDemo` and missing → "The public demo is read-only." Missing (non-demo) → "You need the {label} permission. Ask an owner or manager." `extra` adds contextual rules (assignee checks). |
| `useListParams()` | `<T extends z.ZodTypeAny>(schema: T) => [z.infer<T>, (patch: Partial<z.infer<T>>) => void]` | Parses and validates URL search params, drops invalid values (SCREEN_SPECS §0.3 validation), resets `page` on filter or sort change, and writes with `router.replace` (no history spam for typing) or `push` (for page changes). |
| `useApiMutation()` | wraps `useMutation` | Adds the `X-CSRF-Token` header (from the `ro_csrf` cookie), `expected_version` (the exception `version` on screen), `Idempotency-Key` where configured, maps the error envelope to `ApiError`, and maps 401 to the session-expired redirect. On `409 STALE_VERSION` it shows the "Someone else updated {reference}…" warning toast and invalidates the exception, events and notes queries (SCREEN_SPECS §0.3). |
| `lib/format/*` | `formatMoney`, `formatMoneyCompact`, `formatQuantity`, `formatDelta`, `formatPercent`, `formatPp`, `formatDateTime`, `formatDateTimeShort`, `formatDate`, `formatRelative`, `formatDue`, `formatDuration`, `formatDaysOfCover`, `formatBytes` | Pure functions, rules in DESIGN_SYSTEM §13. Tests include an EDT→EST transition (Nov 1, 2026) and negative values. |
| `lib/status-maps.ts` | `Record<Enum, { label: string; tone: Tone; icon: LucideIcon; description?: string }>` per enum | The single source of UI labels, tones and icons (DESIGN_SYSTEM §3.5). Includes `exceptionTypeLabels`, `resolutionCodeLabels`, `dismissedReasonLabels`, `movementTypeLabels`, `importTypeLabels`, `importIssueMeta` (level, meaning and "How to fix" text mirrored from IMPORT_PIPELINE §6), `evaluationStatusLabels`, `auditActionLabels`, `toolNameLabels`, `permissionLabels` (label + description for the role matrix). |
| QueryClient defaults | `retry: (n, e) => n < 2 && (isNetwork(e) \|\| e.status >= 500)`, `refetchOnWindowFocus: true`, `staleTime: 30_000` | Query keys start with `['store', storeId, …]`. |

---

## 4. Primitives (phase 1): restyling notes

Install with the shadcn CLI, then apply tokens. Only deviations from shadcn defaults are listed.

| Primitive | Customisation |
|---|---|
| Button | Variants `primary` (default), `secondary` (outline), `ghost`, `destructive`, `link`. Sizes `sm` 28 px, `md` 32 px (default), `lg` 40 px (mobile sticky bar). Adds `pending` and `pendingLabel` props (spinner + label, `aria-busy`). The radius is `--radius-md`. |
| Input / Textarea / Select | Border `--input` (3:1). Height 32 px (`md`), 40 px below 640 px with 16 px text. Error state via `aria-invalid` styling. |
| Checkbox / RadioGroup / Switch | 16 px controls with `--input` borders. Checked state uses `--primary`. The label is always clickable. |
| Dialog / AlertDialog | Max-width 560 px (forms) or 440 px (confirm). `--shadow-dialog`. Below 640 px they render as a bottom sheet. Initial focus: first field (forms) or **Cancel** (AlertDialog). |
| Sheet | Left (navigation) and bottom (mobile filters, actions). Focus trap. Closes on route change. |
| Tooltip | 150 ms open delay, `--popover` surface, `text-xs`. Content must also be reachable by focus. Never the only place for essential information, except disabled reasons, which are also in `aria-describedby`. |
| Table | Header `--surface-subtle`, density classes, sticky header option. Used inside C-30. |
| Alert | Tones `info`, `success`, `warning`, `danger`, `neutral`. 20 px icon. Optional action slot. `role="alert"` only for danger alerts that appear in response to user action. Otherwise `role="status"`. |
| Skeleton | `--muted` fill, 2 s pulse, static under reduced motion. |
| Sonner | Bottom-right (≥ 640) / bottom-centre. Max 3 visible. 5 s duration. Close button. Icons follow the tones. |
| Command | Used by C-26 and comboboxes. Group headings in `text-xs` muted. |
| Calendar | Week starts Sunday (en-US). Dates are store-local. Used by date-range filters and C-59. |

---

## 5. Formatting and status atoms (phase 2)

### C-01 Money
**Purpose.** Render a monetary amount in the store currency, correctly and consistently.
```ts
type MoneyProps = {
  value: DecimalString | null;
  currency?: string;                              // default: useStore().currency
  compact?: boolean;                              // axis ticks only
  negativeTone?: "none" | "danger";               // default "none"
  suffix?: "at risk" | "owed" | string;          // e.g. "$600.00 at risk"
};
```
**Variants.** Default, compact, with suffix. **States.** `null` → "—" with `aria-label="None"`.
**A11y.** Negative values use U+2212 visually and expose `aria-label` with an ASCII minus
("-$12.40"), because some screen readers skip U+2212. **Used by.** S-02, S-03, S-04, S-05, S-06,
S-07, S-08, S-16.

### C-02 Quantity / Delta
```ts
type QuantityProps = { value: number | null; negativeTone?: "none" | "danger"; unit?: "units" };
type DeltaProps = { value: number };              // always signed: +40, −3, 0
```
**Used by.** S-04 (evidence), S-06, S-08, S-09, S-10.

### C-03 Percent
```ts
type PercentProps = { ratio: number | null; digits?: 0 | 1 };   // ratio 0..1
type PpDeltaProps = { value: number; goodWhen: "up" | "down"; comparison: string };
```
`PpDelta` renders an arrow icon plus text ("↓ 2.1 pp vs previous 7 days"), in success or danger
tone according to `goodWhen`. The text always states the direction. **Used by.** S-02 (KPI), S-20.

### C-04 DateTime
**Purpose.** Show a timestamp in the store time zone with its zone abbreviation (BR-501).
```ts
type DateTimeProps = {
  value: IsoDateTime | null;
  format?: "full" | "short" | "date";             // full = "Oct 31, 9:42 AM EDT"
  tooltip?: boolean;                               // default true for "short"
};
```
Renders `<time dateTime={value}>`. The `short` format omits the zone, and the column header
supplies "(ET)" via `zoneLabel(store.timezone)`. **Used by.** all list and detail screens.

### C-05 RelativeTime / DueLabel
```ts
type RelativeTimeProps = { value: IsoDateTime; now?: Date };        // "5h ago"
type DueLabelProps = { dueAt: IsoDateTime | null; now?: Date; size?: "sm" | "md" };
```
`DueLabel`: "Due in 3h 55m", or `alarm-clock` + "Overdue 2h" in `--overdue-fg`. Both re-render
every 60 s via a shared ticker (one interval for the app, not one per instance). The tooltip shows
the full DateTime. **A11y.** `<time>` with the full timestamp in `title`. The overdue state is
in the text, not only the colour. **Used by.** S-02, S-03, S-04, S-14, S-15.

### C-06 ExceptionRef
```ts
type ExceptionRefProps = { reference: string; copy?: boolean; href?: string };   // operational_exception.reference, "EXC-1042"
```
Renders the reference verbatim in Inter 500 with tabular numerals (it is a human reference, like an
order number). Never derived from the UUID. **Used by.** S-02, S-03, S-04, S-06, S-08, S-14, S-15, C-26.

### C-07 CopyButton
```ts
type CopyButtonProps = { value: string; label: string };  // label: "Copy request ID"
```
16 px ghost icon button. After copy, the icon swaps to `check` for 1.5 s and a polite live region
says "Copied". **Used by.** ErrorState, S-04, S-06, S-13, S-15.

### C-08 EstimateLabel
```ts
type EstimateLabelProps = { basis?: string };   // default basis from velocity_window_days
```
"est." in `text-xs` muted, with a tooltip: "Estimate based on the last 28 days of sales. It
ignores seasonality and promotions (BR-152)." **Used by.** S-04, S-08, S-09, S-14 (estimates).

### C-09 StatusPill (generic)
**Purpose.** The single pill implementation. Domain pills (C-10..C-15) are thin wrappers that
look up `status-maps.ts`.
```ts
type StatusPillProps = {
  tone: Tone;
  label: string;
  icon?: LucideIcon;
  size?: "sm" | "md";            // 20 / 24 px
  srPrefix?: string;             // visually hidden prefix, e.g. "Severity:"
  iconOnly?: boolean;            // dense tables < 1024: label moves to tooltip + accessible name
};
```
**Variants.** 11 tones × 2 sizes. **States.** Static (never interactive). **A11y.** The icon is
`aria-hidden`. Accessible name = `srPrefix + label`. Contrast pairs are verified in DESIGN_SYSTEM
§20. In `forced-colors` mode the 1 px border stays visible. **Used by.** everywhere.

### C-10 SeverityBadge
```ts
type SeverityBadgeProps = { severity: Severity; size?: "sm" | "md"; iconOnly?: boolean };
```
CRITICAL is the only solid pill. **Used by.** S-02, S-03, S-04, S-06, S-08, S-22.

### C-11 ExceptionStatusPill
```ts
type ExceptionStatusPillProps = {
  status: ExceptionStatus;
  resolutionCode?: string | null;     // decides the RESOLVED form
  verifiedAt?: IsoDateTime | null;    // manual resolution: null → "Resolved — awaiting verification", set → "Verified"
  dismissedReason?: string | null;    // tooltip on "Dismissed"
  size?: "sm" | "md";
};
```
`RESOLVED` renders one of four forms (DESIGN_SYSTEM §3.5): manual with `verifiedAt` null →
"Resolved — awaiting verification" (info, `hourglass`). Manual with `verifiedAt` set → "Verified"
(success). `CONDITION_CLEARED` → "Resolved · condition cleared" (success). `SUPERSEDED` →
"Superseded" (muted). A manual resolution is never shown with a success tone before `verified_at`
exists. **Used by.** S-02, S-03, S-04, S-06, S-08.

### C-12 PriorityIndicator
**Purpose.** Show priority band and score as a meter plus text, a shape distinct from severity
pills.
```ts
type PriorityIndicatorProps = { band: PriorityBand; score: number; size?: "sm" | "md"; href?: string };
```
Four 3 × 10 px bars (filled count: P1 = 4 … P4 = 1, colour `--priority-pN-bar`, empty
`--priority-bar-empty`), then "P1 · 81" in `--priority-pN-fg`, 500 weight, tabular. With `href`
(S-04 header) it links to `#priority`. **A11y.** `aria-label="Priority P1, score 81 of 100"`.
Bars are `aria-hidden`. **Used by.** S-02, S-03, S-04, S-06, S-08.

### C-13 HealthBadge
```ts
type HealthBadgeProps = { health: StockHealth | null; onHand?: number; size?: "sm" | "md"; iconOnly?: boolean };
// resolves to a DisplayHealth: the API value; health null → "NOT_TRACKED"
```
`DATA_ISSUE` (the API's class for `on_hand < 0`, any product status, BR-402a) → "Data issue"
(attention tone, `database` icon) with the tooltip "On hand is negative ({onHand}). That is
physically impossible, so stock health can't be computed until a cycle count corrects it
(BR-402a)." `onHand` only adds the figure to that tooltip; the badge never derives health from it.
`null` (non-ACTIVE product with valid stock) → "Not tracked" (muted) with a tooltip "Stock health
is computed for active products only." OVERSOLD is solid danger. **Used by.** S-06, S-07, S-08, S-09, and
C-26 search results.

### C-14 OrderStatusPill (+ PaymentStatusText, FulfillmentStatusText)
```ts
type OrderStatusPillProps = { status: OrderStatus; size?: "sm" | "md" };
type AxisTextProps = { value: S["PaymentStatus"] | S["FulfillmentStatus"]; axis: "payment" | "fulfillment" };
```
Group tones per DESIGN_SYSTEM §3.5. Axis texts render as icon + coloured text (no pill) in tables,
and as `sm` pills on S-06. **Used by.** S-04, S-05, S-06, S-08.

### C-15 ImportStatusPill
```ts
type ImportStatusPillProps = { status: ImportStatus; size?: "sm" | "md" };
```
Labels: "Validating", "Ready to apply", "Applying", "Completed", "Completed, rows skipped",
"Failed", "Rejected", "Discarded". **Used by.** S-02, S-11, S-12, S-13, S-22.

### C-16 CountBadge
```ts
type CountBadgeProps = { count: number; label: string; tone?: "neutral" | "danger"; dotOnly?: boolean };
```
`label` is the accessible name ("5 active P1 exceptions"). `dotOnly` is for the collapsed sidebar.
**Used by.** C-23, S-03 tabs, S-05, S-07.

---

## 6. Shell and guards (phase 3)

### C-20 AppShell
**Purpose.** The authenticated frame: demo banner, top bar, sidebar or drawer, main region.
```ts
type AppShellProps = { children: React.ReactNode };   // reads useStore(); nav items from IA §4.3
```
**States.** Sidebar expanded or collapsed (persisted), mobile drawer open or closed, offline
banner. **A11y.** Landmarks: `header` (top bar), `nav[aria-label="Main"]`,
`main#content`. A skip link comes first. Route changes move focus to the page `h1` and announce
the document title via a polite live region. **Used by.** all `/s/{storeId}` routes.

### C-21 DemoBanner
**Purpose.** Make seeded data unmistakable on every page of a demo organization (IA-7).
```ts
type DemoBannerProps = { onStartTour?: () => void };   // renders only when organization.isDemo
```
Copy: "**Demo data** Kestrel Home & Kitchen is a fictional store. All records are generated and
periodically reset. You are signed in as a read-only viewer." (the last sentence only for the
VIEWER role). Actions: **Take the tour** (when C-93 exists), **Leave demo** (sign out).
**Variants.** Full (≥ 640, 36 px) and compact (< 640, 32 px: "Demo data · read-only" + **Tour**).
**States.** Not dismissible. **A11y.** `role="region"` `aria-label="Demo notice"`, placed before
the top bar so it is read first. Inverse colours (16.75:1). **Used by.** S-00 (all pages).

### C-22 TopBar
```ts
type TopBarProps = { breadcrumbs?: Crumb[]; onOpenNav: () => void };
```
Left: breadcrumb (≥ 768) or menu button + store name. Right: search trigger, Copilot link
(`copilot.use`), UserMenu. **A11y.** The menu button has `aria-expanded` and `aria-controls`.
**Used by.** S-00.

### C-23 SidebarNav + MobileNavDrawer
```ts
type NavItem = { label: string; href: string; icon: LucideIcon; permission: Permission | Permission[];
                 badge?: { count: number; label: string } };
type NavGroup = { label?: string; items: NavItem[] };
type SidebarNavProps = { groups: NavGroup[]; collapsed: boolean; onCollapsedChange: (v: boolean) => void };
type MobileNavDrawerProps = { groups: NavGroup[]; open: boolean; onOpenChange: (v: boolean) => void };
```
Items whose permission is missing are filtered out, and empty groups disappear (IA §4.3). The
current item is matched by path prefix (`/exceptions/123` highlights Exceptions,
`/inventory/movements` highlights Movements, not Inventory). **Variants.** Expanded (240 px),
collapsed (56 px, tooltips), drawer (< 768). **A11y.** `aria-current="page"`. In collapsed mode
every link has an `aria-label`, and the badge count is in the label. The drawer closes on
navigation and returns focus to the menu button. **Used by.** S-00.

### C-24 StoreSwitcher
```ts
type StoreSwitcherProps = {
  stores: Array<{ id: string; name: string; code: string; currency: string; timezone: string; organizationName: string }>;
  currentStoreId: string;
};
```
With 1 store: a static label (name + "USD · Times in ET"), not a button. With 2 or more: a
Popover with a Command list grouped by organization and a search box when there are more than 5.
Selecting navigates to the same section (IA §7). **A11y.** Combobox pattern (`role="combobox"`,
`aria-expanded`). Options announce "Kestrel Home & Kitchen, Kestrel Commerce, current". **Used
by.** S-00.

### C-25 UserMenu
```ts
type UserMenuProps = { user: { fullName: string; email: string }; role: string; organizationName: string };
```
DropdownMenu: a header (name, email, "Manager · Kestrel Commerce"), then **Sign out** (`POST
/auth/logout` → `/login?reason=signed_out`). No profile or settings items (IA A13). **A11y.**
The trigger has `aria-label="Account menu for Morgan Lee"`. **Used by.** S-00.

### C-26 GlobalSearch
**Purpose.** Jump to an exception, order, product or page from anywhere (IA §8).
```ts
type GlobalSearchProps = { open: boolean; onOpenChange: (v: boolean) => void };
```
Command palette in a Dialog. Ctrl/⌘ K toggles it. Groups: Exceptions (`q` matches `reference`
and title, rows show "EXC-1042 · title"), Orders, Products, Go to.
Queries run only for permitted groups (min 2 characters, 200 ms debounce, 5 per group).
**States.** Idle (shows Go to), loading (a skeleton row per group, existing results kept), results,
no results ("No matches for "kh-99"". Search covers order numbers, SKUs, product names and
exception titles or references.), group error (an inline "Couldn't search orders. Try again." row,
other groups unaffected). **A11y.** cmdk listbox semantics. Result rows read as "Order KHK-10482,
Ready to ship, $120.00". Escape closes and returns focus to the trigger. **Used by.** S-00.

### C-27 PermissionGate
**Purpose.** One place that decides whether an action is shown, enabled or disabled-with-reason.
```ts
type PermissionGateProps = {
  permission: Permission | Permission[];          // all required
  mode: "hide" | "disable";
  extra?: () => Gate;                             // contextual rule, e.g. "only the assignee…"
  children: React.ReactElement | ((gate: Gate) => React.ReactNode);
};
```
In `disable` mode, the child receives `aria-disabled="true"`, a no-op handler, a Tooltip with
the reason, and `aria-describedby` pointing to a visually hidden reason element. Demo
organizations always get "The public demo is read-only." **A11y.** The control stays focusable.
**Used by.** every screen with actions.

### C-28 ActionButton
```ts
type ActionButtonProps = ButtonProps & {
  gate?: Gate;                 // from usePermission(); disabled-with-reason when not allowed
  pending?: boolean;
  pendingLabel?: string;       // "Resolving…"
};
```
Button + PermissionGate behaviour + pending state. **Used by.** S-02, S-03, S-04, S-11, S-12,
S-13, S-16, S-17.

### C-29 PageHeader
```ts
type PageHeaderProps = {
  title: string;                                   // the page h1
  subtitle?: React.ReactNode;
  breadcrumbs?: Array<{ label: string; href?: string }>;
  meta?: React.ReactNode;                          // freshness line, IDs
  status?: React.ReactNode;                        // pills row
  actions?: React.ReactNode;                       // right-aligned. Wraps below on < 768
};
```
**States.** `title` renders during loading (static text). Detail pages pass a skeleton until
the record arrives. **A11y.** Exactly one `h1`, which receives focus after navigation.
**Used by.** all screens.

---

## 7. Data display and states (phase 4)

### C-30 DataTable (server pagination)
**Purpose.** All lists. Server-side sort, filter and pagination with URL state, consistent
density, sticky header, stacked rows on small screens.
```ts
type ColumnDef<T> = {
  id: string;
  header: string;                         // sentence case. Zone in header for times: "Placed (ET)"
  cell: (row: T) => React.ReactNode;
  align?: "left" | "right";               // numbers right
  sortKey?: string;                       // API field. Enables the sort button
  hideBelow?: "md" | "lg" | "xl";
  width?: string;                         // CSS width / max-width
  isPrimary?: boolean;                    // holds the stretched row link
};
type DataTableProps<T> = {
  caption: string;                        // visually hidden. Updated with page and sort
  columns: ColumnDef<T>[];
  rows: T[] | undefined;
  getRowId: (row: T) => string;
  getRowHref?: (row: T) => string;
  getRowLabel?: (row: T) => string;       // accessible name of the row link
  status: LoadStatus; isFetching?: boolean; error?: ApiError; onRetry?: () => void;
  total?: number; page: number; pageSize: 25 | 50 | 100;
  onPageChange: (p: number) => void; onPageSizeChange: (s: 25 | 50 | 100) => void;
  sort?: string; onSortChange?: (sort: string) => void;      // "field" | "-field"
  density?: "comfortable" | "compact"; onDensityChange?: (d: "comfortable" | "compact") => void;
  isFiltered: boolean;                    // decides Empty vs No-results
  empty: React.ReactNode; noResults: React.ReactNode;
  renderStackedRow?: (row: T) => React.ReactNode;           // < 768 for primary lists
  stickyFirstColumn?: boolean;            // ledgers on small screens
  selectedRowId?: string;
};
```
Plain `<table>` built on the shadcn `Table` primitive. No client-side table engine, because
sorting, filtering and paging are server-side. **States.** Loading (8-row skeleton at the
current density), fetching (rows at 60% opacity + `aria-busy`), error (ErrorState in the body),
empty, no results, populated. **A11y.** `<caption>`, `<th scope="col">`, `aria-sort`, one link
per row (stretched), focus restored by row ID after refetch, and focus on the caption after a
page change. **Used by.** S-03, S-05, S-07, S-09, S-10, S-11, S-13, S-15, S-17, S-21, S-22.

### C-31 FilterBar
```ts
type FilterOption = { value: string; label: string; group?: string };
type FilterDef =
  | { key: string; label: string; type: "multi" | "single"; options: FilterOption[] }
  | { key: string; label: string; type: "combobox"; loadOptions: (q: string) => Promise<FilterOption[]> }
  | { key: string; label: string; type: "toggle" }
  | { key: string; label: string; type: "date-range"; presets: Array<"today" | "7d" | "30d" | "60d"> };
type FilterBarProps = {
  search?: { value: string; placeholder: string; onChange: (v: string) => void };
  filters: FilterDef[];
  values: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
  onClearAll: () => void;
  hiddenChips?: Array<{ key: string; label: string }>;     // evaluation_run_id, order_id…
  sort?: { value: string; options: FilterOption[]; onChange: (v: string) => void };
  resultCount?: number; resultNoun: string;                // "23 exceptions"
  trailing?: React.ReactNode;                               // density toggle
};
```
Filter buttons open Popovers with checkbox lists (multi) or a Command (combobox). Active filters
appear as removable chips ("Severity: Critical, High ×"). **Variants.** Inline (≥ 768) and
collapsed ("Filters (3)" opening a bottom sheet with **Apply** and **Reset**, < 768). **A11y.**
Each filter button has `aria-haspopup="dialog"` and shows its selected count in the name
("Severity, 2 selected"). Chip remove buttons are labelled "Remove filter Severity: Critical".
The result count is a polite live region. **Used by.** S-03, S-05, S-07, S-09, S-10, S-11, S-13,
S-15, S-17.

### C-32 SearchInput
```ts
type SearchInputProps = { value: string; onChange: (v: string) => void; placeholder: string; debounceMs?: number; shortcut?: "/" };
```
`type="search"`, a clear button, 300 ms debounce, and `/` focuses it (ignored while typing in
another field). **Used by.** C-31.

### C-33 Pagination
```ts
type PaginationProps = { page: number; pageSize: 25 | 50 | 100; total: number;
  onPageChange: (p: number) => void; onPageSizeChange: (s: 25 | 50 | 100) => void; pageSizes?: number[] };
```
"1–25 of 312", rows-per-page select, Previous and Next, "Page 2 of 13". **A11y.**
`nav[aria-label="Pagination"]`. Previous and Next disable with the real attribute at the bounds.
**Used by.** C-30.

### C-34 EmptyState
```ts
type EmptyStateProps = {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;                 // only if the user can do it
  variant?: "empty" | "no-results" | "success";
  activeFilters?: Array<{ key: string; label: string }>;  // no-results
  onClearFilters?: () => void;
  size?: "page" | "section";
};
```
**A11y.** The title is an `h2` (page) or `h3` (section). There is no live region on first render.
**Used by.** all data screens.

### C-35 ErrorState
```ts
type ErrorStateProps = { title: string; error?: ApiError; onRetry?: () => void; size?: "page" | "section" | "inline" };
```
Shows the message (generic for 5xx), the request ID with C-07, and **Try again**. A 429 renders
the countdown variant. **A11y.** `role="alert"` when it replaces content after a user action.
`role="status"` otherwise. **Used by.** all data screens.

### C-36 PermissionDenied
```ts
type PermissionDeniedProps = { pageName: string; permission: Permission };
```
Copy per SCREEN_SPECS §0.3 (demo variant included). **Used by.** S-00 guard and any route.

### C-37 NotFoundState
```ts
type NotFoundStateProps = { entity: "exception" | "order" | "product" | "import" | "conversation" | "store"; backHref: string };
```
"This {entity} doesn't exist or belongs to another store." **Used by.** S-04, S-06, S-08, S-13,
S-14, the shell.

### C-38 Skeletons
`TableSkeleton {rows=8, density}`, `KpiSkeleton {count}`, `SectionSkeleton {lines=3}`,
`DetailHeaderSkeleton`, `ChartSkeleton {height}`. All are `aria-hidden`. The parent region
carries `aria-busy`.

### C-39 KpiCard
**Purpose.** A single headline number that links to the list behind it.
```ts
type KpiCardProps = {
  label: string;                           // "Overdue orders"
  value: React.ReactNode;                  // formatted, text-display
  secondary?: React.ReactNode;             // "oldest 3d 4h"
  delta?: { node: React.ReactNode };       // C-03 PpDelta
  href?: string;
  info?: string;                           // tooltip text (definition)
  status: LoadStatus;
};
```
**Variants.** Link card (whole card is one `<a>`) and static. **States.** Loading skeleton, error
("—" + a retry icon button), success. No count-up animation. **A11y.** The accessible name
combines label, value and secondary ("Overdue orders: 7, oldest 3 days 4 hours. View overdue
orders."). The info tooltip trigger is a separate focusable button. **Used by.** S-02.

### C-40 StatTile
```ts
type StatTileProps = { label: string; value: React.ReactNode; hint?: React.ReactNode; tone?: "default" | "danger"; estimate?: boolean };
```
A compact metric without a link. **Used by.** S-08, S-12, S-13.

### C-41 DescriptionList
```ts
type DescriptionListProps = { items: Array<{ term: string; description: React.ReactNode; hint?: string }>; columns?: 1 | 2 };
```
`<dl>` semantics. Empty values render "—". **Used by.** S-04 Details, S-06, S-08, S-13, S-16
(read-only).

### C-42 ConfirmDialog
**Purpose.** Consistent confirmation for actions that end tracking, change configuration or
discard work.
```ts
type ConfirmDialogProps = {
  open: boolean; onOpenChange: (v: boolean) => void;
  title: string;                         // "Discard this import?"
  description: React.ReactNode;          // consequence, plainly stated
  confirmLabel: string;                  // repeats the verb: "Discard import"
  tone?: "default" | "destructive";
  pending?: boolean;
  error?: ApiError | null;               // shown as an Alert inside the dialog
  onConfirm: () => void | Promise<void>;
  children?: React.ReactNode;            // e.g. the settings diff list
};
```
**States.** Idle, pending (confirm button pending, Cancel disabled), error (Alert, dialog stays
open). **A11y.** Radix AlertDialog. Initial focus on **Cancel**. Escape cancels. Focus returns to
the trigger. **Used by.** S-12/S-13 (discard), S-16 (save), S-17 (role change uses the form
dialog pattern instead).

### C-43 ChartFrame
```ts
type ChartFrameProps = {
  title: string;                         // metric + window + zone
  subtitle?: string;
  status: LoadStatus; error?: ApiError; onRetry?: () => void;
  isEmpty: boolean; emptyMessage: string;
  ariaSummary: string;                   // "Orders per day, Oct 2 to Oct 31: min 14, max 41, latest 27"
  table: { columns: Array<{ key: string; header: string; align?: "left" | "right" }>; rows: Array<Record<string, React.ReactNode>> };
  height?: 200 | 240;
  actions?: React.ReactNode;             // "Ask the copilot about this chart"
  children: React.ReactNode;             // the chart
};
```
Chart / Table segmented toggle (ToggleGroup). The table view is a real `<table>`. **Used by.**
S-02, S-20.

### C-44 TimeSeriesChart
```ts
type TimeSeriesChartProps = {
  data: Array<{ date: string } & Record<string, number | null>>;     // store-local dates
  series: Array<{ key: string; label: string; color: "chart-1" | "chart-2" | "chart-3" | "chart-4" | "chart-neutral";
                  kind: "line" | "bar"; stackId?: string; estimate?: boolean }>;
  yFormat: "count" | "money" | "percent";
  partialLastBucket?: { until: IsoDateTime };
};
```
Recharts with `isAnimationActive={false}`, styling per DESIGN_SYSTEM §16. **A11y.** The SVG has
`role="img"` and an `aria-label` from ChartFrame. Tooltips are pointer-only, and the table view is
the keyboard path. **Used by.** S-02, S-20.

### C-45 BarBreakdown
**Purpose.** Small categorical counts (by category, by severity, by health) as accessible HTML
bars. Recharts is not needed for this.
```ts
type BarBreakdownProps = {
  items: Array<{ key: string; label: React.ReactNode; value: number; href?: string; emphasis?: boolean }>;
  format?: "count" | "money";
  max?: number;
};
```
Rows: label, a bar (`div` width %, `--chart-1`, or `--chart-emphasis` if `emphasis`), value
(right-aligned). **A11y.** It is a list (`ul`). Each row reads "Inventory, 9". Bars are
`aria-hidden`. **Used by.** S-02, S-20.

---

## 8. Exceptions (phase 5)

### C-50 PriorityBreakdown
**Purpose.** Show exactly how the priority score was calculated (PRIORITY_MODEL), so the ranking
is explainable.
```ts
type PriorityBreakdownProps = {
  breakdown: S["PriorityBreakdown"];   // {components[] {key, label, points, max_points, explanation}, total, uncapped_total, band, formula_version, as_of}
  dueAt: IsoDateTime;
  dueAtOverridden: boolean;
  severity: Severity;
};
```
A table with columns Component (`label`), Explanation (the rule-authored `explanation` sentence),
Points (`points / max_points`) and a meter. When `uncapped_total > 100`, the total row says "capped
at 100". The total row reads "81 / 100 ·
P1 (≥ 70)". A due-date basis line follows. A limitation note links to a popover with the formula
`min(100, S + A + E + D + T)` and the four PRIORITY_MODEL limitations. **States.** Populated only
(the data is always present). Missing breakdown → an inline "Priority breakdown unavailable" plus
the request ID (defect signal). **A11y.** `<table>` with a caption "Why this priority". Meters are
`aria-hidden`, and the points text carries the value. **Used by.** S-04.

### C-51 CalculationBlock
```ts
type CalculationBlockProps = { calculation: S["Calculation"] };
```
`S["Calculation"]` = `{formulas[], inputs{}, outputs{}, steps[]?}` (SCREEN_SPECS §0.4). Header:
"How this was detected · rule INV-OVERSOLD@1 · as of Oct 31, 9:45 AM EDT" (rule ID and `as_of`
from the exception). Body: the `formulas` as an ordered list in mono, then **Inputs** and
**Outputs** as key–value rows (keys humanised from snake_case, values formatted by type: money
strings via `Money`, ISO strings via `DateTime`, negative numbers in danger tone with U+2212), then
`steps` (if present) as a generic table whose columns are the step keys. **A11y.** Lists and
`<dl>`s, no layout tables. Formulas use real minus signs, with `aria-label` text forms. **Used
by.** S-04.

### C-52 EvidenceTable
```ts
type EvidenceTableProps = { evidence: S["Evidence"] };   // {facts[], records{}, notes[]}
```
Columns: Fact (`label`), Value (`value` + `unit`, formatted by its JSON type, with EstimateLabel
when `estimate`; `volatile` facts get a muted "changes over time" tooltip), Source (`source` →
link by `type`: `product`/`inventory_balance` → S-08, `order` → S-06, `inventory_movement` →
`/inventory/movements?product_id={product}`, `data_import` → S-13. `null` → "Calculated").
`records` groups other than `affected_orders` render as titled sub-tables below. `notes` render as
a bullet list. **States.** Populated. Empty → defect message (SCREEN_SPECS S-04). **A11y.**
Source links are named "{label}, opens {entity}". **Used by.** S-04.

### C-53 AffectedOrdersTable
```ts
type AffectedOrdersTableProps = {
  rows: Array<Record<string, unknown>>;   // evidence.records.affected_orders, rendered column by column
  total: number;
};
```
Uses C-30 (compact, no pagination, max 50 rows, then "Showing 50 of {n} affected orders"). Known
keys get formatted columns (order number → S-06 link, paid at, ship by, uncovered quantity, value at
risk). Unknown keys render as plain columns, so a rule can add a field without a UI change.
**Used by.** S-04.

### C-54 Timeline
**Purpose.** A chronological history for exceptions and orders.
```ts
type TimelineItem = {
  id: string; kind: "event" | "note";
  occurredAt: IsoDateTime;
  actor: { type: "USER" | "SYSTEM"; name?: string };
  icon: LucideIcon;
  title: React.ReactNode;              // "Morgan Lee changed status from Open to In progress"
  body?: React.ReactNode;              // note text, resolution note
  badge?: React.ReactNode;             // "AI draft, accepted by Sam Ortiz", "Import"
  detail?: React.ReactNode;            // expandable (evidence diff)
};
type TimelineProps = {
  items: TimelineItem[];
  order?: "newest-first" | "oldest-first";
  hasMore?: boolean; onLoadMore?: () => void; loadingMore?: boolean;
  filter?: "all" | "notes"; onFilterChange?: (f: "all" | "notes") => void;
};
```
Mappers: `toExceptionTimelineItems(events, notes, members)` (copy table in SCREEN_SPECS S-04) and
`toOrderTimelineItems(orderEvents)` ("Paid → Shipped, via Processing, Ready to ship"). **Variants.**
Exception (filterable, with notes) and order (events only). **States.** Loading (3 skeleton rows),
loading more, error (inline retry), populated. **A11y.** `<ol>` with each `<li>` containing a
`<time>`. Expandable details use Collapsible with `aria-expanded`. New items added by the user are
announced politely. **Used by.** S-04, S-06.

### C-55 NoteComposer
**Purpose.** Add append-only notes, optionally starting from an AI draft that a person must
review and save.
```ts
type NoteComposerProps = {
  exceptionId: string;
  canWrite: Gate;                       // exceptions.work
  canDraft: Gate;                       // copilot.use
};
```
**States.** Idle · typing (counter after 3,200/4,000) · drafting ("Drafting with copilot…") ·
draft-ready (an info strip above the textarea: "AI draft. Review and edit before saving. It is
saved only when you click Save note.", with buttons **Save note** and **Discard draft**) ·
submitting · error (inline, text kept, **Retry**) · read-only (`canWrite` false: the textarea is
replaced by the reason text). **Validation.** Body trimmed, 1–4,000 characters. The source is
`AI_DRAFT_ACCEPTED` when saving a draft (edited or not), otherwise `USER`. **A11y.** Labelled
textarea ("Add a note"). Ctrl/⌘ Enter submits. The draft strip is `role="status"`. **Used by.**
S-04.

### C-56 ExceptionActionBar (+ `getExceptionActions`)
**Purpose.** Show exactly the lifecycle actions the state machine and the viewer's permissions
allow, with reasons for the rest.
```ts
type ExceptionActionKind = "acknowledge" | "start" | "claim" | "resolve" | "dismiss" | "reopen";
type ExceptionAction = { kind: ExceptionActionKind; label: string; gate: Gate; opensDialog: boolean };
// Pure, table-tested against STATE_MACHINES §3.2 and the S-04 action table
declare function getExceptionActions(
  ex: { status: ExceptionStatus; assigneeId: string | null },
  viewer: { userId: string; permissions: Set<Permission>; isDemo: boolean }
): { primary?: ExceptionAction; secondary: ExceptionAction[]; more: ExceptionAction[] };

type ExceptionActionBarProps = {
  exception: S["ExceptionDetail"];
  onAction: (kind: ExceptionActionKind) => void;     // opens C-57 dialogs or runs the command
  pendingKind?: ExceptionActionKind;
  showExplainer?: boolean;                            // VIEWER: renders C-63 trigger
};
```
**Variants.** Inline (≥ 768) and sticky bottom bar (< 768: primary + **More** sheet). **States.**
Idle, one action pending (all others `aria-disabled`, "Another action is in progress."), all
disabled (demo). **A11y.** `role="toolbar"` `aria-label="Exception actions"` with arrow-key
navigation between buttons. The More menu items show their disabled reasons as item descriptions.
**Used by.** S-04.

### C-57 ResolveDialog / DismissDialog / ReopenDialog
```ts
type LifecycleDialogProps = { exception: S["ExceptionDetail"]; open: boolean; onOpenChange: (v: boolean) => void };
```
Fields, copy and Zod rules per SCREEN_SPECS S-04: Resolve `{resolution_code, resolution_note}`,
Dismiss `{reason, note}` (stored as `dismissed_reason`), Reopen `{reason}`. Resolve and dismiss
notes need at least 10 characters after trimming. Each body sends `expected_version`. **States.**
Idle, field errors, pending, `409 STALE_VERSION` (warning toast "Someone else updated EXC-1042…",
refetch, dialog kept open with its input, next submit carries the new version; closes if the new
status no longer allows the action), other errors (Alert + request ID). On success: close, toast, invalidate the exception, events and inbox
queries. **A11y.** Dialog title as `h2`. The first field receives focus. Errors are linked with
`aria-describedby`. The radio group (Dismiss) has a legend. **Used by.** S-04.

### C-58 AssigneeControl
```ts
type AssigneeControlProps = {
  assignee: { id: string; fullName: string } | null;
  canAssign: Gate;          // exceptions.assign
  canClaim: Gate;           // exceptions.work and unassigned
  exceptionId: string;
};
```
Read-only text when `canAssign` is not allowed (the reason is on focus). Otherwise a combobox
Popover: "Assign to me", members from `GET /stores/{id}/members` filtered to
`can_work_exceptions = true` (name + role, no emails), "Remove assignee". Commands: `POST /assign
{assignee_id}`, `POST /unassign`, `POST /claim`, each with `expected_version`.
**States.** Idle, loading members, pending (spinner in the trigger), error toast, conflict.
**A11y.** Combobox pattern. The trigger is labelled "Assignee: Unassigned, change". **Used by.**
S-04.

### C-59 DueDateControl
```ts
type DueDateControlProps = {
  dueAt: IsoDateTime;
  dueAtOverridden: boolean;          // true → "Set manually" note under the date
  canEdit: Gate; exceptionId: string; version: number;
};
```
Shows C-05 DueLabel plus an edit button. The Popover has date and time inputs in the store zone
(the zone abbreviation is shown next to the time), a required reason, and the note "A manual due
date is kept until the exception is reopened. Reopening recalculates it from the reopen time."
Sends `POST /set-due-date {due_at, reason, expected_version}`. Validation: the date must be in the
future. **Used by.** S-04.

### C-60 ExceptionLifecycleBanner
```ts
type ExceptionLifecycleBannerProps = { exception: S["ExceptionDetail"]; reopenEvent?: S["ExceptionEvent"] };
```
Selects the banner from the S-04 table (status, resolution code, `verified_at`, reopen reason,
supersession, previous occurrence). **A11y.** `role="status"`. **Used by.** S-04.

### C-61 RunAnalysisButton
```ts
type RunAnalysisButtonProps = { size?: "sm" | "md" };
```
Handles `POST /stores/{id}/evaluations` with an `Idempotency-Key` (synchronous, returns the run).
`SUCCEEDED` → completion toast with `counts`. `SKIPPED` (another run holds the store lock) → info
toast "An analysis is already running. Results will appear when it finishes." `FAILED` → error
toast "Analysis failed. No exceptions were changed." with the request ID. If the run comes back
`RUNNING`, it polls `GET …/evaluations/{rid}` every 2 s. Gated by `evaluations.run`. **Used by.** S-02, S-03, S-21.

### C-62 ExceptionListItem
```ts
type ExceptionListItemProps = { exception: S["ExceptionListItem"]; href: string; variant: "stacked" | "attention" };
```
The 3–4 line block for mobile lists (DESIGN_SYSTEM §11.5) and the Overview "Needs attention" rows.
The whole item is one link with the name "{reference}, {title}, {severity}, priority {band}
{score}, {status}, {due}". The reference (`EXC-1042`) leads the meta line. **Used by.** S-02, S-03 (< 768), S-22.

### C-63 LifecycleExplainer
**Purpose.** For demo viewers (and anyone curious), explain the resolution process without
pretending the buttons work.
```ts
type LifecycleExplainerProps = { exampleLinks?: { verified?: string; reopened?: string } };
```
A Popover with a compact ordered list: Open → Acknowledged → In progress → Resolved — awaiting
verification → Verified. The exception reopens instead if the condition is still present after
the next import, or after 24 h (grace rule, STATE_MACHINES §3.3–3.4). It links to live examples:
the first `RESOLVED` exception with `verified_at` set and a manual resolution code
(`GET exceptions?status=RESOLVED&page_size=25`, picked client-side), and the first `REOPENED` one
(`?status=REOPENED&page_size=1`). The demo seed guarantees both exist. Outside the demo a link is
hidden when no example is found. **Used by.** S-04 (VIEWER),
C-93.

---

## 9. Imports (phase 6)

### C-70 ImportTypePicker
```ts
type ImportType = "products" | "orders" | "order_items" | "inventory_adjustments";
type ImportTypePickerProps = { value: ImportType | null; onChange: (t: ImportType) => void; error?: string };
```
A RadioGroup of 4 cards (title, one-line description, upsert key, **Template** link) plus the
collapsible column reference. **A11y.** Native radio semantics. Each card is the label. The
template link is outside the radio label. **Used by.** S-12.

### C-71 ImportDropzone
**Purpose.** Choose one CSV file, with client-side checks before upload.
```ts
type ImportDropzoneProps = {
  file: File | null;
  onFileChange: (f: File | null) => void;
  maxBytes?: number;            // 5_000_000
  accept?: ".csv";
  error?: string;               // from the form
  disabled?: boolean;
  uploadProgress?: number;      // 0–100 while uploading
};
```
A visible **Choose file** button (wrapping `<input type="file" accept=".csv">`) inside a dashed
`--input` drop area ("or drag a CSV file here"). Drag-over state: `--surface-selected` with a
`--primary` border. Selected state: file icon, name, size (`formatBytes`), **Remove**. Client
checks: the `.csv` extension and size ≤ 5 MB, with SCREEN_SPECS S-12 copy. Encoding and row count
are left to the server. **States.** Empty, drag-over, selected, invalid, uploading (a
progress bar with "Uploading… 64%"), disabled (gate reason). **A11y.** The button is the primary
path. Drag-and-drop is an enhancement only. Errors are linked by `aria-describedby`. Progress uses
`role="progressbar"` with `aria-valuenow`. **Used by.** S-12.

### C-72 ImportStepper
```ts
type ImportStepperProps = { status: ImportStatus | "NEW" };
```
Maps status → step (NEW/UPLOADED → 1, VALIDATING/VALIDATED → 2, APPLYING → 3, terminal applied → 4).
Validation normally completes inside the upload request, so step 2 usually starts at `VALIDATED`.
Below 768 px it collapses to "Step 2 of 4 · Preview". **A11y.** `<ol>` with `aria-current="step"`
and "completed" text on finished steps. **Used by.** S-12.

### C-73 ImportStatusPanel
```ts
type ImportStatusPanelProps = { phase: "validating" | "applying"; rowCount: number; startedAt: IsoDateTime };
```
`motion-essential` spinner, "Validating 1,240 rows…" / "Applying 1,226 rows…", elapsed time, and
the safe-to-leave note. Shown while the upload or apply request is pending, and while a record is
observed in `UPLOADED`/`VALIDATING`/`APPLYING` (then the parent hook polls every 2 s). **A11y.** `role="status"`. The text
changes are announced at most every 10 s. **Used by.** S-12.

### C-74 ImportSummaryTiles
```ts
type ImportSummaryTilesProps = { summary: S["ImportSummary"]; phase: "preview" | "applied" };
```
Six C-40 tiles. Preview: `rows_total`, `creates`, `updates`, `unchanged`, `rows_with_errors`,
`rows_with_warnings`. Applied: `applied.{creates, updates, unchanged, skipped}` plus rows and
warnings. "Rows with errors" and "Skipped" use the danger and warning tones when > 0. **Used by.** S-12, S-13.

### C-75 IssueTable
**Purpose.** Every row-level and file-level issue, filterable, with fix hints and CSV export.
```ts
type IssueTableProps = { importId: string; counts: { error: number; warning: number } };
```
Uses C-30 (compact, server-paginated, `GET …/imports/{id}/issues?severity&code`). Tabs: All,
Errors, Warnings. Filters: code (multi, options from `summary.issue_counts_by_code`), row number.
Columns: Row, Column, Code (mono, with the "How to fix" tooltip from `importIssueMeta`, which
mirrors IMPORT_PIPELINE §6, including `STALE_CYCLE_COUNT`), Severity (pill), Message (API text),
Value (`raw_value`, mono, truncated at 40 characters, full value in the tooltip, rendered as text,
never as HTML). File-level issues (`row_number` null) are listed first with "File" in the Row
column. An unknown code shows the API message with no hint. **Download issues CSV** (`GET
…/issues.csv`: original columns plus `row_number`, `code`, `column`, `message`).
**States.** Loading, empty (success tone "No issues"), no-results, error, populated. **A11y.**
The code hint is reachable by focus (a button wrapping the code). **Used by.** S-12, S-13.

### C-76 ApplyPanel
**Purpose.** Make partial application an explicit, counted decision (BR-606).
```ts
type ApplyPanelProps = {
  importId: string;
  rowCount: number; validRows: number; errorRows: number;
  summary: S["ImportSummary"];
  gate: Gate;                               // imports.run
  onApplied: () => void;
};
```
A mode RadioGroup (Strict, Valid rows only), a consent checkbox (valid-rows-only only), the
"What will change" line, and a dynamic button label ("Apply 1,240 rows" / "Apply 1,226 rows, skip
14"). It sends `{mode, confirm_skipped_rows}` with an `Idempotency-Key` generated once per
`importId + mode` (a new key when the mode changes, to avoid `422 IDEMPOTENCY_KEY_REUSED`). In
valid-rows-only mode for Products or Orders it shows the cascade hint (IMPORT_PIPELINE §7).
**States.** Strict-blocked (button disabled with reason), consent-missing (button disabled with
reason), ready, pending ("Applying…"), error (inline, same key on retry). Maps the apply error
codes per SCREEN_SPECS S-12 (`IMPORT_HAS_ERRORS`, `IMPORT_SKIPPED_ROWS_NOT_CONFIRMED`,
`IMPORT_PREVIEW_EXPIRED`, `IMPORT_PREVIEW_STALE`, `IDEMPOTENT_REQUEST_IN_PROGRESS`,
`IMPORT_NOT_APPLICABLE`).
**A11y.** The fieldset has a legend "Apply mode". The disabled reason is in `aria-describedby`.
**Used by.** S-12.

---

## 10. Copilot (phase 7)

### C-80 CopilotAnswer
**Purpose.** Render the structured answer schema with fixed, labelled sections and visible
provenance, so facts, estimates and suggestions are never blended.
```ts
type CopilotAnswerProps = {
  answer: S["StructuredAnswer"];   // {summary, facts, metrics, estimates, recommendations, limitations, references, data_window, generated_by}
  meta: { createdAt: IsoDateTime; provider?: string; model?: string; latencyMs?: number };
  toolCalls?: S["ToolCall"][];
  variant: "full" | "compact";     // compact: S-04 aside, sections collapsible
};
```
Section order and rendering per SCREEN_SPECS S-14. In the `compact` variant the Summary is always
visible, other sections are Collapsibles showing counts ("Facts (3)"), and Recommendations is
expanded by default. Section headings are fixed strings ("Facts", "Metrics", "Estimates",
"Recommendations", "Limitations", "References"), never model-generated. Each section has a
distinct left rule: Facts and Metrics `--border-strong`, Estimates `--tone-caution-border` plus
the "est." label, Recommendations `--tone-primary-border`. Text stays in text tokens. Answer text is
rendered as plain text with line breaks. Model output is never rendered as HTML or markdown links.
**States.** Populated, partial (empty sections omitted except Limitations), stale (C-86 adds the
banner). **A11y.** Section headings `h3` (full) or `h4` (compact). Formulas toggle with
`aria-expanded`. The provenance footer is a `<footer>` inside the article. Each answer is an
`<article aria-label="Copilot answer, generated Oct 31, 9:51 AM EDT">`. **Used by.** S-04 (C-86),
S-14.

### C-81 ReferenceChip
```ts
type ReferenceChipProps = { reference: { type: "exception" | "order" | "product" | "import"; id: string; label: string } };
```
A tag-styled link whose text starts with the entity type ("Order KHK-10477", "Product
KHK-DO55-SGE", "Exception EXC-1042"). It has no icon, because the type word carries the meaning.
Without read permission for the type, it renders as plain text with a tooltip "You don't have
access to orders." **Used by.** C-80.

### C-82 ToolCallDisclosure
```ts
type ToolCallDisclosureProps = { calls: S["ToolCall"][] };
```
Collapsible "Data used: 3 read-only tools". Rows: a tool label from `toolNameLabels`
(get_dashboard_summary "Dashboard summary", list_exceptions "Exceptions list", get_exception
"Exception detail", get_exception_history "Exception history", get_related_orders "Related orders",
get_product "Product", get_inventory_position "Inventory position", get_inventory_movements
"Inventory movements", get_overdue_orders "Overdue orders", get_import_errors "Import errors",
get_operational_trends "Operational trends"), row count, duration, and status (failed calls in the
danger tone with their `error`). **Used by.** C-80.

### C-83 CopilotComposer
```ts
type CopilotComposerProps = {
  value: string; onChange: (v: string) => void; onSubmit: () => void;
  pending: boolean; rateLimitedUntil?: Date; maxLength?: number;  // 1000
  gate: Gate;                                                      // copilot.use
};
```
**States.** Empty, typing, over-limit, pending (Send disabled), rate-limited (countdown bar), no
permission. **A11y.** Textarea labelled "Ask the copilot". Enter submits, Shift+Enter adds a
newline (stated in visually hidden help text). **Used by.** S-14.

### C-84 ConversationList
```ts
type ConversationListProps = { conversations: S["AIConversation"][]; activeId?: string; status: LoadStatus; onNew: () => void };
```
`nav[aria-label="Conversations"]` list of links. The active item has `aria-current`. **Used by.** S-14.

### C-85 SuggestedQuestions
```ts
type SuggestedQuestionsProps = { questions: string[]; onPick: (q: string) => void };
```
Buttons that fill the composer and never auto-send. **Used by.** S-14.

### C-86 AIInvestigationPanel
**Purpose.** On-demand AI explanation of one exception, clearly separated from the deterministic
sections.
```ts
type AIInvestigationPanelProps = {
  exceptionId: string;
  lastEvidenceChangeAt: IsoDateTime;    // last_detected_at or the latest EVIDENCE_UPDATED event
  gate: Gate;                           // copilot.use
};
```
Header "AI investigation" with a muted note "Explains the evidence. It doesn't change data."
Generate and regenerate call `POST /stores/{id}/copilot/exception-summaries {exception_id,
refresh}` (cached per exception). Note drafts use `POST /stores/{id}/copilot/note-drafts`.
**States.** No permission (reason text), empty (one sentence + **Generate investigation**),
pending ("Reading evidence, history and related records…" + elapsed time), populated (C-80
compact + **Regenerate** + **Ask a follow-up**, which opens S-14 with exception context), stale
(warning strip "Evidence changed after this summary was generated. Regenerate to include the
latest data." when `generated_at < lastEvidenceChangeAt`), error (ErrorState section), rate
limited (countdown). **A11y.** `section aria-labelledby` the heading. Completion is announced
politely. **Used by.** S-04.

---

## 11. Admin and P1 (phase 8)

### C-90 SettingsField + SettingsSaveBar
```ts
type SettingsFieldProps = {
  name: string;                       // RHF path, e.g. "fulfillment_sla_hours"
  label: string; helper: string;      // helper cites the rule ID
  unit?: "hours" | "days" | "minutes" | "×" | "currency";
  defaultValue: number | string;      // shown as "Default 48"
  readOnly: boolean;                  // renders a definition-list row instead of an input
};
type SettingsSaveBarProps = { dirtyCount: number; pending: boolean; onDiscard: () => void; onSave: () => void };
```
The input has a unit suffix inside the field. The save bar is sticky at the bottom, visible only
when dirty. **A11y.** The unit is part of the accessible name ("Fulfillment SLA, hours"). The save
bar is `role="region"` `aria-label="Unsaved changes"`. **Used by.** S-16.

### C-91 RoleMatrix
```ts
type RoleMatrixProps = { roles: Array<{ role: string; permissions: Permission[] }>; permissionMeta: Array<{ code: Permission; label: string; description: string }> };
```
Data from `GET /api/v1/roles` (any authenticated user, `[{role, permissions[]}]`). The matrix is
never hard-coded in the UI. Labels and descriptions come from `permissionLabels`. **A11y.** A `<table>` with row headers
(permission) and column headers (role). Cells have "Granted" or "Not granted" as visually hidden
text. **Used by.** S-17, C-92.

### C-92 ChangeRoleDialog (P1)
```ts
type ChangeRoleDialogProps = { member: S["Member"]; currentUserId: string; ownerCount: number; open: boolean; onOpenChange: (v: boolean) => void };
```
A role select with descriptions, and a "What changes" list (gained and lost permissions computed
from C-91 data). Owner only (`users.manage`). Guards: not your own role, and never the last owner
(pre-checked with `ownerCount`, enforced by the server with `409 LAST_OWNER`). Sends `PATCH
/organizations/{org_id}/members/{membership_id} {role}`. There is no invite, deactivation or
password-reset component in v1. **Used by.** S-17.

### C-93 DemoTourPanel (P1)
**Purpose.** A guided path for public visitors through the six demo steps (USER_FLOWS F6), driven
by live data.
```ts
type DemoTourPanelProps = { open: boolean; onOpenChange: (v: boolean) => void };
type TourStep = { id: "dashboard" | "priority-issue" | "evidence" | "affected-orders" | "copilot" | "recommended-action" | "resolution";
                  title: string; body: string; target: () => Promise<string | null> };  // resolves an href from live queries
```
A right-side Sheet (bottom sheet < 768) with a numbered step list, the current step expanded,
**Go there** and **Next** buttons, and **Finish tour**. Targets are resolved at runtime (for
example the highest-priority active exception). A step with no target shows the fallback copy
from USER_FLOWS F6. There are no spotlight overlays and no auto-advance. The step index is kept in
`sessionStorage`. **A11y.** A non-modal Sheet (the page remains usable). Step changes are
announced. **Used by.** S-00 (DemoBanner **Take the tour**), `?tour=1`.

---

## 12. Screen × component coverage (P0)

| Screen | Key components |
|---|---|
| S-01 Login | Card, Form, Input, Button (pending), Alert |
| S-02 Overview | PageHeader, RunAnalysisButton, KpiCard, ExceptionListItem, BarBreakdown, ChartFrame, TimeSeriesChart, EmptyState, ErrorState |
| S-03 Inbox | PageHeader, Tabs (links), FilterBar, DataTable, PriorityIndicator, SeverityBadge, ExceptionStatusPill, Money, DueLabel, ExceptionListItem, RunAnalysisButton |
| S-04 Exception detail | PageHeader, ExceptionLifecycleBanner, ExceptionActionBar, PriorityBreakdown, CalculationBlock, EvidenceTable, AffectedOrdersTable, Timeline, NoteComposer, AssigneeControl, DueDateControl, AIInvestigationPanel, CopilotAnswer, LifecycleExplainer, DescriptionList, lifecycle dialogs |
| S-05 / S-06 Orders | DataTable, FilterBar, OrderStatusPill, axis texts, Money, DateTime, Timeline (order), DescriptionList |
| S-07 / S-08 Products | DataTable, HealthBadge, StatTile, EstimateLabel, DescriptionList |
| S-09 / S-10 Inventory | DataTable, ToggleGroup (health bar), Quantity/Delta, EstimateLabel |
| S-11..S-13 Imports | DataTable, ImportStatusPill, ImportTypePicker, ImportDropzone, ImportStepper, ImportStatusPanel, ImportSummaryTiles, IssueTable, ApplyPanel, ConfirmDialog |
| S-14 Copilot | ConversationList, CopilotAnswer, ReferenceChip, ToolCallDisclosure, CopilotComposer, SuggestedQuestions |
| S-15 Audit log | DataTable, FilterBar, CopyButton, Collapsible |
| S-16 Settings | SettingsField, SettingsSaveBar, ConfirmDialog, DescriptionList |
| S-17 Users & roles | DataTable, RoleMatrix, ChangeRoleDialog |
| All | AppShell, DemoBanner, SidebarNav, StoreSwitcher, TopBar, UserMenu, GlobalSearch, PermissionGate, ActionButton, Skeletons, PermissionDenied, NotFoundState |
