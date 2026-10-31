# Design System

> **Status:** v1 design specification (task T-030, milestone M3).
> Implementation targets: `apps/web/styles/tokens.css` (tokens), `apps/web/app/globals.css`
> (Tailwind theme mapping), `apps/web/lib/format/*` (formatters), `apps/web/lib/status-maps.ts`
> (enum → label, icon, tone). Components must use these tokens. Arbitrary hex values in components
> are not allowed (AGENTS.md §4).

---

## 1. Design direction

RetailOps Intelligence is a working tool for people who triage problems under time pressure.
The visual language borrows the restraint of well-regarded developer and finance dashboards.

| Principle | What it means in practice |
|---|---|
| **Neutral canvas, one accent** | Grey surfaces and text. Indigo (`--primary`) is reserved for interactive emphasis: primary buttons, links, focus, the active work state. It is never used for data meaning. |
| **Colour carries meaning or nothing** | Red/orange/yellow/green/blue appear only for severity, priority, status, health and validation. A colour never appears without a text label (and usually an icon). |
| **Typography does the hierarchy** | Size and weight, not boxes and colour, separate page title, section, and data. Borders separate regions. Shadows only lift floating layers. |
| **Dense but readable** | 14 px base text, 13 px in compact tables, 44 px default row height, tabular numerals everywhere. |
| **Calm motion** | Motion only explains a change of layer (a menu opens, a sheet slides in). Nothing counts up, bounces, glows, or animates on load. No gradients, no glassmorphism, no decorative charts. |
| **Honest data** | Estimates are labelled as estimates (BR-152). Exposure is "value at risk (gross)", never "loss" (BR-404). Times show their zone (BR-501). Seeded data is labelled (DemoBanner). |

Light theme ships in v1. All colours are defined as semantic tokens with a complete dark-mode
value set (§3.4), so dark mode is a provider switch, not a refactor.

---

## 2. Token architecture

Three layers. Components use **semantic** and **domain** tokens only.

| Layer | Example | Who uses it |
|---|---|---|
| Primitive | `--gray-600`, `--indigo-600`, `--red-700` | Only the token files |
| Semantic | `--foreground`, `--muted-foreground`, `--primary`, `--border`, `--tone-danger-fg` | Primitives (shadcn/ui) and layout |
| Domain | `--severity-critical-bg`, `--priority-p1-bar`, `--health-oversold-fg` | Product components (badges, indicators) |

> **Naming trap (shadcn/ui).** shadcn's `--accent` is the *subtle hover fill* used by menus and
> ghost buttons, not a brand colour. In this system the brand accent is `--primary` (indigo). Keep
> shadcn's names unchanged so generated components work without edits.

**Tones.** Every coloured badge, pill, callout and inline message picks one of eleven *tones*. A
tone is a triple of `fg` (text and icon), `bg` (fill) and `border`. Domain tokens alias tones, so
dark mode only has to redefine the tones.

| Tone | Meaning | Used by |
|---|---|---|
| `neutral` | Informational, no judgement | LOW severity, awaiting payment, P3 |
| `outline` | Default/new, not yet touched | OPEN status, closed orders |
| `muted` | Finished, no longer relevant | DISMISSED, Superseded, not-tracked health |
| `primary` | Actively being worked | IN_PROGRESS |
| `info` | Noted, in flight | ACKNOWLEDGED, Resolved — awaiting verification, orders to fulfil, import ready |
| `success` | Good outcome | Verified, Resolved · condition cleared, HEALTHY, fulfilled orders, import completed |
| `warning` | Needs attention soon | REOPENED, BELOW_REORDER_POINT, returns, completed with skipped rows |
| `caution` | Early signal | MEDIUM severity, APPROACHING_REORDER_POINT |
| `attention` | Serious | HIGH severity, P2, "Data issue" stock health (BR-402a) |
| `danger` | Problem now | OUT_OF_STOCK, payment failed, import failed/rejected, validation errors |
| `danger-solid` | Worst case on screen | CRITICAL severity, OVERSOLD (filled pill, white text) |

---

## 3. Colour

### 3.1 Primitives

```css
/* apps/web/styles/tokens.css — primitives (do not use in components) */
:root {
  /* Neutral (cool grey) */
  --gray-0:   #FFFFFF;
  --gray-25:  #FCFCFD;
  --gray-50:  #F8F9FA;
  --gray-100: #F1F3F5;
  --gray-150: #E9ECEF;
  --gray-200: #DEE2E6;
  --gray-300: #CED4DA;
  --gray-400: #9AA1A9;
  --gray-450: #8A939C;  /* lightest grey that meets 3:1 on white: input borders */
  --gray-500: #6C757D;  /* lightest grey that meets 4.5:1 on white: placeholder */
  --gray-600: #555D66;
  --gray-700: #3F464E;
  --gray-800: #2A3037;
  --gray-900: #1A1E23;
  --gray-950: #0E1114;

  /* Accent (indigo) — the only brand colour */
  --indigo-50:  #EEF0FC;
  --indigo-100: #E0E4FA;
  --indigo-200: #C2CAF4;
  --indigo-300: #9AA6EC;
  --indigo-500: #4A5BD6;
  --indigo-600: #3B4CCA;
  --indigo-700: #3140A8;
  --indigo-800: #283487;
  --indigo-900: #1E2347;

  /* Semantic hues */
  --green-50:  #ECFDF3; --green-200:  #ABEFC6; --green-600:  #079455; --green-700:  #067647;
  --amber-50:  #FFFAEB; --amber-200:  #FEDF89; --amber-600:  #DC6803; --amber-700:  #B54708;
  --red-50:    #FEF3F2; --red-200:    #FECDCA; --red-600:    #D92D20; --red-700:    #B42318; --red-800: #912018;
  --blue-50:   #EFF8FF; --blue-200:   #B2DDFF; --blue-600:   #1570EF; --blue-700:   #175CD3;
  --orange-50: #FEF6EE; --orange-200: #F9DBAF; --orange-600: #E04F16; --orange-700: #B93815;
  --yellow-50: #FEFBE8; --yellow-200: #FEEE95; --yellow-600: #CA8504; --yellow-700: #A15C07;
}
```

### 3.2 Semantic tokens (light, v1 default)

```css
:root {
  color-scheme: light;

  /* Surfaces & text (shadcn/ui names kept) */
  --background: var(--gray-50);            /* app canvas behind cards */
  --foreground: var(--gray-900);
  --card: var(--gray-0);
  --card-foreground: var(--gray-900);
  --popover: var(--gray-0);
  --popover-foreground: var(--gray-900);
  --muted: var(--gray-100);
  --muted-foreground: var(--gray-600);     /* secondary/meta text: 6.68:1 on white */
  --accent: var(--gray-100);               /* shadcn hover fill — NOT the brand colour */
  --accent-foreground: var(--gray-900);
  --secondary: var(--gray-100);
  --secondary-foreground: var(--gray-900);

  --primary: var(--indigo-600);
  --primary-foreground: var(--gray-0);
  --primary-hover: var(--indigo-700);
  --primary-active: var(--indigo-800);

  --destructive: var(--red-700);
  --destructive-foreground: var(--gray-0);
  --destructive-hover: var(--red-800);

  --border: var(--gray-200);               /* card, table, divider (decorative) */
  --border-strong: var(--gray-300);        /* section dividers, outline pills */
  --input: var(--gray-450);                /* form control boundary: 3.12:1 (WCAG 1.4.11) */
  --input-hover: var(--gray-500);          /* control boundary on hover / pressed outline button */
  --ring: var(--indigo-600);               /* focus ring: 6.83:1 */

  --text-secondary: var(--gray-700);
  --text-placeholder: var(--gray-500);
  --text-disabled: var(--gray-400);
  --text-link: var(--indigo-600);

  --surface-subtle: var(--gray-50);        /* table header, read-only field, code block */
  --surface-hover: var(--gray-50);         /* table row hover */
  --surface-selected: var(--indigo-50);    /* selected row, active filter chip */
  --surface-disabled: var(--gray-100);

  --sidebar: var(--gray-50);
  --sidebar-foreground: var(--gray-700);
  --sidebar-active: var(--gray-150);
  --sidebar-active-foreground: var(--gray-900);
  --sidebar-border: var(--gray-200);

  --overlay: rgb(14 17 20 / 0.48);         /* dialog/sheet scrim */

  --demo-banner: var(--gray-900);
  --demo-banner-foreground: var(--gray-0);
  --demo-banner-muted: var(--gray-300);

  /* Tones: fg / bg / border */
  --tone-neutral-fg: var(--gray-700);    --tone-neutral-bg: var(--gray-100);   --tone-neutral-border: var(--gray-200);
  --tone-outline-fg: var(--gray-800);    --tone-outline-bg: var(--gray-0);     --tone-outline-border: var(--gray-300);
  --tone-muted-fg: var(--gray-600);      --tone-muted-bg: var(--gray-100);     --tone-muted-border: var(--gray-200);
  --tone-primary-fg: var(--indigo-700);  --tone-primary-bg: var(--indigo-50);  --tone-primary-border: var(--indigo-200);
  --tone-info-fg: var(--blue-700);       --tone-info-bg: var(--blue-50);       --tone-info-border: var(--blue-200);
  --tone-success-fg: var(--green-700);   --tone-success-bg: var(--green-50);   --tone-success-border: var(--green-200);
  --tone-warning-fg: var(--amber-700);   --tone-warning-bg: var(--amber-50);   --tone-warning-border: var(--amber-200);
  --tone-caution-fg: var(--yellow-700);  --tone-caution-bg: var(--yellow-50);  --tone-caution-border: var(--yellow-200);
  --tone-attention-fg: var(--orange-700);--tone-attention-bg: var(--orange-50);--tone-attention-border: var(--orange-200);
  --tone-danger-fg: var(--red-700);      --tone-danger-bg: var(--red-50);      --tone-danger-border: var(--red-200);
  --tone-danger-solid-fg: var(--gray-0); --tone-danger-solid-bg: var(--red-700); --tone-danger-solid-border: var(--red-700);

  /* Solid marks (meters, dots, chart emphasis) */
  --mark-danger: var(--red-600);
  --mark-attention: var(--orange-600);
  --mark-warning: var(--amber-600);
  --mark-success: var(--green-600);
  --mark-info: var(--blue-600);

  /* Charts (see §16; categorical set validated for colour-vision deficiency) */
  --chart-1: #2A78D6;  --chart-2: #EB6834;  --chart-3: #1BAF7A;  --chart-4: #EDA100;
  --chart-neutral: var(--gray-450);
  --chart-grid: var(--gray-150);
  --chart-axis: var(--gray-300);
  --chart-emphasis: var(--red-600);
}
```

