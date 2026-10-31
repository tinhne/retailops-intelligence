// AUTO-GENERATED from apps/api OpenAPI schema by packages/contracts/scripts/generate.mjs.
// Do not edit by hand. Run `pnpm contracts:generate` after changing API schemas.

export interface paths {
    "/api/v1/auth/demo": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Demo Login
         * @description Sign in as the read-only public demo viewer (ADR-0011).
         */
        post: operations["demo_login_api_v1_auth_demo_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Login */
        post: operations["login_api_v1_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Logout */
        post: operations["logout_api_v1_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Me */
        get: operations["me_api_v1_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/health/live": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Live */
        get: operations["live_api_v1_health_live_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/health/ready": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Ready */
        get: operations["ready_api_v1_health_ready_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/roles": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Roles
         * @description The code-defined role → permission matrix (ADR-0007), for read-only display in the UI.
         */
        get: operations["list_roles_api_v1_roles_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Store
         * @description Store details, operational settings and data freshness (latest import per type and the
         *     latest evaluation run).
         */
        get: operations["get_store_api_v1_stores__store_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/analytics/dashboard": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Dashboard */
        get: operations["get_dashboard_api_v1_stores__store_id__analytics_dashboard_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/analytics/exceptions-breakdown": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Exception Breakdown */
        get: operations["get_exception_breakdown_api_v1_stores__store_id__analytics_exceptions_breakdown_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/analytics/trends": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Trends */
        get: operations["get_trends_api_v1_stores__store_id__analytics_trends_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/audit-logs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Audit Logs */
        get: operations["list_audit_logs_api_v1_stores__store_id__audit_logs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/categories": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Categories */
        get: operations["list_categories_api_v1_stores__store_id__categories_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/evaluations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Evaluations */
        get: operations["list_evaluations_api_v1_stores__store_id__evaluations_get"];
        put?: never;
        /**
         * Trigger Evaluation
         * @description Manual "Run analysis". 201 with the new run; 200 with the SKIPPED run while another
         *     evaluation holds the store lock; 200 with the original run on an Idempotency-Key replay.
         */
        post: operations["trigger_evaluation_api_v1_stores__store_id__evaluations_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/evaluations/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Evaluation */
        get: operations["get_evaluation_api_v1_stores__store_id__evaluations__run_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/exceptions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Exceptions */
        get: operations["list_exceptions_api_v1_stores__store_id__exceptions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/exceptions/{exception_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Exception */
        get: operations["get_exception_api_v1_stores__store_id__exceptions__exception_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/exceptions/{exception_id}/acknowledge": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Acknowledge Exception */
        post: operations["acknowledge_exception_api_v1_stores__store_id__exceptions__exception_id__acknowledge_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/exceptions/{exception_id}/assign": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Assign Exception
         * @description Assign, reassign or unassign (exceptions.assign). Users with only exceptions.work may
         *     claim an unassigned exception by passing their own id.
         */
        post: operations["assign_exception_api_v1_stores__store_id__exceptions__exception_id__assign_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/exceptions/{exception_id}/dismiss": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Dismiss Exception */
        post: operations["dismiss_exception_api_v1_stores__store_id__exceptions__exception_id__dismiss_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/exceptions/{exception_id}/due-date": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Set Exception Due Date */
        patch: operations["set_exception_due_date_api_v1_stores__store_id__exceptions__exception_id__due_date_patch"];
        trace?: never;
    };
    "/api/v1/stores/{store_id}/exceptions/{exception_id}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Exception Events */
        get: operations["list_exception_events_api_v1_stores__store_id__exceptions__exception_id__events_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/exceptions/{exception_id}/notes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Exception Notes */
        get: operations["list_exception_notes_api_v1_stores__store_id__exceptions__exception_id__notes_get"];
        put?: never;
        /** Add Exception Note */
        post: operations["add_exception_note_api_v1_stores__store_id__exceptions__exception_id__notes_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/exceptions/{exception_id}/reopen": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reopen Exception */
        post: operations["reopen_exception_api_v1_stores__store_id__exceptions__exception_id__reopen_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/exceptions/{exception_id}/resolve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Resolve Exception */
        post: operations["resolve_exception_api_v1_stores__store_id__exceptions__exception_id__resolve_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/exceptions/{exception_id}/start": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start Exception */
        post: operations["start_exception_api_v1_stores__store_id__exceptions__exception_id__start_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/imports": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Imports */
        get: operations["list_imports_api_v1_stores__store_id__imports_get"];
        put?: never;
        /**
         * Create Import
         * @description Upload a CSV and validate it. A file-level failure is still 201, with status REJECTED.
         */
        post: operations["create_import_api_v1_stores__store_id__imports_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/imports/templates/{import_type}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Download Template */
        get: operations["download_template_api_v1_stores__store_id__imports_templates__import_type__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/imports/{import_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Import */
        get: operations["get_import_api_v1_stores__store_id__imports__import_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/imports/{import_id}/apply": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Apply Import
         * @description Apply atomically (BR-606), then run the IMPORT-triggered exception evaluation.
         */
        post: operations["apply_import_api_v1_stores__store_id__imports__import_id__apply_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/imports/{import_id}/discard": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Discard Import */
        post: operations["discard_import_api_v1_stores__store_id__imports__import_id__discard_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/imports/{import_id}/issues": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Issues */
        get: operations["list_issues_api_v1_stores__store_id__imports__import_id__issues_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/imports/{import_id}/issues.csv": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Download Issues */
        get: operations["download_issues_api_v1_stores__store_id__imports__import_id__issues_csv_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/inventory/movements": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Movements */
        get: operations["list_movements_api_v1_stores__store_id__inventory_movements_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/inventory/positions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Positions */
        get: operations["list_positions_api_v1_stores__store_id__inventory_positions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/inventory/reconciliation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Reconciliation */
        get: operations["get_reconciliation_api_v1_stores__store_id__inventory_reconciliation_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/members": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Members
         * @description Organization members for the assignee picker: name, role and whether they can work
         *     exceptions. Emails are not exposed.
         */
        get: operations["list_members_api_v1_stores__store_id__members_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/orders": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Orders */
        get: operations["list_orders_api_v1_stores__store_id__orders_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/orders/{order_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Order */
        get: operations["get_order_api_v1_stores__store_id__orders__order_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/products": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Products */
        get: operations["list_products_api_v1_stores__store_id__products_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/products/{product_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Product */
        get: operations["get_product_api_v1_stores__store_id__products__product_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stores/{store_id}/settings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Settings */
        get: operations["get_settings_api_v1_stores__store_id__settings_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Settings
         * @description Partial update of the thresholds in BUSINESS_RULES.md §7, audited as ``settings.update``.
         */
        patch: operations["update_settings_api_v1_stores__store_id__settings_patch"];
        trace?: never;
    };
    "/api/v1/stores/{store_id}/suppliers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Suppliers */
        get: operations["list_suppliers_api_v1_stores__store_id__suppliers_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** ActiveExceptionSummary */
        ActiveExceptionSummary: {
            /** By Band */
            by_band: {
                [key: string]: number;
            };
            /** By Category */
            by_category: {
                [key: string]: number;
            };
            /** By Severity */
            by_severity: {
                [key: string]: number;
            };
            /**
             * Exposure By Category
             * @description Σ exposure_amount of active exceptions per category: gross order-line value at risk (BR-404), not loss. Not additive across categories, because one order can count in several exceptions, so no total is provided.
             */
            exposure_by_category: {
                [key: string]: string;
            };
            /**
             * Past Due
             * @description Active exceptions with due_at < as_of.
             */
            past_due: number;
            /**
             * Reopened
             * @description Active exceptions currently in REOPENED.
             */
            reopened: number;
            /** Total */
            total: number;
            /** Unassigned */
            unassigned: number;
        };
        /**
         * ActorType
         * @enum {string}
         */
        ActorType: "USER" | "SYSTEM";
        /** AppliedCounts */
        AppliedCounts: {
            /** Creates */
            creates: number;
            mode: components["schemas"]["ImportMode"];
            /** Skipped */
            skipped: number;
            /** Unchanged */
            unchanged: number;
            /** Updates */
            updates: number;
        };
        /** ApplyImportRequest */
        ApplyImportRequest: {
            /** Confirm Skipped Rows */
            confirm_skipped_rows?: number | null;
            /** @default STRICT */
            mode: components["schemas"]["ImportMode"];
        };
        /** AssignRequest */
        AssignRequest: {
            /**
             * Assignee Id
             * @description null unassigns
             */
            assignee_id: string | null;
            /**
             * Expected Version
             * @description Optimistic concurrency: 409 STALE_VERSION on mismatch
             */
            expected_version?: number | null;
        };
        /** AttentionItem */
        AttentionItem: {
            /** Assignee Id */
            assignee_id: string | null;
            /** Assignee Name */
            assignee_name: string | null;
            category: components["schemas"]["ExceptionCategory"];
            /**
             * Due At
             * Format: date-time
             */
            due_at: string;
            exception_type: components["schemas"]["ExceptionType"];
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Is Past Due */
            is_past_due: boolean;
            priority_band: components["schemas"]["PriorityBand"];
            /** Priority Score */
            priority_score: number;
            /** Reference */
            reference: string;
            severity: components["schemas"]["Severity"];
            status: components["schemas"]["ExceptionStatus"];
            /** Title */
            title: string;
        };
        /** AuditLogOut */
        AuditLogOut: {
            /** Action */
            action: string;
            /** Actor User Id */
            actor_user_id: string | null;
            /** Details */
            details: {
                [key: string]: unknown;
            };
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Occurred At
             * Format: date-time
             */
            occurred_at: string;
            /** Request Id */
            request_id: string | null;
            /** Store Id */
            store_id: string | null;
            /** Target Id */
            target_id: string | null;
            /** Target Type */
            target_type: string | null;
        };
        /** BlockedActionOut */
        BlockedActionOut: {
            action: components["schemas"]["ExceptionAction"];
            /** Code */
            code: string;
            /** Reason */
            reason: string;
        };
        /** Body_create_import_api_v1_stores__store_id__imports_post */
        Body_create_import_api_v1_stores__store_id__imports_post: {
            /** File */
            file: string;
            import_type: components["schemas"]["ImportType"];
        };
        /** CategoryList */
        CategoryList: {
            /** Items */
            items: string[];
        };
        /**
         * ChangeSource
         * @enum {string}
         */
        ChangeSource: "IMPORT" | "USER" | "SYSTEM";
        /** DashboardOut */
        DashboardOut: {
            active_exceptions: components["schemas"]["ActiveExceptionSummary"];
            /**
             * As Of
             * Format: date-time
             */
            as_of: string;
            /**
             * Attention
             * @description Top 8 active exceptions by priority.
             */
            attention: components["schemas"]["AttentionItem"][];
            /** Currency */
            currency: string;
            data_freshness: components["schemas"]["DataFreshness"];
            inventory: components["schemas"]["InventoryHealthSummary"];
            on_time_shipment_30_days: components["schemas"]["OnTimeShipment"];
            orders: components["schemas"]["OrderHealthSummary"];
            sales_last_7_days: components["schemas"]["SalesSummary"];
            sales_today: components["schemas"]["SalesSummary"];
            /** Timezone */
            timezone: string;
        };
        /** DataFreshness */
        DataFreshness: {
            /**
             * Imports
             * @description One entry per import type.
             */
            imports: components["schemas"]["ImportFreshness"][];
            /** @description The most recently started evaluation run, whatever its status. */
            last_evaluation_run: components["schemas"]["EvaluationRunFreshness"] | null;
        };
        /** DeadlineWeights */
        DeadlineWeights: {
            /** Overdue */
            overdue: number;
            /** Within 24H */
            within_24h: number;
            /** Within 72H */
            within_72h: number;
        };
        /** DismissRequest */
        DismissRequest: {
            dismissal_reason: components["schemas"]["DismissalReason"];
            /**
             * Expected Version
             * @description Optimistic concurrency: 409 STALE_VERSION on mismatch
             */
            expected_version?: number | null;
            /** Note */
            note: string;
        };
        /** DismissalOut */
        DismissalOut: {
            /** Condition Cleared At */
            condition_cleared_at: string | null;
            /** Dismissed At */
            dismissed_at: string | null;
            dismissed_by: components["schemas"]["UserRef"] | null;
            dismissed_reason: components["schemas"]["DismissalReason"] | null;
            /** Note */
            note: string | null;
        };
        /**
         * DismissalReason
         * @enum {string}
         */
        DismissalReason: "FALSE_POSITIVE" | "ACCEPTED_RISK" | "DUPLICATE" | "NOT_ACTIONABLE";
        /** DriftOut */
        DriftOut: {
            /** Computed */
            computed: number;
            /** Field */
            field: string;
            /**
             * Product Id
             * Format: uuid
             */
            product_id: string;
            /** Sku */
            sku: string | null;
            /** Stored */
            stored: number;
        };
        /** DueDateRequest */
        DueDateRequest: {
            /**
             * Due At
             * Format: date-time
             */
            due_at: string;
            /**
             * Expected Version
             * @description Optimistic concurrency: 409 STALE_VERSION on mismatch
             */
            expected_version?: number | null;
            /** Note */
            note?: string | null;
        };
        /** EntityLinkOut */
        EntityLinkOut: {
            /**
             * Entity Id
             * Format: uuid
             */
            entity_id: string;
            entity_type: components["schemas"]["EntityType"];
            /** Label */
            label: string;
            /** Name */
            name?: string | null;
            role: components["schemas"]["LinkRole"];
        };
        /** EntityRefOut */
        EntityRefOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Label */
            label: string;
            /** Name */
            name?: string | null;
            type: components["schemas"]["EntityType"];
        };
        /**
         * EntityType
         * @enum {string}
         */
        EntityType: "product" | "order";
        /**
         * Estimate
         * @description A value that is an estimate, never a fact (BR-152). The UI and AI must label it so.
         */
        Estimate: {
            /** Basis */
            basis: string;
            /**
             * Is Estimate
             * @default true
             * @constant
             */
            is_estimate: true;
            /** Note */
            note?: string | null;
            /** Value */
            value: string | null;
            /** Window Days */
            window_days: number;
        };
        /** EvaluationCreate */
        EvaluationCreate: {
            /**
             * Rule Ids
             * @description Rule ids such as INV-OVERSOLD@1; all if omitted
             */
            rule_ids?: string[] | null;
        };
        /** EvaluationRunFreshness */
        EvaluationRunFreshness: {
            /**
             * As Of
             * Format: date-time
             */
            as_of: string;
            /** Finished At */
            finished_at: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Started At
             * Format: date-time
             */
            started_at: string;
            status: components["schemas"]["EvaluationStatus"];
            trigger: components["schemas"]["EvaluationTrigger"];
        };
        /** EvaluationRunOut */
        EvaluationRunOut: {
            /**
             * As Of
             * Format: date-time
             */
            as_of: string;
            /** Counts */
            counts: {
                [key: string]: number;
            };
            /** Duration Ms */
            duration_ms: number | null;
            /** Error */
            error: string | null;
            /** Finished At */
            finished_at: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Import Id */
            import_id: string | null;
            /** Rules */
            rules: string[];
            /**
             * Started At
             * Format: date-time
             */
            started_at: string;
            status: components["schemas"]["EvaluationStatus"];
            trigger: components["schemas"]["EvaluationTrigger"];
            triggered_by: components["schemas"]["UserRef"] | null;
        };
        /**
         * EvaluationStatus
         * @enum {string}
         */
        EvaluationStatus: "RUNNING" | "SUCCEEDED" | "FAILED" | "SKIPPED";
        /**
         * EvaluationTrigger
         * @enum {string}
         */
        EvaluationTrigger: "MANUAL" | "IMPORT" | "SCHEDULED";
        /**
         * ExceptionAction
         * @enum {string}
         */
        ExceptionAction: "acknowledge" | "start" | "resolve" | "dismiss" | "reopen" | "assign" | "claim" | "add_note" | "set_due_date";
        /** ExceptionBreakdownOut */
        ExceptionBreakdownOut: {
            /**
             * As Of
             * Format: date-time
             */
            as_of: string;
            /** Items */
            items: components["schemas"]["ExceptionTypeBreakdown"][];
            window: components["schemas"]["TimeWindow"];
        };
        /**
         * ExceptionCategory
         * @enum {string}
         */
        ExceptionCategory: "INVENTORY" | "FULFILLMENT" | "PAYMENT" | "DATA_QUALITY";
        /** ExceptionDetail */
        ExceptionDetail: {
            /** Affected Order Count */
            affected_order_count: number;
            /** Age Hours */
            age_hours: number;
            assignee: components["schemas"]["UserRef"] | null;
            /** Available Actions */
            available_actions: components["schemas"]["ExceptionAction"][];
            /** Blocked Actions */
            blocked_actions: components["schemas"]["BlockedActionOut"][];
            /** Calculation */
            calculation: {
                [key: string]: unknown;
            };
            category: components["schemas"]["ExceptionCategory"];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Deadline At */
            deadline_at: string | null;
            /** Dedup Key */
            dedup_key: string;
            /** Detection Count */
            detection_count: number;
            dismissal: components["schemas"]["DismissalOut"] | null;
            /**
             * Due At
             * Format: date-time
             */
            due_at: string;
            /** Due At Overridden */
            due_at_overridden: boolean;
            /** Evidence */
            evidence: {
                [key: string]: unknown;
            };
            exception_type: components["schemas"]["ExceptionType"];
            /**
             * Exposure Amount
             * @description Gross order-line value at risk (BR-404)
             */
            exposure_amount: string;
            /**
             * First Detected At
             * Format: date-time
             */
            first_detected_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Is Past Due */
            is_past_due: boolean;
            /**
             * Last Detected At
             * Format: date-time
             */
            last_detected_at: string;
            /** Links */
            links: components["schemas"]["EntityLinkOut"][];
            previous_occurrence: components["schemas"]["ExceptionRef"] | null;
            primary_entity: components["schemas"]["EntityRefOut"];
            priority_band: components["schemas"]["PriorityBand"];
            /** Priority Breakdown */
            priority_breakdown: {
                [key: string]: unknown;
            };
            /** Priority Score */
            priority_score: number;
            /** Recommended Action */
            recommended_action: string;
            /** Reference */
            reference: string;
            /** Reopen Count */
            reopen_count: number;
            resolution: components["schemas"]["ResolutionOut"] | null;
            /** Rule Id */
            rule_id: string;
            severity: components["schemas"]["Severity"];
            status: components["schemas"]["ExceptionStatus"];
            superseded_by: components["schemas"]["ExceptionRef"] | null;
            /** Supersedes */
            supersedes: components["schemas"]["ExceptionRef"][];
            /** Title */
            title: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Version */
            version: number;
        };
        /** ExceptionEventOut */
        ExceptionEventOut: {
            actor: components["schemas"]["UserRef"] | null;
            actor_type: components["schemas"]["ActorType"];
            /** Evaluation Run Id */
            evaluation_run_id: string | null;
            event_type: components["schemas"]["ExceptionEventType"];
            from_status: components["schemas"]["ExceptionStatus"] | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Occurred At
             * Format: date-time
             */
            occurred_at: string;
            /** Payload */
            payload: {
                [key: string]: unknown;
            };
            to_status: components["schemas"]["ExceptionStatus"] | null;
        };
        /**
         * ExceptionEventType
         * @enum {string}
         */
        ExceptionEventType: "DETECTED" | "EVIDENCE_UPDATED" | "SEVERITY_CHANGED" | "STATUS_CHANGED" | "ASSIGNED" | "UNASSIGNED" | "NOTE_ADDED" | "DUE_DATE_CHANGED" | "AUTO_RESOLVED" | "VERIFIED" | "REOPENED" | "SUPERSEDED";
        /** ExceptionListItem */
        ExceptionListItem: {
            /** Affected Order Count */
            affected_order_count: number;
            /** Age Hours */
            age_hours: number;
            assignee: components["schemas"]["UserRef"] | null;
            category: components["schemas"]["ExceptionCategory"];
            /** Deadline At */
            deadline_at: string | null;
            /** Detection Count */
            detection_count: number;
            /**
             * Due At
             * Format: date-time
             */
            due_at: string;
            /** Due At Overridden */
            due_at_overridden: boolean;
            exception_type: components["schemas"]["ExceptionType"];
            /**
             * Exposure Amount
             * @description Gross order-line value at risk (BR-404)
             */
            exposure_amount: string;
            /**
             * First Detected At
             * Format: date-time
             */
            first_detected_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Is Past Due */
            is_past_due: boolean;
            /**
             * Last Detected At
             * Format: date-time
             */
            last_detected_at: string;
            primary_entity: components["schemas"]["EntityRefOut"];
            priority_band: components["schemas"]["PriorityBand"];
            /** Priority Score */
            priority_score: number;
            /** Reference */
            reference: string;
            /** Reopen Count */
            reopen_count: number;
            severity: components["schemas"]["Severity"];
            status: components["schemas"]["ExceptionStatus"];
            /** Title */
            title: string;
            /** Version */
            version: number;
        };
        /** ExceptionNoteOut */
        ExceptionNoteOut: {
            author: components["schemas"]["UserRef"] | null;
            /** Body */
            body: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            source: components["schemas"]["NoteSource"];
        };
        /** ExceptionRef */
        ExceptionRef: {
            exception_type: components["schemas"]["ExceptionType"];
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Reference */
            reference: string;
            status: components["schemas"]["ExceptionStatus"];
            /** Title */
            title: string;
        };
        /**
         * ExceptionStatus
         * @enum {string}
         */
        ExceptionStatus: "OPEN" | "ACKNOWLEDGED" | "IN_PROGRESS" | "REOPENED" | "RESOLVED" | "DISMISSED";
        /**
         * ExceptionType
         * @enum {string}
         */
        ExceptionType: "INVENTORY_OVERSOLD" | "INVENTORY_OVERSELL_RISK" | "INVENTORY_OUT_OF_STOCK" | "INVENTORY_BELOW_REORDER_POINT" | "ORDER_FULFILLMENT_OVERDUE" | "ORDER_STALLED_AFTER_PAYMENT" | "ORDER_REFUND_PENDING" | "DATA_ORDER_TOTAL_MISMATCH" | "DATA_NEGATIVE_ON_HAND";
        /** ExceptionTypeBreakdown */
        ExceptionTypeBreakdown: {
            /**
             * Active
             * @description Active right now (snapshot, not windowed).
             */
            active: number;
            /** Auto Resolved */
            auto_resolved: number;
            category: components["schemas"]["ExceptionCategory"];
            /** Detected In Window */
            detected_in_window: number;
            exception_type: components["schemas"]["ExceptionType"];
            /**
             * Median Hours To Resolve Auto
             * @description Median of resolved_at − first_detected_at, CONDITION_CLEARED (M-10).
             */
            median_hours_to_resolve_auto: string | null;
            /**
             * Median Hours To Resolve Manual
             * @description Median of resolved_at − first_detected_at, manual resolution codes (M-10).
             */
            median_hours_to_resolve_manual: string | null;
            /**
             * Reopened In Window
             * @description REOPENED events in the window.
             */
            reopened_in_window: number;
            /**
             * Resolved In Window
             * @description Manual + automatic; SUPERSEDED excluded.
             */
            resolved_in_window: number;
            /** Resolved Manually */
            resolved_manually: number;
            /** Superseded In Window */
            superseded_in_window: number;
        };
        /**
         * FulfillmentStatus
         * @enum {string}
         */
        FulfillmentStatus: "UNFULFILLED" | "IN_PROGRESS" | "SHIPPED" | "DELIVERED" | "RETURNED";
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /**
         * ImportDetailOut
         * @description An import plus its file-level issues (row_number NULL): why it was rejected, warnings.
         */
        ImportDetailOut: {
            /** Applied At */
            applied_at: string | null;
            /** Applied By */
            applied_by: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Created By */
            created_by: string | null;
            /** Evaluation Run Id */
            evaluation_run_id: string | null;
            /** Expires At */
            expires_at: string | null;
            /** Failure Reason */
            failure_reason: string | null;
            /** File Issues */
            file_issues: components["schemas"]["ImportIssueOut"][];
            /** File Sha256 */
            file_sha256: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            import_type: components["schemas"]["ImportType"];
            mode: components["schemas"]["ImportMode"] | null;
            /** Original Filename */
            original_filename: string;
            /** Row Count */
            row_count: number | null;
            /** Size Bytes */
            size_bytes: number;
            status: components["schemas"]["ImportStatus"];
            summary: components["schemas"]["ImportSummary"];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Validated At */
            validated_at: string | null;
        };
        /** ImportFreshness */
        ImportFreshness: {
            /**
             * Applied At
             * @description Latest applied_at of a COMPLETED or COMPLETED_WITH_ERRORS import (M-05).
             */
            applied_at: string | null;
            /** Import Id */
            import_id: string | null;
            import_type: components["schemas"]["ImportType"];
            status: components["schemas"]["ImportStatus"] | null;
        };
        /** ImportIssueOut */
        ImportIssueOut: {
            /** Code */
            code: string;
            /** Column */
            column: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Message */
            message: string;
            /** Raw Value */
            raw_value: string | null;
            /** Row Number */
            row_number: number | null;
            severity: components["schemas"]["IssueSeverity"];
        };
        /**
         * ImportMode
         * @enum {string}
         */
        ImportMode: "STRICT" | "VALID_ROWS_ONLY";
        /** ImportOut */
        ImportOut: {
            /** Applied At */
            applied_at: string | null;
            /** Applied By */
            applied_by: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Created By */
            created_by: string | null;
            /** Evaluation Run Id */
            evaluation_run_id: string | null;
            /** Expires At */
            expires_at: string | null;
            /** Failure Reason */
            failure_reason: string | null;
            /** File Sha256 */
            file_sha256: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            import_type: components["schemas"]["ImportType"];
            mode: components["schemas"]["ImportMode"] | null;
            /** Original Filename */
            original_filename: string;
            /** Row Count */
            row_count: number | null;
            /** Size Bytes */
            size_bytes: number;
            status: components["schemas"]["ImportStatus"];
            summary: components["schemas"]["ImportSummary"];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Validated At */
            validated_at: string | null;
        };
        /**
         * ImportStatus
         * @enum {string}
         */
        ImportStatus: "UPLOADED" | "VALIDATING" | "VALIDATED" | "REJECTED" | "APPLYING" | "COMPLETED" | "COMPLETED_WITH_ERRORS" | "FAILED" | "DISCARDED";
        /**
         * ImportSummary
         * @description Validation counts and the first planned changes (summary JSON of ``data_import``).
         */
        ImportSummary: {
            applied?: components["schemas"]["AppliedCounts"] | null;
            /**
             * Creates
             * @default 0
             */
            creates: number;
            /** Evaluation Error */
            evaluation_error?: string | null;
            /** Issue Counts By Code */
            issue_counts_by_code?: {
                [key: string]: number;
            };
            /** Preview */
            preview?: components["schemas"]["PreviewRow"][];
            /**
             * Rows Total
             * @default 0
             */
            rows_total: number;
            /**
             * Rows Valid
             * @default 0
             */
            rows_valid: number;
            /**
             * Rows With Errors
             * @default 0
             */
            rows_with_errors: number;
            /**
             * Rows With Warnings
             * @default 0
             */
            rows_with_warnings: number;
            /**
             * Unchanged
             * @default 0
             */
            unchanged: number;
            /**
             * Updates
             * @default 0
             */
            updates: number;
        };
        /**
         * ImportType
         * @enum {string}
         */
        ImportType: "products" | "orders" | "order_items" | "inventory_adjustments";
        /**
         * InventoryHealthSummary
         * @description ACTIVE products by health from current balances (§2.5), not from exceptions.
         */
        InventoryHealthSummary: {
            /** Active Products */
            active_products: number;
            /** Approaching Reorder Point */
            approaching_reorder_point: number;
            /** Below Reorder Point */
            below_reorder_point: number;
            /** Healthy */
            healthy: number;
            /** Out Of Stock */
            out_of_stock: number;
            /** Oversold */
            oversold: number;
        };
        /** InventoryPositionOut */
        InventoryPositionOut: {
            /**
             * Available
             * @description BR-101: on_hand − reserved. May be negative (BR-102).
             */
            available: number;
            /**
             * Avg Daily Units
             * @description Estimate (BR-150, BR-152).
             */
            avg_daily_units: string;
            /** Category */
            category: string | null;
            /**
             * Days Of Cover
             * @description Estimate (BR-151, BR-152); null means not enough sales history.
             */
            days_of_cover: string | null;
            /** @description §2.5; null for products that are not ACTIVE. */
            health: components["schemas"]["StockHealth"] | null;
            /**
             * Incoming
             * @description Never counted in available (BR-103).
             */
            incoming: number;
            /** Incoming Eta */
            incoming_eta: string | null;
            /** Last Cycle Count At */
            last_cycle_count_at: string | null;
            /** Name */
            name: string;
            /** On Hand */
            on_hand: number;
            /**
             * Product Id
             * Format: uuid
             */
            product_id: string;
            /** Reorder Point */
            reorder_point: number;
            /** Reserved */
            reserved: number;
            /** Sku */
            sku: string;
            status: components["schemas"]["ProductStatus"];
        };
        /**
         * IssueSeverity
         * @enum {string}
         */
        IssueSeverity: "ERROR" | "WARNING";
        /**
         * LinkRole
         * @enum {string}
         */
        LinkRole: "PRIMARY" | "AFFECTED";
        /** LinkedException */
        LinkedException: {
            exception_type: components["schemas"]["ExceptionType"];
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Is Active */
            is_active: boolean;
            link_role: components["schemas"]["LinkRole"];
            priority_band: components["schemas"]["PriorityBand"];
            /** Reference */
            reference: string;
            severity: components["schemas"]["Severity"];
            status: components["schemas"]["ExceptionStatus"];
        };
        /** LoginRequest */
        LoginRequest: {
            /** Email */
            email: string;
            /** Password */
            password: string;
        };
        /**
         * ManualResolutionCode
         * @description Resolution codes a person may choose (STATE_MACHINES.md §3.2).
         * @enum {string}
         */
        ManualResolutionCode: "STOCK_REPLENISHED" | "ORDER_FULFILLED" | "REFUND_ISSUED" | "DATA_CORRECTED" | "CUSTOMER_CONTACTED" | "FIXED_IN_SOURCE_SYSTEM" | "OTHER";
        /** MeResponse */
        MeResponse: {
            /** Csrf Token */
            csrf_token: string;
            /** Memberships */
            memberships: components["schemas"]["MembershipOut"][];
            user: components["schemas"]["UserOut"];
        };
        /** MemberList */
        MemberList: {
            /** Items */
            items: components["schemas"]["MemberOut"][];
        };
        /**
         * MemberOut
         * @description A member as shown in the assignee picker. Emails are deliberately not exposed.
         */
        MemberOut: {
            /** Can Work Exceptions */
            can_work_exceptions: boolean;
            /** Full Name */
            full_name: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            role: components["schemas"]["Role"];
        };
        /** MembershipOut */
        MembershipOut: {
            /** Is Demo */
            is_demo: boolean;
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            /** Organization Name */
            organization_name: string;
            /** Permissions */
            permissions: components["schemas"]["Permission"][];
            role: components["schemas"]["Role"];
            /** Stores */
            stores: components["schemas"]["StoreSummary"][];
        };
        /** MovementOut */
        MovementOut: {
            /** Created By */
            created_by: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Import Id */
            import_id: string | null;
            /** Incoming After */
            incoming_after: number;
            /** Incoming Delta */
            incoming_delta: number;
            movement_type: components["schemas"]["MovementType"];
            /** Note */
            note: string | null;
            /**
             * Occurred At
             * Format: date-time
             */
            occurred_at: string;
            /** On Hand After */
            on_hand_after: number;
            /** On Hand Delta */
            on_hand_delta: number;
            /**
             * Product Id
             * Format: uuid
             */
            product_id: string;
            /** Product Name */
            product_name: string;
            /**
             * Recorded At
             * Format: date-time
             */
            recorded_at: string;
            /** Reference */
            reference: string | null;
            /** Sku */
            sku: string;
            source: components["schemas"]["MovementSource"];
        };
        /**
         * MovementSource
         * @enum {string}
         */
        MovementSource: "IMPORT" | "ORDER" | "SYSTEM";
        /**
         * MovementType
         * @enum {string}
         */
        MovementType: "CYCLE_COUNT" | "RECEIPT" | "INCOMING_EXPECTED" | "INCOMING_CANCELLED" | "DAMAGE" | "SHRINKAGE" | "RETURN_RESTOCK" | "CORRECTION" | "SHIPMENT";
        /** NoteCreate */
        NoteCreate: {
            /** Body */
            body: string;
            /**
             * Expected Version
             * @description Optimistic concurrency: 409 STALE_VERSION on mismatch
             */
            expected_version?: number | null;
        };
        /**
         * NoteSource
         * @enum {string}
         */
        NoteSource: "USER" | "AI_DRAFT_ACCEPTED";
        /** OnTimeShipment */
        OnTimeShipment: {
            /** Late */
            late: number;
            /**
             * On Time
             * @description Numerator: shipped_at ≤ ship_by.
             */
            on_time: number;
            /**
             * On Time Rate Pct
             * @description 100 × on_time / shipped_with_deadline, 1 dp; null when the denominator is 0.
             */
            on_time_rate_pct: string | null;
            /**
             * Shipped With Deadline
             * @description Denominator: shipped in window with ship_by.
             */
            shipped_with_deadline: number;
            /**
             * Shipped Without Deadline
             * @description Shipped in window without ship_by.
             */
            shipped_without_deadline: number;
            window: components["schemas"]["TimeWindow"];
        };
        /**
         * OrderAmounts
         * @description Recorded amounts and the BR-205 reconciliation.
         */
        OrderAmounts: {
            /** Currency */
            currency: string;
            /**
             * Difference
             * @description total − expected_total.
             */
            difference: string | null;
            /** Discount Total */
            discount_total: string;
            /**
             * Expected Total
             * @description lines_total − discount_total + shipping_total + tax_total; null without lines.
             */
            expected_total: string | null;
            /**
             * Has Total Mismatch
             * @description |difference| > 0.01 and at least one line.
             */
            has_total_mismatch: boolean;
            /**
             * Lines Total
             * @description Σ (quantity × unit_price − line_discount).
             */
            lines_total: string;
            /** Shipping Total */
            shipping_total: string;
            /** Subtotal */
            subtotal: string;
            /** Tax Total */
            tax_total: string;
            /** Total */
            total: string;
        };
        /** OrderDetail */
        OrderDetail: {
            amounts: components["schemas"]["OrderAmounts"];
            /** Cancelled At */
            cancelled_at: string | null;
            /** Carrier */
            carrier: string | null;
            channel: components["schemas"]["SalesChannel"];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Customer Ref */
            customer_ref: string | null;
            /** Delivered At */
            delivered_at: string | null;
            /**
             * Events
             * @description Status history, oldest first.
             */
            events: components["schemas"]["OrderEventOut"][];
            /**
             * Exceptions
             * @description Active first, then newest first.
             */
            exceptions: components["schemas"]["LinkedException"][];
            fulfillment_status: components["schemas"]["FulfillmentStatus"];
            /** Hours Overdue */
            hours_overdue: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Is Overdue
             * @description BR-202 evaluated at the request time.
             */
            is_overdue: boolean;
            /** Last Import Id */
            last_import_id: string | null;
            /** Lines */
            lines: components["schemas"]["OrderLineOut"][];
            /** Order Number */
            order_number: string;
            /** Paid At */
            paid_at: string | null;
            payment_status: components["schemas"]["PaymentStatus"];
            /**
             * Placed At
             * Format: date-time
             */
            placed_at: string;
            /** Ship By */
            ship_by: string | null;
            /** @description IMPORTED (from the source system) or STORE_SLA (paid_at + SLA), BR-201. */
            ship_by_source: components["schemas"]["ShipBySource"] | null;
            /** Shipped At */
            shipped_at: string | null;
            status: components["schemas"]["OrderStatus"];
            /** Tracking Number */
            tracking_number: string | null;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** OrderEventOut */
        OrderEventOut: {
            /** Actor User Id */
            actor_user_id: string | null;
            from_status: components["schemas"]["OrderStatus"] | null;
            fulfillment_status: components["schemas"]["FulfillmentStatus"];
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Import Id */
            import_id: string | null;
            /**
             * Occurred At
             * Format: date-time
             */
            occurred_at: string;
            payment_status: components["schemas"]["PaymentStatus"];
            /** Skipped Statuses */
            skipped_statuses: string[];
            source: components["schemas"]["ChangeSource"];
            to_status: components["schemas"]["OrderStatus"];
        };
        /** OrderHealthSummary */
        OrderHealthSummary: {
            /**
             * Awaiting Shipment
             * @description Orders in PAID, PROCESSING or READY_TO_SHIP.
             */
            awaiting_shipment: number;
            /**
             * Overdue Count
             * @description BR-202 at as_of: committed status and ship_by < as_of.
             */
            overdue_count: number;
            /**
             * Overdue Value
             * @description Σ total of the overdue orders (gross).
             */
            overdue_value: string;
        };
        /** OrderLineOut */
        OrderLineOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Line Discount */
            line_discount: string;
            /** Line Number */
            line_number: number;
            /** Line Total */
            line_total: string;
            /**
             * Product Id
             * Format: uuid
             */
            product_id: string;
            /** Product Name */
            product_name: string;
            /** Product Sku */
            product_sku: string;
            /** Quantity */
            quantity: number;
            reservation: components["schemas"]["ReservationRef"] | null;
            /**
             * Sku
             * @description SKU as imported on the line.
             */
            sku: string;
            /** Unit Price */
            unit_price: string;
        };
        /** OrderListItem */
        OrderListItem: {
            channel: components["schemas"]["SalesChannel"];
            /** Currency */
            currency: string;
            /** Customer Ref */
            customer_ref: string | null;
            fulfillment_status: components["schemas"]["FulfillmentStatus"];
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Is Overdue
             * @description BR-202 evaluated at the request time.
             */
            is_overdue: boolean;
            /** Line Count */
            line_count: number;
            /** Order Number */
            order_number: string;
            /** Paid At */
            paid_at: string | null;
            payment_status: components["schemas"]["PaymentStatus"];
            /**
             * Placed At
             * Format: date-time
             */
            placed_at: string;
            /** Ship By */
            ship_by: string | null;
            ship_by_source: components["schemas"]["ShipBySource"] | null;
            /** Shipped At */
            shipped_at: string | null;
            status: components["schemas"]["OrderStatus"];
            /** Total */
            total: string;
        };
        /**
         * OrderStatus
         * @enum {string}
         */
        OrderStatus: "CREATED" | "PAYMENT_PENDING" | "PAYMENT_FAILED" | "PAID" | "PROCESSING" | "READY_TO_SHIP" | "SHIPPED" | "DELIVERED" | "RETURN_REQUESTED" | "RETURNED" | "CANCELLED" | "REFUNDED";
        /** OrganizationOut */
        OrganizationOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Is Demo */
            is_demo: boolean;
            /** Name */
            name: string;
        };
        /** Page[AuditLogOut] */
        Page_AuditLogOut_: {
            /** Items */
            items: components["schemas"]["AuditLogOut"][];
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
            /** Total */
            total: number;
        };
        /** Page[EvaluationRunOut] */
        Page_EvaluationRunOut_: {
            /** Items */
            items: components["schemas"]["EvaluationRunOut"][];
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
            /** Total */
            total: number;
        };
        /** Page[ExceptionEventOut] */
        Page_ExceptionEventOut_: {
            /** Items */
            items: components["schemas"]["ExceptionEventOut"][];
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
            /** Total */
            total: number;
        };
        /** Page[ExceptionListItem] */
        Page_ExceptionListItem_: {
            /** Items */
            items: components["schemas"]["ExceptionListItem"][];
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
            /** Total */
            total: number;
        };
        /** Page[ExceptionNoteOut] */
        Page_ExceptionNoteOut_: {
            /** Items */
            items: components["schemas"]["ExceptionNoteOut"][];
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
            /** Total */
            total: number;
        };
        /** Page[ImportIssueOut] */
        Page_ImportIssueOut_: {
            /** Items */
            items: components["schemas"]["ImportIssueOut"][];
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
            /** Total */
            total: number;
        };
        /** Page[ImportOut] */
        Page_ImportOut_: {
            /** Items */
            items: components["schemas"]["ImportOut"][];
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
            /** Total */
            total: number;
        };
        /** Page[InventoryPositionOut] */
        Page_InventoryPositionOut_: {
            /** Items */
            items: components["schemas"]["InventoryPositionOut"][];
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
            /** Total */
            total: number;
        };
        /** Page[MovementOut] */
        Page_MovementOut_: {
            /** Items */
            items: components["schemas"]["MovementOut"][];
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
            /** Total */
            total: number;
        };
        /** Page[OrderListItem] */
        Page_OrderListItem_: {
            /** Items */
            items: components["schemas"]["OrderListItem"][];
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
            /** Total */
            total: number;
        };
        /** Page[ProductListItem] */
        Page_ProductListItem_: {
            /** Items */
            items: components["schemas"]["ProductListItem"][];
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
            /** Total */
            total: number;
        };
        /** Page[SupplierOut] */
        Page_SupplierOut_: {
            /** Items */
            items: components["schemas"]["SupplierOut"][];
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
            /** Total */
            total: number;
        };
        /**
         * PaymentStatus
         * @enum {string}
         */
        PaymentStatus: "PENDING" | "PAID" | "FAILED" | "REFUNDED";
        /**
         * Permission
         * @enum {string}
         */
        Permission: "dashboard.read" | "catalog.read" | "orders.read" | "inventory.read" | "exceptions.read" | "exceptions.work" | "exceptions.assign" | "exceptions.manage" | "evaluations.run" | "imports.read" | "imports.run" | "analytics.read" | "copilot.use" | "audit.read" | "settings.read" | "settings.manage" | "users.read" | "users.manage";
        /** PreviewRow */
        PreviewRow: {
            action: components["schemas"]["RowAction"];
            /** Changed Fields */
            changed_fields: string[];
            /** Key */
            key: string;
            /** Row Number */
            row_number: number;
        };
        /**
         * PriorityBand
         * @enum {string}
         */
        PriorityBand: "P1" | "P2" | "P3" | "P4";
        /**
         * PriorityWeights
         * @description Same shape as ``DEFAULT_PRIORITY_WEIGHTS`` (PRIORITY_MODEL.md, Configuration).
         *
         *     Every component is a non-negative integer, and the highest score the weights can produce
         *     (``max S + cap_A + cap_E + max D + cap_T``) must not exceed 100.
         */
        PriorityWeights: {
            /** Affected Orders Cap */
            affected_orders_cap: number;
            /** Affected Orders Per Order */
            affected_orders_per_order: number;
            /** Age Cap */
            age_cap: number;
            /** Age Points Per Day */
            age_points_per_day: number;
            deadline: components["schemas"]["DeadlineWeights"];
            /** Exposure Cap Points */
            exposure_cap_points: number;
            severity: components["schemas"]["SeverityWeights"];
        };
        /** ProductDetail */
        ProductDetail: {
            /**
             * Active Exception Count
             * @description Active exceptions linked to the product as PRIMARY or AFFECTED entity.
             */
            active_exception_count: number;
            /**
             * Approaching Threshold
             * @description ceil(reorder_point × approaching_reorder_factor); null if reorder_point is 0.
             */
            approaching_threshold: number | null;
            avg_daily_units: components["schemas"]["Estimate"];
            /** Category */
            category: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            days_of_cover: components["schemas"]["Estimate"];
            /** @description §2.5; null for products that are not ACTIVE. */
            health: components["schemas"]["StockHealth"] | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Reorder Point */
            reorder_point: number;
            /** Reorder Quantity */
            reorder_quantity: number | null;
            /** Sku */
            sku: string;
            status: components["schemas"]["ProductStatus"];
            stock: components["schemas"]["StockSnapshot"];
            supplier: components["schemas"]["SupplierDetail"] | null;
            /** Unit Cost */
            unit_cost: string | null;
            /** Unit Price */
            unit_price: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** ProductListItem */
        ProductListItem: {
            /**
             * Available
             * @description BR-101: on_hand − reserved.
             */
            available: number;
            /** Category */
            category: string | null;
            /** @description §2.5; null for products that are not ACTIVE. */
            health: components["schemas"]["StockHealth"] | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** On Hand */
            on_hand: number;
            /** Reorder Point */
            reorder_point: number;
            /** Reorder Quantity */
            reorder_quantity: number | null;
            /** Reserved */
            reserved: number;
            /** Sku */
            sku: string;
            status: components["schemas"]["ProductStatus"];
            supplier: components["schemas"]["SupplierRef"] | null;
            /** Unit Cost */
            unit_cost: string | null;
            /** Unit Price */
            unit_price: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * ProductStatus
         * @enum {string}
         */
        ProductStatus: "ACTIVE" | "DRAFT" | "ARCHIVED";
        /**
         * ReconciliationOut
         * @description BR-104: cached balances compared with the ledger and reservations. Drift is a defect.
         */
        ReconciliationOut: {
            /**
             * Checked At
             * Format: date-time
             */
            checked_at: string;
            /** Drift Count */
            drift_count: number;
            /** Is Consistent */
            is_consistent: boolean;
            /** Items */
            items: components["schemas"]["DriftOut"][];
        };
        /** ReopenRequest */
        ReopenRequest: {
            /**
             * Expected Version
             * @description Optimistic concurrency: 409 STALE_VERSION on mismatch
             */
            expected_version?: number | null;
            /**
             * Reason
             * @description Why the exception is reopened
             */
            reason: string;
        };
        /** ReservationRef */
        ReservationRef: {
            /** Quantity */
            quantity: number;
            status: components["schemas"]["ReservationStatus"];
        };
        /**
         * ReservationStatus
         * @enum {string}
         */
        ReservationStatus: "ACTIVE" | "CONSUMED" | "RELEASED";
        /**
         * ResolutionCode
         * @enum {string}
         */
        ResolutionCode: "STOCK_REPLENISHED" | "ORDER_FULFILLED" | "REFUND_ISSUED" | "DATA_CORRECTED" | "CUSTOMER_CONTACTED" | "FIXED_IN_SOURCE_SYSTEM" | "OTHER" | "CONDITION_CLEARED" | "SUPERSEDED";
        /** ResolutionOut */
        ResolutionOut: {
            resolution_actor: components["schemas"]["ActorType"] | null;
            resolution_code: components["schemas"]["ResolutionCode"] | null;
            /** Resolution Note */
            resolution_note: string | null;
            /** Resolved At */
            resolved_at: string | null;
            resolved_by: components["schemas"]["UserRef"] | null;
            /** Verified At */
            verified_at: string | null;
        };
        /** ResolveRequest */
        ResolveRequest: {
            /**
             * Expected Version
             * @description Optimistic concurrency: 409 STALE_VERSION on mismatch
             */
            expected_version?: number | null;
            resolution_code: components["schemas"]["ManualResolutionCode"];
            /** Resolution Note */
            resolution_note: string;
        };
        /**
         * Role
         * @enum {string}
         */
        Role: "OWNER" | "MANAGER" | "STAFF" | "ANALYST" | "VIEWER";
        /** RolePermissionsOut */
        RolePermissionsOut: {
            /** Permissions */
            permissions: components["schemas"]["Permission"][];
            role: components["schemas"]["Role"];
        };
        /**
         * RowAction
         * @enum {string}
         */
        RowAction: "CREATE" | "UPDATE" | "UNCHANGED" | "SKIP";
        /**
         * SalesChannel
         * @enum {string}
         */
        SalesChannel: "WEB" | "MARKETPLACE" | "POS" | "OTHER";
        /** SalesSummary */
        SalesSummary: {
            /**
             * Gmv
             * @description Σ total of paid_orders (gross; refunds not subtracted).
             */
            gmv: string;
            /**
             * Orders Placed
             * @description Orders with placed_at in the window, any status.
             */
            orders_placed: number;
            /**
             * Paid Orders
             * @description The GMV population: placed in the window and paid.
             */
            paid_orders: number;
            window: components["schemas"]["TimeWindow"];
        };
        /**
         * Severity
         * @enum {string}
         */
        Severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
        /** SeverityWeights */
        SeverityWeights: {
            /** Critical */
            CRITICAL: number;
            /** High */
            HIGH: number;
            /** Low */
            LOW: number;
            /** Medium */
            MEDIUM: number;
        };
        /**
         * ShipBySource
         * @enum {string}
         */
        ShipBySource: "IMPORTED" | "STORE_SLA";
        /**
         * StockHealth
         * @enum {string}
         */
        StockHealth: "OVERSOLD" | "OUT_OF_STOCK" | "BELOW_REORDER_POINT" | "APPROACHING_REORDER_POINT" | "HEALTHY";
        /** StockSnapshot */
        StockSnapshot: {
            /** Available */
            available: number;
            /** Incoming */
            incoming: number;
            /** Incoming Eta */
            incoming_eta: string | null;
            /** Last Cycle Count At */
            last_cycle_count_at: string | null;
            /** On Hand */
            on_hand: number;
            /** Reserved */
            reserved: number;
        };
        /** StoreDetailOut */
        StoreDetailOut: {
            data_freshness: components["schemas"]["DataFreshness"];
            settings: components["schemas"]["StoreSettingsOut"];
            store: components["schemas"]["StoreOut"];
        };
        /** StoreOut */
        StoreOut: {
            /** Code */
            code: string;
            /** Currency */
            currency: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            organization: components["schemas"]["OrganizationOut"];
            /** Timezone */
            timezone: string;
        };
        /** StoreSettingsOut */
        StoreSettingsOut: {
            /**
             * Approaching Reorder Factor
             * @description §2.5 APPROACHING_REORDER_POINT
             */
            approaching_reorder_factor: string;
            /** Evaluation Interval Minutes */
            evaluation_interval_minutes: number;
            /**
             * Exposure Cap
             * @description PRIORITY_MODEL.md exposure component
             */
            exposure_cap: string;
            /**
             * Fulfillment Sla Hours
             * @description BR-201: ship_by = paid_at + this many hours.
             */
            fulfillment_sla_hours: number;
            priority_weights: components["schemas"]["PriorityWeights"];
            /**
             * Refund Overdue Hours
             * @description BR-206
             */
            refund_overdue_hours: number;
            /**
             * Reopen Window Hours
             * @description STATE_MACHINES.md §3.3
             */
            reopen_window_hours: number;
            /**
             * Stall Threshold Hours
             * @description BR-203
             */
            stall_threshold_hours: number;
            /** Updated At */
            updated_at: string | null;
            /**
             * Velocity Window Days
             * @description BR-150
             */
            velocity_window_days: number;
        };
        /**
         * StoreSettingsUpdate
         * @description Partial update. Omitted fields keep their value; an explicit ``null`` is rejected.
         */
        StoreSettingsUpdate: {
            /** Approaching Reorder Factor */
            approaching_reorder_factor?: number | string | null;
            /** Evaluation Interval Minutes */
            evaluation_interval_minutes?: number | null;
            /** Exposure Cap */
            exposure_cap?: number | string | null;
            /** Fulfillment Sla Hours */
            fulfillment_sla_hours?: number | null;
            priority_weights?: components["schemas"]["PriorityWeights"] | null;
            /** Refund Overdue Hours */
            refund_overdue_hours?: number | null;
            /** Reopen Window Hours */
            reopen_window_hours?: number | null;
            /** Stall Threshold Hours */
            stall_threshold_hours?: number | null;
            /** Velocity Window Days */
            velocity_window_days?: number | null;
        };
        /** StoreSummary */
        StoreSummary: {
            /** Code */
            code: string;
            /** Currency */
            currency: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Timezone */
            timezone: string;
        };
        /** SupplierDetail */
        SupplierDetail: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Lead Time Days */
            lead_time_days: number | null;
            /** Name */
            name: string;
        };
        /** SupplierOut */
        SupplierOut: {
            /** Contact Ref */
            contact_ref: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Lead Time Days */
            lead_time_days: number | null;
            /** Name */
            name: string;
            /** Product Count */
            product_count: number;
        };
        /** SupplierRef */
        SupplierRef: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
        };
        /**
         * TimeWindow
         * @description Half-open window ``[start, end)`` in UTC. ``start`` is midnight in the store time zone.
         */
        TimeWindow: {
            /**
             * Days
             * @description Number of store-local calendar days; the last one is partial.
             */
            days: number;
            /**
             * End
             * Format: date-time
             */
            end: string;
            /**
             * Start
             * Format: date-time
             */
            start: string;
            /** Timezone */
            timezone: string;
        };
        /** TrendDay */
        TrendDay: {
            /**
             * Date
             * Format: date
             */
            date: string;
            /**
             * Exceptions Detected
             * @description Exceptions with first_detected_at in the day.
             */
            exceptions_detected: number;
            /**
             * Exceptions Resolved
             * @description RESOLVED exceptions (excluding SUPERSEDED) with resolved_at in the day.
             */
            exceptions_resolved: number;
            /** Gmv */
            gmv: string;
            /** Orders Placed */
            orders_placed: number;
            /** Shipped Late */
            shipped_late: number;
            /** Shipped On Time */
            shipped_on_time: number;
            /**
             * Units
             * @description Units on lines of orders placed (BR-150 status filter).
             */
            units: number;
        };
        /** TrendMetrics */
        TrendMetrics: {
            /**
             * Exceptions Detected
             * @description Exceptions with first_detected_at in the day.
             */
            exceptions_detected: number;
            /**
             * Exceptions Resolved
             * @description RESOLVED exceptions (excluding SUPERSEDED) with resolved_at in the day.
             */
            exceptions_resolved: number;
            /** Gmv */
            gmv: string;
            /** Orders Placed */
            orders_placed: number;
            /** Shipped Late */
            shipped_late: number;
            /** Shipped On Time */
            shipped_on_time: number;
            /**
             * Units
             * @description Units on lines of orders placed (BR-150 status filter).
             */
            units: number;
        };
        /** TrendsOut */
        TrendsOut: {
            /**
             * As Of
             * Format: date-time
             */
            as_of: string;
            /** Currency */
            currency: string;
            /** Days */
            days: components["schemas"]["TrendDay"][];
            /**
             * Partial Last Day
             * @default true
             */
            partial_last_day: boolean;
            totals: components["schemas"]["TrendMetrics"];
            window: components["schemas"]["TimeWindow"];
        };
        /** UserOut */
        UserOut: {
            /** Email */
            email: string;
            /** Full Name */
            full_name: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
        };
        /** UserRef */
        UserRef: {
            /** Full Name */
            full_name: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
        /** VersionedRequest */
        VersionedRequest: {
            /**
             * Expected Version
             * @description Optimistic concurrency: 409 STALE_VERSION on mismatch
             */
            expected_version?: number | null;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    demo_login_api_v1_auth_demo_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeResponse"];
                };
            };
        };
    };
    login_api_v1_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    logout_api_v1_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    me_api_v1_auth_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeResponse"];
                };
            };
        };
    };
    live_api_v1_health_live_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
        };
    };
    ready_api_v1_health_ready_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    list_roles_api_v1_roles_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RolePermissionsOut"][];
                };
            };
        };
    };
    get_store_api_v1_stores__store_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StoreDetailOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_dashboard_api_v1_stores__store_id__analytics_dashboard_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DashboardOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_exception_breakdown_api_v1_stores__store_id__analytics_exceptions_breakdown_get: {
        parameters: {
            query?: {
                /** @description Store-local days, ending today. */
                days?: number;
            };
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExceptionBreakdownOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_trends_api_v1_stores__store_id__analytics_trends_get: {
        parameters: {
            query?: {
                /** @description Store-local days, ending today. */
                days?: number;
            };
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TrendsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_audit_logs_api_v1_stores__store_id__audit_logs_get: {
        parameters: {
            query?: {
                /** @description Action prefix, e.g. 'exception.' */
                action?: string | null;
                actor_user_id?: string | null;
                from?: string | null;
                to?: string | null;
                page?: number;
                page_size?: number;
            };
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_AuditLogOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_categories_api_v1_stores__store_id__categories_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CategoryList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_evaluations_api_v1_stores__store_id__evaluations_get: {
        parameters: {
            query?: {
                status?: components["schemas"]["EvaluationStatus"][] | null;
                trigger?: components["schemas"]["EvaluationTrigger"][] | null;
                /** @description started_at or as_of; '-' = descending */
                sort?: string;
                page?: number;
                page_size?: number;
            };
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_EvaluationRunOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    trigger_evaluation_api_v1_stores__store_id__evaluations_post: {
        parameters: {
            query?: never;
            header?: {
                "Idempotency-Key"?: string | null;
            };
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["EvaluationCreate"] | null;
            };
        };
        responses: {
            /** @description Idempotent replay, or SKIPPED because a run is in progress */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EvaluationRunOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_evaluation_api_v1_stores__store_id__evaluations__run_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EvaluationRunOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_exceptions_api_v1_stores__store_id__exceptions_get: {
        parameters: {
            query?: {
                /** @description Repeatable. Defaults to the active statuses. */
                status?: components["schemas"]["ExceptionStatus"][] | null;
                severity?: components["schemas"]["Severity"][] | null;
                exception_type?: components["schemas"]["ExceptionType"][] | null;
                category?: components["schemas"]["ExceptionCategory"][] | null;
                priority_band?: components["schemas"]["PriorityBand"][] | null;
                /** @description 'me', 'unassigned' or a user id */
                assignee?: string | null;
                product_id?: string | null;
                order_id?: string | null;
                /** @description Reference or title contains */
                q?: string | null;
                /** @description Only exceptions due at or before this instant (with a time zone) */
                due_to?: string | null;
                /** @description priority_score, due_at, first_detected_at, last_detected_at; '-' = desc */
                sort?: string;
                page?: number;
                page_size?: number;
            };
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ExceptionListItem_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_exception_api_v1_stores__store_id__exceptions__exception_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                exception_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExceptionDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    acknowledge_exception_api_v1_stores__store_id__exceptions__exception_id__acknowledge_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                exception_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["VersionedRequest"] | null;
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExceptionDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    assign_exception_api_v1_stores__store_id__exceptions__exception_id__assign_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                exception_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AssignRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExceptionDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    dismiss_exception_api_v1_stores__store_id__exceptions__exception_id__dismiss_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                exception_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DismissRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExceptionDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_exception_due_date_api_v1_stores__store_id__exceptions__exception_id__due_date_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                exception_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DueDateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExceptionDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_exception_events_api_v1_stores__store_id__exceptions__exception_id__events_get: {
        parameters: {
            query?: {
                page?: number;
                page_size?: number;
            };
            header?: never;
            path: {
                exception_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ExceptionEventOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_exception_notes_api_v1_stores__store_id__exceptions__exception_id__notes_get: {
        parameters: {
            query?: {
                page?: number;
                page_size?: number;
            };
            header?: never;
            path: {
                exception_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ExceptionNoteOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    add_exception_note_api_v1_stores__store_id__exceptions__exception_id__notes_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                exception_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["NoteCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExceptionNoteOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reopen_exception_api_v1_stores__store_id__exceptions__exception_id__reopen_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                exception_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReopenRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExceptionDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    resolve_exception_api_v1_stores__store_id__exceptions__exception_id__resolve_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                exception_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResolveRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExceptionDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    start_exception_api_v1_stores__store_id__exceptions__exception_id__start_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                exception_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["VersionedRequest"] | null;
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExceptionDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_imports_api_v1_stores__store_id__imports_get: {
        parameters: {
            query?: {
                import_type?: components["schemas"]["ImportType"] | null;
                status?: components["schemas"]["ImportStatus"] | null;
                sort?: "created_at" | "-created_at" | "applied_at" | "-applied_at" | "status" | "-status" | "import_type" | "-import_type";
                page?: number;
                page_size?: number;
            };
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ImportOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_import_api_v1_stores__store_id__imports_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_create_import_api_v1_stores__store_id__imports_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ImportDetailOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    download_template_api_v1_stores__store_id__imports_templates__import_type__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                import_type: components["schemas"]["ImportType"];
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description CSV template */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/csv": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_import_api_v1_stores__store_id__imports__import_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                import_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ImportDetailOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    apply_import_api_v1_stores__store_id__imports__import_id__apply_post: {
        parameters: {
            query?: never;
            header?: {
                "Idempotency-Key"?: string | null;
            };
            path: {
                import_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ApplyImportRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ImportDetailOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    discard_import_api_v1_stores__store_id__imports__import_id__discard_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                import_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ImportDetailOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_issues_api_v1_stores__store_id__imports__import_id__issues_get: {
        parameters: {
            query?: {
                severity?: components["schemas"]["IssueSeverity"] | null;
                code?: string | null;
                sort?: "row_number" | "-row_number" | "code" | "-code" | "severity" | "-severity";
                page?: number;
                page_size?: number;
            };
            header?: never;
            path: {
                import_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ImportIssueOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    download_issues_api_v1_stores__store_id__imports__import_id__issues_csv_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                import_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Issues as CSV */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/csv": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_movements_api_v1_stores__store_id__inventory_movements_get: {
        parameters: {
            query?: {
                product_id?: string | null;
                /** @description Repeatable. */
                movement_type?: components["schemas"]["MovementType"][] | null;
                source?: components["schemas"]["MovementSource"] | null;
                /** @description Inclusive. */
                from?: string | null;
                /** @description Exclusive. */
                to?: string | null;
                sort?: "-recorded_at" | "recorded_at" | "-occurred_at" | "occurred_at";
                page?: number;
                page_size?: number;
            };
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_MovementOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_positions_api_v1_stores__store_id__inventory_positions_get: {
        parameters: {
            query?: {
                /** @description Substring of SKU or name. */
                q?: string | null;
                /** @description Repeatable. */
                health?: components["schemas"]["StockHealth"][] | null;
                category?: string | null;
                /** @description Include DRAFT and ARCHIVED products. */
                include_inactive?: boolean;
                sort?: "available" | "-available" | "days_of_cover" | "-days_of_cover" | "sku" | "-sku";
                page?: number;
                page_size?: number;
            };
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_InventoryPositionOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_reconciliation_api_v1_stores__store_id__inventory_reconciliation_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReconciliationOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_members_api_v1_stores__store_id__members_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MemberList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_orders_api_v1_stores__store_id__orders_get: {
        parameters: {
            query?: {
                /** @description Substring of order number or customer. */
                q?: string | null;
                /** @description Repeatable. */
                status?: components["schemas"]["OrderStatus"][] | null;
                payment_status?: components["schemas"]["PaymentStatus"] | null;
                fulfillment_status?: components["schemas"]["FulfillmentStatus"] | null;
                channel?: components["schemas"]["SalesChannel"] | null;
                /** @description Inclusive. */
                placed_from?: string | null;
                /** @description Exclusive. */
                placed_to?: string | null;
                /** @description BR-202: committed status and ship_by before now (false = the rest). */
                overdue?: boolean | null;
                /** @description Orders with a line for this product. */
                product_id?: string | null;
                sort?: "-placed_at" | "placed_at" | "-total" | "total" | "ship_by" | "-ship_by" | "order_number" | "-order_number";
                page?: number;
                page_size?: number;
            };
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_OrderListItem_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_order_api_v1_stores__store_id__orders__order_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                order_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OrderDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_products_api_v1_stores__store_id__products_get: {
        parameters: {
            query?: {
                /** @description Substring of SKU or name. */
                q?: string | null;
                status?: components["schemas"]["ProductStatus"] | null;
                category?: string | null;
                supplier_id?: string | null;
                /** @description Repeatable. ACTIVE products. */
                health?: components["schemas"]["StockHealth"][] | null;
                sort?: "sku" | "-sku" | "name" | "-name" | "updated_at" | "-updated_at" | "available" | "-available";
                page?: number;
                page_size?: number;
            };
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ProductListItem_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_product_api_v1_stores__store_id__products__product_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                product_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProductDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_settings_api_v1_stores__store_id__settings_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StoreSettingsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_settings_api_v1_stores__store_id__settings_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StoreSettingsUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StoreSettingsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_suppliers_api_v1_stores__store_id__suppliers_get: {
        parameters: {
            query?: {
                q?: string | null;
                sort?: "name" | "-name" | "lead_time_days" | "-lead_time_days";
                page?: number;
                page_size?: number;
            };
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_SupplierOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