### 3.3 Domain tokens

Domain tokens alias tones (they resolve to the hex values shown in §3.5). Each family has `-fg`,
`-bg`, `-border`. Only the declarations that differ from the pattern are shown in full.

```css
:root {
  /* Severity (EXCEPTION_CATALOG) */
  --severity-critical-fg: var(--tone-danger-solid-fg); --severity-critical-bg: var(--tone-danger-solid-bg); --severity-critical-border: var(--tone-danger-solid-border);
  --severity-high-fg: var(--tone-attention-fg);        --severity-high-bg: var(--tone-attention-bg);        --severity-high-border: var(--tone-attention-border);
  --severity-medium-fg: var(--tone-caution-fg);        --severity-medium-bg: var(--tone-caution-bg);        --severity-medium-border: var(--tone-caution-border);
  --severity-low-fg: var(--tone-neutral-fg);           --severity-low-bg: var(--tone-neutral-bg);           --severity-low-border: var(--tone-neutral-border);

  /* Exception status (STATE_MACHINES §3.1) */
  /* --status-open-{fg,bg,border}         = --tone-outline-{fg,bg,border} */
  /* --status-acknowledged-{fg,bg,border} = --tone-info-{fg,bg,border} */
  /* --status-in-progress-{fg,bg,border}  = --tone-primary-{fg,bg,border} */
  /* --status-reopened-{fg,bg,border}     = --tone-warning-{fg,bg,border} */
  /* --status-resolved-{fg,bg,border}     = --tone-success-{fg,bg,border} */
  /* --status-dismissed-{fg,bg,border}    = --tone-muted-{fg,bg,border} */

  /* Priority bands (PRIORITY_MODEL): text + meter bars, no fill */
  --priority-p1-fg: var(--red-700);    --priority-p1-bar: var(--red-600);
  --priority-p2-fg: var(--orange-700); --priority-p2-bar: var(--orange-600);
  --priority-p3-fg: var(--gray-700);   --priority-p3-bar: var(--gray-600);
  --priority-p4-fg: var(--gray-600);   --priority-p4-bar: var(--gray-500);
  --priority-bar-empty: var(--gray-200);

  /* Stock health (BUSINESS_RULES §2.5) */
  /* --health-oversold-{fg,bg,border}             = --tone-danger-solid-{fg,bg,border} */
  /* --health-out-of-stock-{fg,bg,border}         = --tone-danger-{fg,bg,border} */
  /* --health-below-reorder-{fg,bg,border}        = --tone-warning-{fg,bg,border} */
  /* --health-approaching-reorder-{fg,bg,border}  = --tone-caution-{fg,bg,border} */
  /* --health-healthy-{fg,bg,border}              = --tone-success-{fg,bg,border} */
  /* --health-not-tracked-{fg,bg,border}          = --tone-muted-{fg,bg,border}   (non-ACTIVE products) */
  /* --health-data-issue-{fg,bg,border}           = --tone-attention-{fg,bg,border} (on_hand < 0, BR-402a) */

  /* Order status groups (STATE_MACHINES §1) */
  /* --order-awaiting-payment-{fg,bg,border} = --tone-neutral-{fg,bg,border}   CREATED, PAYMENT_PENDING */
  /* --order-payment-failed-{fg,bg,border}   = --tone-danger-{fg,bg,border}    PAYMENT_FAILED */
  /* --order-to-fulfill-{fg,bg,border}       = --tone-info-{fg,bg,border}      PAID, PROCESSING, READY_TO_SHIP */
  /* --order-fulfilled-{fg,bg,border}        = --tone-success-{fg,bg,border}   SHIPPED, DELIVERED */
  /* --order-returns-{fg,bg,border}          = --tone-warning-{fg,bg,border}   RETURN_REQUESTED, RETURNED */
  /* --order-closed-{fg,bg,border}           = --tone-outline-{fg,bg,border}   CANCELLED, REFUNDED */

  --overdue-fg: var(--red-700);   /* "Overdue 30h" inline flag */
}
```

> The commented `{fg,bg,border} = --tone-x-…` lines stand for three declarations each, for
> example `--status-open-fg: var(--tone-outline-fg); --status-open-bg: var(--tone-outline-bg);
> --status-open-border: var(--tone-outline-border);`. Write them out in full in `tokens.css`.

### 3.4 Dark-mode values (ready, not shipped in v1)

Applied with `.dark` on `<html>` (next-themes, `attribute="class"`). Only semantic tokens and tones
change. Domain tokens follow automatically, except priority bars.

```css
.dark {
  color-scheme: dark;
  --background: #0E1114;  --foreground: #ECEEF0;
  --card: #15191D;        --card-foreground: #ECEEF0;
  --popover: #1B2025;     --popover-foreground: #ECEEF0;
  --muted: #22272D;       --muted-foreground: #9AA3AC;
  --accent: #22272D;      --accent-foreground: #ECEEF0;
  --secondary: #22272D;   --secondary-foreground: #ECEEF0;
  --primary: #4A5BD6;     --primary-foreground: #FFFFFF; --primary-hover: #5A6ADB; --primary-active: #3B4CCA;
  --destructive: #C9281C; --destructive-foreground: #FFFFFF; --destructive-hover: #D92D20;
  --border: #2A3037;      --border-strong: #3F464E; --input: #6B747E; --input-hover: #87909A; --ring: #9AA6EC;
  --text-secondary: #C4CAD0; --text-placeholder: #87909A; --text-disabled: #5B636C; --text-link: #9AA6EC;
  --surface-subtle: #1B2025; --surface-hover: #1B2025; --surface-selected: #1E2347; --surface-disabled: #22272D;
  --sidebar: #0E1114; --sidebar-foreground: #C4CAD0; --sidebar-active: #22272D; --sidebar-active-foreground: #ECEEF0; --sidebar-border: #2A3037;
  --overlay: rgb(0 0 0 / 0.64);
  --demo-banner: #C4CAD0; --demo-banner-foreground: #1A1E23; --demo-banner-muted: #3F464E;

  --tone-neutral-fg: #C4CAD0;   --tone-neutral-bg: #22272D;   --tone-neutral-border: #3F464E;
  --tone-outline-fg: #ECEEF0;   --tone-outline-bg: #15191D;   --tone-outline-border: #3F464E;
  --tone-muted-fg: #9AA3AC;     --tone-muted-bg: #22272D;     --tone-muted-border: #2A3037;
  --tone-primary-fg: #C2CAF4;   --tone-primary-bg: #1E2347;   --tone-primary-border: #2E3570;
  --tone-info-fg: #53B1FD;      --tone-info-bg: #0B2440;      --tone-info-border: #1849A9;
  --tone-success-fg: #47CD89;   --tone-success-bg: #0B2A1C;   --tone-success-border: #085D3A;
  --tone-warning-fg: #FDB022;   --tone-warning-bg: #2E1E07;   --tone-warning-border: #93370D;
  --tone-caution-fg: #EAAA08;   --tone-caution-bg: #2A2205;   --tone-caution-border: #854A0E;
  --tone-attention-fg: #F38744; --tone-attention-bg: #2D1709; --tone-attention-border: #932F19;
  --tone-danger-fg: #F97066;    --tone-danger-bg: #2F1211;    --tone-danger-border: #912018;
  --tone-danger-solid-fg: #FFFFFF; --tone-danger-solid-bg: #C9281C; --tone-danger-solid-border: #C9281C;

  --mark-danger: #F04438; --mark-attention: #F38744; --mark-warning: #F79009; --mark-success: #17B26A; --mark-info: #2E90FA;
  --priority-p1-fg: #F97066; --priority-p1-bar: #F04438;
  --priority-p2-fg: #F38744; --priority-p2-bar: #F38744;
  --priority-p3-fg: #C4CAD0; --priority-p3-bar: #9AA3AC;
  --priority-p4-fg: #9AA3AC; --priority-p4-bar: #6B747E;
  --priority-bar-empty: #2A3037;
  --overdue-fg: #F97066;
  --chart-1: #3987E5; --chart-2: #D95926; --chart-3: #199E70; --chart-4: #C98500;
  --chart-neutral: #6B747E; --chart-grid: #2A3037; --chart-axis: #3F464E; --chart-emphasis: #F04438;
}
```

### 3.5 Resolved domain colours (light)

| Family | Value | Label (UI) | Icon (lucide) | fg | bg | border |
|---|---|---|---|---|---|---|
| Severity | `CRITICAL` | Critical | `octagon-alert` | `#FFFFFF` | `#B42318` | `#B42318` |
| | `HIGH` | High | `triangle-alert` | `#B93815` | `#FEF6EE` | `#F9DBAF` |
| | `MEDIUM` | Medium | `circle-alert` | `#A15C07` | `#FEFBE8` | `#FEEE95` |
| | `LOW` | Low | `circle-minus` | `#3F464E` | `#F1F3F5` | `#DEE2E6` |
| Exception status | `OPEN` | Open | `circle` | `#2A3037` | `#FFFFFF` | `#CED4DA` |
| | `ACKNOWLEDGED` | Acknowledged | `eye` | `#175CD3` | `#EFF8FF` | `#B2DDFF` |
| | `IN_PROGRESS` | In progress | `circle-play` | `#3140A8` | `#EEF0FC` | `#C2CAF4` |
| | `REOPENED` | Reopened | `rotate-ccw` | `#B54708` | `#FFFAEB` | `#FEDF89` |
| | `RESOLVED`, manual, `verified_at` null | Resolved — awaiting verification | `hourglass` | `#175CD3` | `#EFF8FF` | `#B2DDFF` |
| | `RESOLVED`, `verified_at` set | Verified | `circle-check` | `#067647` | `#ECFDF3` | `#ABEFC6` |
| | `RESOLVED`, `CONDITION_CLEARED` | Resolved · condition cleared | `circle-check` | `#067647` | `#ECFDF3` | `#ABEFC6` |
| | `RESOLVED`, `SUPERSEDED` | Superseded | `corner-up-right` | `#555D66` | `#F1F3F5` | `#DEE2E6` |
| | `DISMISSED` | Dismissed | `circle-slash` | `#555D66` | `#F1F3F5` | `#DEE2E6` |
| Priority | `P1` (≥ 70) | P1 | 4 of 4 bars | `#B42318` | none | bars `#D92D20` |
| | `P2` (50–69) | P2 | 3 of 4 bars | `#B93815` | none | bars `#E04F16` |
| | `P3` (30–49) | P3 | 2 of 4 bars | `#3F464E` | none | bars `#555D66` |
| | `P4` (< 30) | P4 | 1 of 4 bars | `#555D66` | none | bars `#6C757D` |
| Stock health | `OVERSOLD` | Oversold | `circle-x` | `#FFFFFF` | `#B42318` | `#B42318` |
| | `OUT_OF_STOCK` | Out of stock | `package-x` | `#B42318` | `#FEF3F2` | `#FECDCA` |
| | `BELOW_REORDER_POINT` | Below reorder point | `trending-down` | `#B54708` | `#FFFAEB` | `#FEDF89` |
| | `APPROACHING_REORDER_POINT` | Approaching reorder point | `arrow-down-right` | `#A15C07` | `#FEFBE8` | `#FEEE95` |
| | `HEALTHY` | Healthy | `circle-check` | `#067647` | `#ECFDF3` | `#ABEFC6` |
| | (non-ACTIVE product) | Not tracked | `minus` | `#555D66` | `#F1F3F5` | `#DEE2E6` |
| | (`on_hand < 0`, any status) | Data issue | `database` | `#B93815` | `#FEF6EE` | `#F9DBAF` |
| Order status group | Awaiting payment (`CREATED`, `PAYMENT_PENDING`) | Created / Payment pending | `clock` | `#3F464E` | `#F1F3F5` | `#DEE2E6` |
| | Payment failed (`PAYMENT_FAILED`) | Payment failed | `circle-x` | `#B42318` | `#FEF3F2` | `#FECDCA` |
| | To fulfil (`PAID`, `PROCESSING`, `READY_TO_SHIP`) | Paid / Processing / Ready to ship | `package` | `#175CD3` | `#EFF8FF` | `#B2DDFF` |
| | Fulfilled (`SHIPPED`, `DELIVERED`) | Shipped / Delivered | `truck` / `package-check` | `#067647` | `#ECFDF3` | `#ABEFC6` |
| | Returns (`RETURN_REQUESTED`, `RETURNED`) | Return requested / Returned | `undo-2` | `#B54708` | `#FFFAEB` | `#FEDF89` |
| | Closed (`CANCELLED`, `REFUNDED`) | Cancelled / Refunded | `ban` / `receipt` | `#2A3037` | `#FFFFFF` | `#CED4DA` |

**`RESOLVED` is shown in four forms**, derived from `resolution_code` and `verified_at`
(STATE_MACHINES §3.3–3.4). A manual resolution reads "Resolved — awaiting verification" (info
tone, `hourglass`) until `verified_at` is set, then "Verified". The verification grace rule means
a manual resolution can legitimately stay unverified until the next import completes or 24 h
pass, so the label must not claim success early. Automatic resolutions read "Resolved · condition
cleared", and supersessions read "Superseded".

**"Data issue" overrides stock health.** When `on_hand < 0`, the stock figure is invalid input.
Only `DATA_NEGATIVE_ON_HAND` is raised and every inventory rule is suppressed (BR-402a), so a
health class computed from `available` would be misleading. `HealthBadge` shows "Data issue" for
any product status, with the tooltip "On hand is negative (−3). That is physically impossible,
so stock health can't be computed until a cycle count corrects it (BR-402a)."

**Order secondary axes** (`payment_status`, `fulfillment_status`) use the same tones, shown as
smaller text-only pills on the order detail page and as plain text in table columns:
payment `PENDING` neutral · `PAID` success · `FAILED` danger · `REFUNDED` muted. Fulfillment
`UNFULFILLED` neutral · `IN_PROGRESS` info · `SHIPPED`/`DELIVERED` success · `RETURNED` warning.

**Import status** (`data_import.status`): `UPLOADED`/`VALIDATING` "Validating" neutral `loader`
(static icon, see §10) · `VALIDATED` "Ready to apply" info `file-check` · `APPLYING` "Applying"
info `loader` · `COMPLETED` "Completed" success `circle-check` · `COMPLETED_WITH_ERRORS`
"Completed, rows skipped" warning `circle-alert` · `FAILED` "Failed" danger `circle-x` ·
`REJECTED` "Rejected" danger `file-x` · `DISCARDED` "Discarded" muted `circle-slash`.

**Import issue severity:** `ERROR` danger `circle-x` · `WARNING` warning `triangle-alert`.

**Membership role:** plain text with no colour (roles are not states).

### 3.6 Colour usage rules

1. Only `danger-solid` uses a filled background with white text, and only for CRITICAL severity
   and OVERSOLD health. If everything is loud, nothing is.
2. Priority never uses a filled pill. Severity is a pill, priority is a meter plus number. The
   different shapes stop the two from being confused in the same row.
3. The accent (`--primary`) never encodes data. A chart series, a KPI value or a status never
   turns indigo, except the `IN_PROGRESS` status ("your team is on it").
4. Negative quantities (`available < 0`) and overdue durations use `--tone-danger-fg` text with a
   minus sign (U+2212) or the word "Overdue". The colour supplements the sign and never replaces it.
5. Validation errors use `--tone-danger-*`. Warnings use `--tone-warning-*`. Neither is used
   decoratively.

---

## 4. Typography

### 4.1 Font loading

```ts
// apps/web/app/fonts.ts
import { Inter } from "next/font/google";
export const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
// <html className={inter.variable}> ; body uses var(--font-sans)
```

```css
:root {
  --font-sans: var(--font-inter), ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-mono: ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
}
body {
  font-family: var(--font-sans);
  font-size: 14px; line-height: 20px;
  font-variant-numeric: tabular-nums;   /* every number in the product aligns */
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
```

**Numerals.** Tabular figures are set globally, so money, quantities, timestamps, scores and axis
ticks align in columns and do not shift width when they refresh. Machine identifiers
(`request_id`, file SHA-256, raw CSV values, rule IDs, issue codes) use `--font-mono` with
`slashed-zero`. Human references (exception reference `EXC-1042`, SKUs, order numbers) stay in
Inter at weight 500, because they are read and spoken more than compared.

### 4.2 Type scale

| Token (Tailwind class) | Size / line height | Weight | Tracking | Role |
|---|---|---|---|---|
| `text-display` | 28 / 34 px | 600 | −0.015em | KPI value on Overview |
| `text-title-lg` | 20 / 28 px | 600 | −0.01em | Page title (`h1`), one per page |
| `text-title` | 16 / 24 px | 600 | −0.005em | Section title (`h2`), dialog title |
| `text-title-sm` | 14 / 20 px | 600 | 0 | Card title, sub-section (`h3`), table group header |
| `text-body` | 14 / 20 px | 400 | 0 | Default UI text, form inputs (≥ 640 px) |
| `text-body-strong` | 14 / 20 px | 500 | 0 | Primary cell in a row, emphasised values, buttons |
| `text-sm` | 13 / 18 px | 400 | 0 | Compact table cells, meta lines, breadcrumbs |
| `text-xs` | 12 / 16 px | 500 | 0.005em | Column headers, badges, helper and error text, chart axes |
| `text-overline` | 11 / 16 px | 600 | 0.06em, uppercase | Sidebar group labels only |
| `text-prose` | 14 / 22 px | 400 | 0 | Long-form text: copilot answers, notes, rule recommendations |
| `text-mono` | 12 / 16 px | 400 | 0 | IDs, codes, formulas, raw values (`font-mono`) |

Rules:
- Minimum size is 12 px. The only exception is `text-overline` (11 px uppercase semibold), used
  for sidebar group labels.
- Below 640 px, `input`, `select` and `textarea` use 16 px so iOS Safari does not zoom on focus.
- Headings follow document order: one `h1` per page (PageHeader), `h2` per section, `h3` inside
  cards. Never skip a level for visual size. Use the class instead.
- Sentence case for every label, title, button and menu item ("Run analysis", not "Run Analysis").
- Text never wears a data/series colour, except inside a tone pill where fg/bg are a tested pair.

---

## 5. Spacing and layout

Base unit 4 px (Tailwind default `--spacing: 0.25rem`). Allowed steps: `0.5` (2), `1` (4),
`1.5` (6), `2` (8), `3` (12), `4` (16), `5` (20), `6` (24), `8` (32), `10` (40), `12` (48),
`16` (64). Other values need a design review.

| Token | Value | Use |
|---|---|---|
| `--demo-banner-h` | 36 px (≥ 640), 32 px (< 640) | Demo banner |
| `--topbar-h` | 56 px | Top bar |
| `--sidebar-w` | 240 px | Expanded sidebar |
| `--sidebar-w-collapsed` | 56 px | Collapsed sidebar (icon rail) |
| `--page-gutter` | 16 px (< 768), 24 px (768–1279), 32 px (≥ 1280) | Horizontal page padding |
| `--content-max` | 1440 px | Max content width (centred on wider screens) |
| `--aside-w` | 360 px | Right column on detail pages (≥ 1280) |
| Card padding | 16 px (< 768), 20 px (≥ 768) | `Card` |
| Section gap | 24 px | Between page sections |
| Stack gap | 12 px | Between fields, between related blocks |
| Inline gap | 8 px | Icon + label, button groups, chips |
| Page header → content | 24 px | |

---

## 6. Radius, borders, shadows, z-index

| Token | Value | Use |
|---|---|---|
| `--radius-sm` | 4 px | Badges, pills, checkboxes, kbd hints |
| `--radius-md` | 6 px | Buttons, inputs, selects, menu items, tooltips |
| `--radius-lg` | 8 px | Cards, popovers, dropdowns, dialogs, tables (outer) |
| `--radius-full` | 9999 px | Avatars, count badges, status dots |

shadcn `--radius` is set to `6px`. Pills are `--radius-sm`, not fully rounded. That is more
precise at small sizes and distinguishes them from count badges.

**Borders.** 1 px everywhere. `--border` for cards, tables and dividers. `--border-strong` for
outline pills and section separators inside cards. `--input` for form controls (meets 3:1).
Tables have horizontal row dividers only. There are no vertical cell borders, except for the
sticky first column, which gets a right border when the table is horizontally scrolled.

| Shadow token | Value | Use |
|---|---|---|
| `--shadow-none` | `none` | Cards, tables, buttons: borders only |
| `--shadow-popover` | `0 4px 12px -2px rgb(16 24 40 / 0.10), 0 2px 4px -2px rgb(16 24 40 / 0.06)` | Popover, dropdown, combobox, tooltip, command palette |
| `--shadow-dialog` | `0 16px 32px -8px rgb(16 24 40 / 0.18), 0 4px 8px -4px rgb(16 24 40 / 0.08)` | Dialog, sheet, mobile drawer |
| `--shadow-sticky` | `0 1px 0 0 var(--border)` | Sticky table header / action bar once content scrolls under it |

| z-index token | Value | Layer |
|---|---|---|
| `--z-base` | 0 | Content |
| `--z-sticky-cell` | 10 | Sticky table header and first column |
| `--z-sticky-bar` | 20 | Sticky page action bar (exception detail on mobile) |
| `--z-sidebar` | 30 | Sidebar |
| `--z-topbar` | 40 | Top bar and demo banner |
| `--z-dropdown` | 50 | Dropdown, popover, combobox, command palette |
| `--z-overlay` | 60 | Dialog/sheet scrim and content |
| `--z-toast` | 70 | Toasts |
| `--z-tooltip` | 80 | Tooltips (above dialogs) |
| `--z-skip-link` | 90 | "Skip to content" link |

---

## 7. Motion

| Token | Value | Use |
|---|---|---|
| `--duration-fast` | 100 ms | Colour, background and border changes on hover/press |
| `--duration-base` | 150 ms | Tooltip, popover, dropdown: fade + scale 0.98 → 1 |
| `--duration-slow` | 200 ms | Dialog fade + scale, sheet/drawer slide, sidebar width collapse |
| `--ease-standard` | `cubic-bezier(0.2, 0, 0, 1)` | Entering |
| `--ease-exit` | `cubic-bezier(0.4, 0, 1, 1)` | Leaving (use 75% of the enter duration) |

**Never animated:** page transitions, data arriving, KPI numbers, chart drawing (Recharts
`isAnimationActive={false}` on every series), list re-sorting, toasts other than a fade, and
anything on page load.

**Skeletons:** a 2 s opacity pulse between 1 and 0.6. Under reduced motion they are static.

**Reduced motion:**

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
  .motion-essential { animation-duration: 1s !important; animation-iteration-count: infinite !important; }
}
```

The only `motion-essential` element is the 16 px progress spinner inside a pending button or an
import in `VALIDATING`/`APPLYING`. It is the sole indication that work is happening, and it
always comes with a text label ("Applying 1,240 rows…").

---

## 8. Breakpoints and responsive rules

Tailwind defaults: `sm` 640 · `md` 768 · `lg` 1024 · `xl` 1280 · `2xl` 1536. Supported minimum
viewport: **360 px**. Nothing may scroll horizontally at the page level at 360 px. Tables may
scroll inside their own container.

| Range | Navigation | Lists | Detail pages | Dialogs |
|---|---|---|---|---|
| 360–767 | Top bar with menu button. Sidebar becomes a left drawer (Sheet, 280 px, max 85vw). | **Stacked rows**: each row renders as a 2–3 line block (see §11.5). Filters collapse into a "Filters (3)" button that opens a bottom sheet. | Single column. Sections in priority order. Sticky bottom action bar for the primary action. | Full-screen sheet from the bottom. |
| 768–1023 | Collapsed icon rail (56 px), with tooltips. It expands as an overlay on demand. | Full table with low-priority columns hidden (each table spec lists `hideBelow`). | Single column, wider. | Centred dialog, max-width 560 px. |
| 1024–1279 | Expanded sidebar (240 px). The user can collapse it, and the choice is persisted. | Full table. | Single column with a two-column card grid where noted. | Centred. |
| ≥ 1280 | Expanded sidebar. | Full table, content max 1440 px. | Main + 360 px right aside. | Centred. |

---

## 9. Focus ring and keyboard

- Visible only on keyboard focus (`:focus-visible`). Never remove an outline without a
  replacement.
- Default ring: `outline: 2px solid var(--ring); outline-offset: 2px; border-radius: inherit`.
  6.83:1 on white, 6.48:1 on the canvas.
- Form controls: `border-color: var(--ring); box-shadow: 0 0 0 1px var(--ring)` (2 px total,
  no offset, so it doesn't clip inside tables). Invalid control: the same but with
  `--tone-danger-fg`.
- Table row links: `outline-offset: -2px` (inset), so the ring is not clipped by the table container.
- A "Skip to content" link is the first focusable element and becomes visible on focus.
- Focus order follows reading order. Dialogs trap focus and return it to the trigger on close
  (Radix default). After a mutation that removes the focused element (a row leaves the inbox),
  focus moves to the next row, or to the table caption if none remains.

---

## 10. Interaction states

| Element | Default | Hover | Active (pressed) | Focus-visible | Disabled | Loading / pending |
|---|---|---|---|---|---|---|
| Button, primary | bg `--primary`, text `--primary-foreground` | bg `--primary-hover` | bg `--primary-active` | ring | bg `--surface-disabled`, text `--text-disabled`, border `--border` | Leading icon replaced by a spinner, label becomes the present participle ("Resolving…"), width locked, `aria-busy="true"`, clicks ignored |
| Button, secondary (outline) | bg `--card`, border `--input`, text `--foreground` | bg `--accent` | bg `--muted`, border `--input-hover` | ring | same as primary disabled | same |
| Button, ghost | transparent, text `--text-secondary` | bg `--accent`, text `--foreground` | bg `--muted` | ring | text `--text-disabled` | same |
| Button, destructive | bg `--destructive`, text `--destructive-foreground` | bg `--destructive-hover` | bg `--destructive-hover` | ring | as primary disabled | same |
| Link | text `--text-link`, no underline in tables and nav, underline in prose | underline | text `--primary-active` | ring | n/a | n/a |
| Table row (navigable) | bg `--card` | bg `--surface-hover` | bg `--muted` | inset ring on the row link | n/a | Row being mutated: 60% opacity, `aria-busy` |
| Table row (selected) | bg `--surface-selected` plus 2 px left inset `--primary` | unchanged | n/a | ring | n/a | n/a |
| Input / select / textarea | bg `--card`, border `--input` | border `--input-hover` | n/a | ring (see §9) | bg `--surface-disabled`, border `--border`, text `--text-disabled` | n/a |
| Menu item | transparent | bg `--accent` | bg `--muted` | bg `--accent` (Radix highlight) | text `--text-disabled`, plus a reason in the item's description line | n/a |
| Sidebar item | text `--sidebar-foreground` | bg `--accent` | bg `--muted` | ring | n/a | n/a |
| Sidebar item, current | bg `--sidebar-active`, text `--sidebar-active-foreground`, icon `--primary`, `aria-current="page"` | unchanged | unchanged | ring | n/a | n/a |

**Permission-disabled actions** use `aria-disabled="true"`, not the `disabled` attribute, so they
stay focusable and their tooltip ("The public demo is read-only.") can be reached by keyboard and
screen reader. The click handler is a no-op, and the reason is also exposed via
`aria-describedby`. Disabled-by-state actions (a transition that is not allowed) follow the same
pattern. The `disabled` attribute is used only while a form submission is in flight.

**Pending mutations.** Optimistic updates are **not** used for lifecycle transitions: the server
may reject them with 409 (`EXCEPTION_TRANSITION_NOT_ALLOWED`, or `STALE_VERSION` when the sent
`expected_version` differs from `operational_exception.version`). The button shows its pending
state until the response arrives (typically < 500 ms), then the page data is invalidated and
refetched. Notes may be optimistic (append-only, no state machine).

**Stale version (409 `STALE_VERSION`).** Every exception command sends the `version` the user is
looking at as `expected_version`. On a mismatch the UI (1) shows a warning toast "Someone else
updated EXC-1042. The latest details are now shown. Review them and try again.", (2) refetches
the exception, its events and notes, and (3) keeps any open dialog open with the user's input,
so the next submit carries the new version. If the refetched status no longer allows the action
(for example it is now `RESOLVED`), the dialog closes and the toast says "EXC-1042 is now
Resolved — awaiting verification. No change was made."

---

## 11. Tables

### 11.1 Anatomy

| Part | Spec |
|---|---|
| Container | `Card` with `--radius-lg` and a 1 px `--border`. The table fills the width. The horizontal-scroll container is inside the card. |
| Toolbar (above) | FilterBar: search input (left), filter buttons, active filter chips, "Clear all". Right side: density toggle, result count ("312 exceptions"). |
| Header row | Height 36 px. bg `--surface-subtle`, `text-xs` 500, text `--muted-foreground`, sentence case, bottom border `--border`. **Sticky** (`top: 0` within the scroll container, or below the top bar for page-level scroll), with `--shadow-sticky` once scrolled. |
| Body rows | Height **44 px (comfortable, default)** or **36 px (compact)**. Text `text-body` (comfortable) or `text-sm` (compact). 1 px `--border` divider. Cell padding 12 px horizontal, 16 px for the first and last cell. |
| Footer | Pagination bar (§11.3). |

**Density defaults:** comfortable for the Exceptions inbox, Orders, Products, Imports and Users.
Compact for the Movements ledger, Inventory positions, Import issues and the Audit log. The user's
choice is persisted per table in `localStorage`.

### 11.2 Cell rules

| Content | Alignment | Format |
|---|---|---|
| Text, names, titles | Left | Truncate with an ellipsis at the column max-width, full text in a tooltip and in `title`. Titles may wrap to 2 lines in comfortable density. |
| Money, quantities, scores, counts, percentages | **Right**, header also right-aligned | Tabular, formatted per §13. Negative values use U+2212 and `--tone-danger-fg` where negative means a problem. |
| Dates/times | Left | Table format `Oct 31, 9:42 AM`, zone in the column header ("Placed (ET)"), full timestamp in a tooltip |
| Status / severity / health | Left | Pill (§12). One pill per cell. |
| Priority | Left | `PriorityIndicator` (meter + "P1 · 81") |
| Identifiers | Left | Order number / SKU in 500 weight. Exception reference in mono. |
| Empty value | Same as the column | Em dash "—" in `--muted-foreground`, with `aria-label="None"` |
| Row actions | Right, last column | Max one icon button (`more-horizontal`) opening a menu. No inline destructive buttons. |

**Row navigation.** The primary cell contains a real `<a href>`, stretched over the row with a
pseudo-element (`after:absolute after:inset-0`), so the whole row is clickable. Middle-click and
Cmd/Ctrl-click open a new tab, and screen readers announce one link per row. Never put `onClick`
on `<tr>`. Interactive elements inside the row (menus, checkboxes) sit above the stretched link
(`relative z-[1]`).

**Sorting.** Sortable headers are `<button>`s with an `arrow-up-down` icon (unsorted, shown on
hover/focus), `arrow-up` or `arrow-down` (sorted). The header cell carries
`aria-sort="ascending|descending|none"`. One sort key at a time, written to `?sort=field` /
`?sort=-field`.

### 11.3 Pagination (server-side)

Footer, 48 px: left "1–25 of 312". Right: "Rows per page" select (25 / 50 / 100, max 100 per API),
then "Previous" / "Next" buttons and "Page 2 of 13". State lives in the URL (`page`,
`page_size`). Changing a filter or sort resets `page` to 1. On page change, scroll to the top of the
table and move focus to the table caption (visually hidden `<caption>`: "Exceptions, page 2 of 13,
sorted by priority descending").

While a new page loads, the current rows stay visible at 60% opacity with `aria-busy="true"` on the
table (`placeholderData: keepPreviousData`). A skeleton appears only on first load.

### 11.4 Selection

v1 has no bulk actions (no bulk API, IA-5), so lists have **no row checkboxes**. "Selected" styling
is used only for the current row in master–detail contexts (copilot conversation list, import
issue focused from a link).

### 11.5 Small screens (< 768 px)

Primary lists (Exceptions, Orders, Products, Inventory, Imports) render **stacked rows**:

```text
┌──────────────────────────────────────────────┐
│ ▮▮▮▮ P1 · 81   [■ Critical]        Due in 3h │  ← line 1: priority, severity, due
│ Oversold: Enamel Dutch Oven 5.5 qt, Sage     │  ← line 2: title (2 lines max)
│ KHK-DO55-SGE · 4 orders · $600.00 at risk    │  ← line 3: entity, counts, value (muted)
│ [○ Open]  Unassigned                         │  ← line 4: status, assignee
└──────────────────────────────────────────────┘
```

Ledger-type tables (Movements, Import issues, Audit log, Order line items) keep the table, scroll
horizontally inside the card, and pin the first column (sticky, with a right border while scrolled).

---

## 12. Badges and status pills

**Rule zero: never rely on colour alone.** Every pill has a text label. Status-like pills also
have an icon whose *shape* differs per value, so the value can be told apart in greyscale, by
colour-blind users, and in Windows high-contrast mode (`forced-colors: active`, where the border
remains visible).

| Property | Pill (severity, status, health, order, import) | Count badge | Tag (category, type, role) |
|---|---|---|---|
| Height | 20 px (`sm`) / 24 px (`md`, detail headers) | 18 px | 20 px |
| Padding | 6 px horizontal (8 px for `md`) | 6 px | 6 px |
| Radius | `--radius-sm` | `--radius-full` | `--radius-sm` |
| Text | `text-xs` 500, sentence-case label from `status-maps.ts` | `text-xs` 600, tabular | `text-xs` 500 |
| Icon | 12 px (14 px for `md`), left, `aria-hidden` | none | none |
| Colours | tone fg/bg/border | `--tone-danger-*` in nav, `--tone-neutral-*` elsewhere | `--tone-neutral-*` |

- The accessible name is the label alone (icon is `aria-hidden`). In tables where the column
  header already names the dimension, that is enough. Elsewhere, prefix the name with the
  dimension via visually hidden text: "Severity: Critical".
- Labels come from `status-maps.ts`, never from transforming the enum string at render time.
  Enum strings appear verbatim only in technical contexts (import issue codes, the rule ID,
  audit actions), in mono.
- A pill is never a button. Filtering by a value happens in the FilterBar, not by clicking pills.
- **Estimates** get an inline `EstimateLabel`: "est." in `text-xs` `--muted-foreground` after the
  value, with a tooltip: "Estimate based on the last 28 days of sales. It ignores seasonality and
  promotions (BR-152)." The window comes from `store_settings.velocity_window_days`.
- **Overdue** flag: `alarm-clock` icon + "Overdue 30h" in `--overdue-fg`. No pill, so it does not
  compete with status.

---

## 13. Data formatting

All formatters live in `apps/web/lib/format/` and take the store context (currency, time zone).
Locale is `en-US` in v1. Formatters are pure functions with unit tests.

| Kind | Function | Rule | Examples |
|---|---|---|---|
| Money | `formatMoney(value: string, currency)` | API sends decimals as **strings** (NUMERIC, BR-503). Never `parseFloat` for arithmetic. `Intl.NumberFormat("en-US", {style:"currency", currency, minimumFractionDigits:2})` formats the string directly. Negative uses U+2212. | `$1,234.50` · `$0.00` · `−$12.40` |
| Money, compact | `formatMoneyCompact` | **Only** chart axis ticks. KPI cards and tables always show full values. | `$12.4K` · `$1.2M` |
| Value at risk | `Money` with suffix | Always labelled "at risk" or "value at risk (gross)", never "loss" (BR-404) | `$600.00 at risk` |
| Integer quantity | `formatQuantity(n)` | Thousands separators. Negative with U+2212. | `1,240` · `−4` |
| Signed delta (ledger) | `formatDelta(n)` | Always signed. Zero shows `0`. | `+40` · `−3` · `0` |
| Percentage | `formatPercent(ratio, {digits})` | API sends ratios (0–1). 1 decimal by default, 0 decimals at or above 100. | `94.2%` · `100%` · `0.8%` |
| Percentage-point change | `formatPp` | | `+3.1 pp` · `−0.4 pp` |
| Score | plain integer | The priority score is always shown with its band | `P1 · 81` |
| Date-time, full | `formatDateTime(iso, tz)` | Store time zone, **specific** zone abbreviation (BR-501). Year omitted when it is the current year in the store zone. | `Oct 31, 9:42 AM EDT` · `Nov 2, 8:15 AM EST` · `Dec 30, 2025, 4:05 PM EST` |
| Date-time, table cell | `formatDateTimeShort` | No zone in the cell. The column header carries the **generic** zone via `timeZoneName: "shortGeneric"` ("ET"). The tooltip shows the full format. | `Oct 31, 9:42 AM` |
| Date only | `formatDate` | Store-zone calendar date | `Oct 31, 2026` |
| Relative (past) | `formatRelative(iso, now)` | `< 1 min` "just now" · `< 60 min` "12m ago" · `< 24 h` "5h ago" · `< 7 d` "3d ago" · otherwise the short date. Always wrapped in `<time dateTime="{UTC ISO}">` with the full timestamp in a tooltip. Re-rendered every 60 s, with no animation. | `5h ago` |
| Relative (deadline) | `formatDue(iso, now)` | Future: "Due in 3h 12m" (minutes shown only under 24 h), "Due in 2d 4h". Past: "Overdue 30h" up to 72 h, then "Overdue 4d 6h". | `Due in 3h 12m` |
| Duration | `formatDuration(hours)` | `h` under 72 h, then `d h` | `30h` · `4d 6h` |
| Days of cover | `formatDaysOfCover(value \| null)` | 1 decimal + `days` + "est." label. Null → "Not enough sales history" (BR-151). | `6.5 days est.` |
| Exception reference | none (verbatim) | `operational_exception.reference` from the per-store sequence, shown as-is in Inter 500. The UUID is never shown outside "Technical details". | `EXC-1042` |
| File size | `formatBytes` | Base 1,000, 1 decimal | `1.8 MB` |
| Row counts in prose | `formatQuantity` + noun, pluralised | | `1 row` · `14 rows` |

**Time zone transitions.** The demo store's zone (America/New_York) changes from EDT to EST on
the first Sunday of November. Never hard-code an abbreviation. Always derive it from `Intl` for
each timestamp. Charts with daily buckets use store-local calendar days, and their title says so
("per day, ET").

---

## 14. Forms and validation

| Aspect | Rule |
|---|---|
| Layout | Label above the control. One column. Max form width 560 px (dialogs) or 720 px (settings). Field gap 16 px, section gap 32 px. |
| Label | `text-body-strong`. Required is the default. Optional fields append "(optional)" in `--muted-foreground`. |
| Helper text | `text-xs` 400 `--muted-foreground` below the control, linked with `aria-describedby`. Settings fields reference their rule ("Used by BR-201 ship-by deadline. Default 48."). |
| Validation timing | React Hook Form `mode: "onTouched"`, `reValidateMode: "onChange"`: first validated on blur, then live once an error is shown. Submit validates everything. |
| Field error | Replaces the helper text. `circle-alert` 14 px + message in `--tone-danger-fg`, `text-xs` 500. Control border is `--tone-danger-fg` and has `aria-invalid="true"`. The message says what to do: "Enter at least 10 characters (currently 6)." |
| Form-level error | On submit with errors: focus moves to an `Alert` (danger tone) at the top of the form: "2 fields need attention", with links that focus each field. Server 422 errors map `error.details[].field` to fields. Unmapped details go into the alert. |
| Server errors (non-422) | `Alert` inside the dialog or form, with the error message and `request_id` (mono, with a copy button). The form keeps its values. Retry is the same submit button. |
| Conflict (409) | `STALE_VERSION`: warning toast "Someone else updated {reference}…" plus an automatic refetch. The form values are kept and the next submit sends the new version (§10). Other 409 codes (`EXCEPTION_TRANSITION_NOT_ALLOWED`, `LAST_OWNER`, `IMPORT_*`): an Alert inside the form with the API message, values kept. See SCREEN_SPECIFICATIONS §0.3 "Conflict". |
| Submit button | Disabled (real `disabled`) only while submitting. Before that it is always enabled, so submit can reveal validation errors (never pre-disabled "until valid"). |
| Character limits | Shown as "6 / 4,000" under textareas once 80% is reached, or immediately where a minimum applies ("6 / 10 minimum"). |
| Zod schemas | Live next to the form (`schema.ts`). Min/max values mirror the backend Pydantic constraints. The contracts package is the source of truth for field names. |
| Destructive confirmation | Uses `ConfirmDialog` (AlertDialog). It names the object and the consequence. The confirm button repeats the verb ("Dismiss exception"), never "OK" or "Yes". |

---

## 15. Navigation styles

| Element | Spec |
|---|---|
| Sidebar, expanded (240 px) | bg `--sidebar`, right border `--sidebar-border`. Product mark + store switcher at the top (56 px, aligned with the top bar). Groups: `text-overline` label in `--muted-foreground`, 24 px top margin, 8 px bottom margin. Items: 32 px high, 8 px horizontal padding, 16 px icon, 8 px gap, `text-body-strong` (500). Current item: `--sidebar-active` bg, `--primary` icon, `aria-current="page"`. Count badge right-aligned. Footer: collapse toggle (`panel-left-close`). |
| Sidebar, collapsed (56 px) | Icons only, centred in 40 × 32 px targets. Group labels become 1 px dividers. Every item has a Tooltip (right side, 150 ms delay) with the label, and an `aria-label`. The count badge becomes a 6 px dot at the icon's top-right, with the count kept in the accessible name. The toggle is `panel-left-open`. |
| Mobile drawer (< 768 px) | Radix Dialog as a left Sheet (280 px, max 85vw), with the same content as the expanded sidebar. It opens from the top-bar menu button (`aria-expanded`, `aria-controls`). Focus is trapped. Escape or a scrim tap closes it. **It closes automatically on navigation.** |
| Top bar (56 px) | bg `--card`, bottom border. Left: page breadcrumb (≥ 768) or menu button + store name (< 768). Right: search trigger (input-looking button "Search… ⌘K" ≥ 1024, icon only below), Copilot shortcut (icon `message-square-text`, label "Copilot", shown when `copilot.use`; no sparkle icons anywhere), user menu (avatar initials 28 px). |
| Breadcrumb | `text-sm`. Parent links in `--muted-foreground`, current page in `--foreground` with `aria-current="page"`. `chevron-right` 14 px separators. Max 3 levels. Middle levels collapse to "…" below 1024 px. |
| Tabs (list views, detail sub-sections) | Underline style: 36 px high, `text-body-strong`, `--muted-foreground`. Active: `--foreground` with a 2 px `--primary` bottom border. Counts in a neutral count badge. Radix Tabs for in-page panels. For views that change the URL (`?view=mine`), use links styled as tabs (`aria-current`), not Radix Tabs. |

---

## 16. Charts (Recharts)

Charts appear on Overview and Analytics. A chart earns its place only when the shape over time or
across categories matters. A single number is a `KpiCard`, not a chart.

| Rule | Spec |
|---|---|
| Container | `ChartFrame`: title (`text-title-sm`) stating metric, window and zone ("Orders placed per day, last 30 days (ET)"), optional subtitle, a "Chart / Table" segmented toggle, and the chart at a fixed height (240 px default, 200 px compact). |
| Series colours | Single series: `--chart-1`. Categorical (max 4, fixed order, assigned by entity, never by rank): exception category `INVENTORY` → `--chart-1`, `FULFILLMENT` → `--chart-2`, `PAYMENT` → `--chart-3`, `DATA_QUALITY` → `--chart-4`. Comparison / previous period: `--chart-neutral`. |
| Chart tokens (light) | `--chart-1: #2A78D6` · `--chart-2: #EB6834` · `--chart-3: #1BAF7A` · `--chart-4: #EDA100` · `--chart-neutral: #8A939C` · `--chart-grid: #E9ECEF` · `--chart-axis: #CED4DA` · `--chart-emphasis: #D92D20` |
| Chart tokens (dark) | `#3987E5` · `#D95926` · `#199E70` · `#C98500` · `#6B747E` · grid `#2A3037` · axis `#3F464E` · emphasis `#F04438` |
| Palette validation | The 4-slot categorical set passes CVD separation (worst adjacent ΔE 9.1 light / 8.4 dark) and the normal-vision floor. Slots 3 and 4 fall below 3:1 against white, so every multi-series chart must carry a legend and direct labels or the table view (it always has the table view). |
| Severity in charts | **Not colour-coded.** Red, orange and yellow cannot be separated reliably as adjacent fills (normal-vision ΔE below 15 between HIGH and MEDIUM). Severity breakdowns use position: one labelled bar per severity, in `--chart-1`. Only the CRITICAL bar may use `--chart-emphasis`. |
| Marks | Lines 2 px, round caps, no dots except the hovered point (8 px with a 2 px surface ring). Bars ≤ 24 px thick, 4 px radius on the data end only, square at the baseline, 2 px gap between stacked segments. Area fills are not used. |
| Estimates | Drawn dashed (`strokeDasharray="4 4"`) and labelled "est." in the legend. This is the only dashed line. |
| Axes and grid | Horizontal gridlines only, 1 px `--chart-grid`, solid. X axis baseline `--chart-axis`. Tick text `text-xs` `--muted-foreground`, tabular. Y axis starts at 0 for bars and counts. Compact ticks (`1K`, `$12K`). Max 5 y ticks. One y-axis only (no dual axes). |
| Legend | Present for 2 or more series, above the plot, left-aligned, with 8 px square swatches and text in `--foreground`. Hidden for a single series (the title names it). |
| Tooltip | `--popover` surface, `--shadow-popover`, `text-xs`. Header: the bucket's date in store time. Rows: swatch, series label, value formatted with §13. Line charts use a crosshair cursor (1 px `--chart-axis`). Bars highlight the hovered bar's band with `--surface-hover`. |
| Interaction | Hover/tooltip only. No zoom, brush or animated transitions. `isAnimationActive={false}` everywhere. |
| Accessibility | The chart `<svg>` has `role="img"` and an `aria-label` summarising the data ("Orders per day, Oct 2 to Oct 31: min 14, max 41, latest 27"). The Table view renders the same data as a real `<table>` and is the keyboard-accessible path. |
| Empty / partial data | Empty: an EmptyState inside the frame ("No orders placed in this period"). Partial days (today) are flagged in the tooltip as "Partial day (until 9:42 AM EDT)". |
| Loading / error | Skeleton block of the chart height. ErrorState (compact) with Retry inside the frame. |

---

## 17. Iconography

Lucide (`lucide-react`). Sizes: 16 px default (buttons, nav, inline), 12 px in `sm` pills, 14 px
in `md` pills and field errors, 20 px in page-level alerts, 24 px in empty states (inside a 40 px
`--muted` circle). Stroke width 2. Icons next to text are `aria-hidden`. Icon-only buttons have an
`aria-label` and a tooltip. The icons for statuses, severities and health values are fixed in §3.5
and must not be reused for unrelated meanings on the same screen.

---

## 18. Voice and labels

| Do | Don't |
|---|---|
| "Value at risk (gross)", "$600.00 at risk" | "Loss", "Revenue lost" (BR-404) |
| "6.5 days of cover (est.)" | "Runs out Nov 6" stated as fact |
| "Resolve", "Dismiss", "Reopen", "Start work", "Acknowledge" | "Close", "Delete", "Archive" for exceptions |
| "Exception" | "Alert", "Incident", "Ticket" |
| "Run analysis" (manual evaluation) | "Refresh", "Sync" |
| "The public demo is read-only." | "Access denied!" |
| "Apply 1,226 valid rows and skip 14" | "Continue" |
| "Generated by the deterministic engine" / "Generated by LLM provider ({model})" | "AI magic", sparkle icons |

---

## 19. Tailwind theme mapping

Tailwind CSS v4 (CSS-first configuration, which current shadcn/ui targets). Tokens stay in
`tokens.css`, and `globals.css` exposes them to utilities with `@theme inline`.

```css
/* apps/web/app/globals.css */
@import "tailwindcss";
@import "../styles/tokens.css";

@custom-variant dark (&:where(.dark, .dark *));

@theme inline {
  --font-sans: var(--font-sans);
  --font-mono: var(--font-mono);

  /* surfaces & text */
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-card: var(--card);
  --color-card-foreground: var(--card-foreground);
  --color-popover: var(--popover);
  --color-popover-foreground: var(--popover-foreground);
  --color-muted: var(--muted);
  --color-muted-foreground: var(--muted-foreground);
  --color-accent: var(--accent);
  --color-accent-foreground: var(--accent-foreground);
  --color-secondary: var(--secondary);
  --color-secondary-foreground: var(--secondary-foreground);
  --color-primary: var(--primary);
  --color-primary-foreground: var(--primary-foreground);
  --color-primary-hover: var(--primary-hover);
  --color-primary-active: var(--primary-active);
  --color-destructive: var(--destructive);
  --color-destructive-foreground: var(--destructive-foreground);
  --color-destructive-hover: var(--destructive-hover);
  --color-border: var(--border);
  --color-border-strong: var(--border-strong);
  --color-input: var(--input);
  --color-input-hover: var(--input-hover);
  --color-ring: var(--ring);
  --color-text-secondary: var(--text-secondary);
  --color-text-placeholder: var(--text-placeholder);
  --color-text-disabled: var(--text-disabled);
  --color-link: var(--text-link);
  --color-surface-subtle: var(--surface-subtle);
  --color-surface-hover: var(--surface-hover);
  --color-surface-selected: var(--surface-selected);
  --color-surface-disabled: var(--surface-disabled);
  --color-sidebar: var(--sidebar);
  --color-sidebar-foreground: var(--sidebar-foreground);
  --color-sidebar-active: var(--sidebar-active);
  --color-sidebar-active-foreground: var(--sidebar-active-foreground);
  --color-sidebar-border: var(--sidebar-border);
  --color-overlay: var(--overlay);
  --color-demo-banner: var(--demo-banner);
  --color-demo-banner-foreground: var(--demo-banner-foreground);

  /* tones (repeat for neutral, outline, muted, primary, info, success, warning, caution, attention, danger, danger-solid) */
  --color-tone-danger-fg: var(--tone-danger-fg);
  --color-tone-danger-bg: var(--tone-danger-bg);
  --color-tone-danger-border: var(--tone-danger-border);
  /* … */

  /* domain */
  --color-priority-p1: var(--priority-p1-fg);   --color-priority-p1-bar: var(--priority-p1-bar);
  --color-priority-p2: var(--priority-p2-fg);   --color-priority-p2-bar: var(--priority-p2-bar);
  --color-priority-p3: var(--priority-p3-fg);   --color-priority-p3-bar: var(--priority-p3-bar);
  --color-priority-p4: var(--priority-p4-fg);   --color-priority-p4-bar: var(--priority-p4-bar);
  --color-priority-bar-empty: var(--priority-bar-empty);
  --color-overdue: var(--overdue-fg);
  --color-mark-danger: var(--mark-danger);
  --color-chart-1: var(--chart-1);  --color-chart-2: var(--chart-2);
  --color-chart-3: var(--chart-3);  --color-chart-4: var(--chart-4);
  --color-chart-neutral: var(--chart-neutral); --color-chart-grid: var(--chart-grid);
  --color-chart-axis: var(--chart-axis); --color-chart-emphasis: var(--chart-emphasis);

  /* radius */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;

  /* type scale */
  --text-display: 1.75rem;   --text-display--line-height: 2.125rem; --text-display--font-weight: 600; --text-display--letter-spacing: -0.015em;
  --text-title-lg: 1.25rem;  --text-title-lg--line-height: 1.75rem; --text-title-lg--font-weight: 600; --text-title-lg--letter-spacing: -0.01em;
  --text-title: 1rem;        --text-title--line-height: 1.5rem;     --text-title--font-weight: 600; --text-title--letter-spacing: -0.005em;
  --text-title-sm: 0.875rem; --text-title-sm--line-height: 1.25rem; --text-title-sm--font-weight: 600;
  --text-body: 0.875rem;     --text-body--line-height: 1.25rem;
  --text-body-strong: 0.875rem; --text-body-strong--line-height: 1.25rem; --text-body-strong--font-weight: 500;
  --text-sm: 0.8125rem;      --text-sm--line-height: 1.125rem;
  --text-xs: 0.75rem;        --text-xs--line-height: 1rem;          --text-xs--font-weight: 500; --text-xs--letter-spacing: 0.005em;
  --text-overline: 0.6875rem;--text-overline--line-height: 1rem;    --text-overline--font-weight: 600; --text-overline--letter-spacing: 0.06em;
  --text-prose: 0.875rem;    --text-prose--line-height: 1.375rem;

  /* shadows, motion */
  --shadow-popover: 0 4px 12px -2px rgb(16 24 40 / 0.10), 0 2px 4px -2px rgb(16 24 40 / 0.06);
  --shadow-dialog: 0 16px 32px -8px rgb(16 24 40 / 0.18), 0 4px 8px -4px rgb(16 24 40 / 0.08);
  --ease-standard: cubic-bezier(0.2, 0, 0, 1);
  --ease-exit: cubic-bezier(0.4, 0, 1, 1);
}
```

Resulting utilities (examples): `bg-background`, `text-muted-foreground`, `border-input`,
`bg-tone-danger-bg text-tone-danger-fg border-tone-danger-border`, `bg-priority-p1-bar`,
`text-overdue`, `text-title-lg`, `text-xs`, `rounded-sm`, `shadow-popover`,
`ease-standard duration-150`. Chart components read colours through `var(--chart-1)` in Recharts
`stroke`/`fill` props, never as hex.

**Tailwind v3 fallback** (only if the scaffold pins v3): map the same names under
`theme.extend.colors` as `"tone-danger-fg": "var(--tone-danger-fg)"`, and so on, and the type scale
under `theme.extend.fontSize` as `["0.875rem", { lineHeight: "1.25rem", fontWeight: "500" }]`.
Opacity modifiers (`bg-primary/50`) are not used in this system, so hex variables are enough.

Lint rule: `eslint-plugin-tailwindcss` `no-arbitrary-value` for colour utilities (`bg-[#…]`
fails CI).

---

## 20. Contrast table (WCAG 2.1 AA)

Computed with the WCAG relative-luminance formula. Text needs 4.5:1. UI component boundaries and
the focus indicator need 3:1 (SC 1.4.11).

| Pair | Foreground | Background | Ratio | Requirement | Result |
|---|---|---|---|---|---|
| Body text on card | `#1A1E23` | `#FFFFFF` | 16.75 | 4.5 | Pass |
| Body text on canvas | `#1A1E23` | `#F8F9FA` | 15.89 | 4.5 | Pass |
| Secondary text on card | `#3F464E` | `#FFFFFF` | 9.56 | 4.5 | Pass |
| Muted text on card | `#555D66` | `#FFFFFF` | 6.68 | 4.5 | Pass |
| Muted text on canvas / table header | `#555D66` | `#F8F9FA` | 6.34 | 4.5 | Pass |
| Muted text on selected row | `#555D66` | `#EEF0FC` | 5.89 | 4.5 | Pass |
| Sidebar current item text | `#1A1E23` | `#E9ECEF` | 14.12 | 4.5 | Pass |
| Placeholder on input | `#6C757D` | `#FFFFFF` | 4.69 | 4.5 | Pass |
| Link on card | `#3B4CCA` | `#FFFFFF` | 6.83 | 4.5 | Pass |
| Primary button label | `#FFFFFF` | `#3B4CCA` | 6.83 | 4.5 | Pass |
| Destructive button label | `#FFFFFF` | `#B42318` | 6.57 | 4.5 | Pass |
| In-progress pill | `#3140A8` | `#EEF0FC` | 7.62 | 4.5 | Pass |
| Success pill | `#067647` | `#ECFDF3` | 5.40 | 4.5 | Pass |
| Warning pill | `#B54708` | `#FFFAEB` | 5.20 | 4.5 | Pass |
| Danger pill | `#B42318` | `#FEF3F2` | 6.05 | 4.5 | Pass |
| Info pill | `#175CD3` | `#EFF8FF` | 5.57 | 4.5 | Pass |
| Severity Critical (solid) | `#FFFFFF` | `#B42318` | 6.57 | 4.5 | Pass |
| Severity High | `#B93815` | `#FEF6EE` | 5.39 | 4.5 | Pass |
| Severity Medium | `#A15C07` | `#FEFBE8` | 4.98 | 4.5 | Pass |
| Severity Low | `#3F464E` | `#F1F3F5` | 8.59 | 4.5 | Pass |
| Status Open (outline) | `#2A3037` | `#FFFFFF` | 13.32 | 4.5 | Pass |
| Status Dismissed | `#555D66` | `#F1F3F5` | 6.01 | 4.5 | Pass |
| Demo banner | `#FFFFFF` | `#1A1E23` | 16.75 | 4.5 | Pass |
| Input border | `#8A939C` | `#FFFFFF` | 3.12 | 3.0 | Pass |
| Focus ring on card | `#3B4CCA` | `#FFFFFF` | 6.83 | 3.0 | Pass |
| Focus ring on canvas | `#3B4CCA` | `#F8F9FA` | 6.48 | 3.0 | Pass |
| P1 meter bar | `#D92D20` | `#FFFFFF` | 4.83 | 3.0 | Pass |
| P2 meter bar | `#E04F16` | `#FFFFFF` | 3.96 | 3.0 | Pass |
| *Dark:* body on card | `#ECEEF0` | `#15191D` | 15.19 | 4.5 | Pass |
| *Dark:* muted on card | `#9AA3AC` | `#15191D` | 6.91 | 4.5 | Pass |
| *Dark:* primary button label | `#FFFFFF` | `#4A5BD6` | 5.59 | 4.5 | Pass |
| *Dark:* danger pill | `#F97066` | `#2F1211` | 6.20 | 4.5 | Pass |
| *Dark:* severity Critical | `#FFFFFF` | `#C9281C` | 5.52 | 4.5 | Pass |
| *Dark:* input border | `#6B747E` | `#15191D` | 3.72 | 3.0 | Pass |
| *Dark:* focus ring | `#9AA6EC` | `#15191D` | 7.60 | 3.0 | Pass |

Known non-text exceptions: the `--border` (`#DEE2E6`, 1.30:1) card and table dividers are
decorative and do not identify a component. Empty priority meter segments (`--priority-bar-empty`)
are supplemental, because the "P1 · 81" text carries the value. Disabled controls are exempt
(SC 1.4.3), but they still carry a reason tooltip.
