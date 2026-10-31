"""A few hours of team activity on the demo store's exceptions (T-056).

After the first evaluation, the fictional Kestrel team works the queue through the same code paths
the API uses: the exception lifecycle service (assign, acknowledge, start, note, resolve, dismiss),
the CSV import pipeline for two small data refreshes, and the rule engine, which verifies or reopens
manual resolutions. Nothing is written to exception tables by hand.

Timeline, in minutes after ``start`` (the time the dataset was generated for):

====  ===========================================================================================
  12  Priya (manager) assigns the worst oversold SKU to Marcus
  15  Priya assigns the out-of-stock SKU to Sofia
  22  Marcus acknowledges the oversold SKU
  35  Marcus starts the most overdue order and leaves a note
  50  Sofia starts a stalled paid order
  65  Sofia starts a pending refund
 100  Marcus starts a below-reorder-point SKU, notes the rush delivery, resolves it at 120
 150  Priya imports ``inventory_adjustments.csv`` with that receipt: the evaluation VERIFIES it
 165  Priya dismisses a 0.40 USD total mismatch as an accepted rounding difference
 180  Sofia resolves the stalled order (the payment webhook had failed)
 200  Sofia resolves the pending refund ("refund issued")
 240  Priya imports ``orders.csv``: the stalled order is now in processing (VERIFIED), but the
      refund still shows as paid, so the engine REOPENS that resolution (VERIFICATION_FAILED)
 250  Priya adds a note to the reopened refund
====  ===========================================================================================

The caller runs a final scheduled evaluation at the real "now" afterwards. Every person, note and
reference is fictional.
"""

import csv
import io
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.demo.seed import DemoSummary
from app.domains.catalog.models import Product
from app.domains.exceptions import engine
from app.domains.exceptions import service as exceptions
from app.domains.exceptions.models import (
    DismissalReason,
    EntityType,
    EvaluationStatus,
    EvaluationTrigger,
    ExceptionType,
    OperationalException,
    ResolutionCode,
)
from app.domains.identity import service as identity
from app.domains.identity.models import User
from app.domains.identity.service import StoreContext
from app.domains.imports import parsing
from app.domains.imports import service as imports
from app.domains.imports.models import DataImport, ImportMode, ImportStatus, ImportType
from app.domains.orders import service as orders
from app.domains.orders.models import Order

HISTORY_HOURS = 5
"""How long before "now" the dataset is generated, to leave room for the timeline above."""

MANAGER = "manager@kestrel.example"
STAFF_MARCUS = "staff@kestrel.example"
STAFF_SOFIA = "sofia@kestrel.example"


class DemoHistoryError(RuntimeError):
    """A step of the scripted history did not behave as designed (the seed is broken)."""


@dataclass
class HistorySummary:
    imports: list[str] = field(default_factory=list)
    evaluations: list[dict[str, int]] = field(default_factory=list)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _csv(header: list[str], rows: list[list[str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


class _History:
    def __init__(self, db: Session, summary: DemoSummary, start: datetime) -> None:
        self.db = db
        self.store_id = summary.store_id
        self.scenarios = summary.scenarios
        self.start = start
        self.result = HistorySummary()
        self._contexts: dict[str, StoreContext] = {}

    # ------------------------------------------------------------------ lookups
    def at(self, minutes: int) -> datetime:
        return self.start + timedelta(minutes=minutes)

    def ctx(self, email: str) -> StoreContext:
        if email not in self._contexts:
            user = self.db.scalars(select(User).where(User.email == email)).one()
            self._contexts[email] = identity.store_context(self.db, user, self.store_id)
        return self._contexts[email]

    def user_id(self, email: str) -> uuid.UUID:
        return self.ctx(email).user.id

    def product(self, sku: str) -> Product:
        return self.db.scalars(
            select(Product).where(Product.store_id == self.store_id, Product.sku == sku)
        ).one()

    def order(self, number: str) -> Order:
        order = orders.find_by_number(self.db, self.store_id, number)
        if order is None:
            raise DemoHistoryError(f"Scenario order {number} is missing.")
        return order

    def exception_for(
        self, exception_type: ExceptionType, entity_type: EntityType, entity_id: uuid.UUID
    ) -> uuid.UUID:
        exc_id = self.db.scalar(
            select(OperationalException.id)
            .where(
                OperationalException.store_id == self.store_id,
                OperationalException.exception_type == exception_type,
                OperationalException.primary_entity_type == entity_type,
                OperationalException.primary_entity_id == entity_id,
            )
            .order_by(OperationalException.first_detected_at.desc())
            .limit(1)
        )
        if exc_id is None:
            raise DemoHistoryError(f"No {exception_type.value} exception for {entity_id}.")
        return exc_id

    def product_exception(self, exception_type: ExceptionType, index: int = 0) -> uuid.UUID:
        sku = self.scenarios[exception_type.value][index]
        return self.exception_for(exception_type, EntityType.PRODUCT, self.product(sku).id)

    def order_exception(self, exception_type: ExceptionType, index: int = 0) -> uuid.UUID:
        number = self.scenarios[exception_type.value][index]
        return self.exception_for(exception_type, EntityType.ORDER, self.order(number).id)

    # ------------------------------------------------------------------ imports
    def run_import(
        self, email: str, import_type: ImportType, filename: str, content: bytes, minutes: int
    ) -> None:
        """Upload, validate and apply a CSV exactly as the imports endpoints do."""
        ctx = self.ctx(email)
        now = self.at(minutes)
        upload = parsing.read_upload(io.BytesIO(content), filename)
        detail = imports.create_import(
            self.db, ctx, import_type=import_type, upload=upload, now=now
        )
        if detail.status is not ImportStatus.VALIDATED or detail.summary.rows_with_errors:
            raise DemoHistoryError(f"{filename} did not validate: {detail.summary}")
        # Record-keeping columns default to the database clock; align the upload time with the
        # scripted timeline so the import history reads in order.
        self.db.execute(update(DataImport).where(DataImport.id == detail.id).values(created_at=now))
        self.db.commit()

        def evaluate(
            db: Session,
            *,
            store_id: uuid.UUID,
            import_id: uuid.UUID,
            as_of: datetime,
            triggered_by: uuid.UUID | None,
        ) -> uuid.UUID:
            run = engine.run_evaluation(
                db,
                store_id,
                trigger=EvaluationTrigger.IMPORT,
                as_of=as_of,
                triggered_by=triggered_by,
                import_id=import_id,
            )
            if run.status is not EvaluationStatus.SUCCEEDED:
                raise DemoHistoryError(f"Import evaluation {run.status.value}: {run.error}")
            self.result.evaluations.append(dict(run.counts))
            return run.id

        applied = imports.apply_import(
            self.db,
            ctx,
            detail.id,
            mode=ImportMode.STRICT,
            confirm_skipped_rows=None,
            idempotency_key=None,
            now=now,
            on_applied=evaluate,
        )
        if applied.status is not ImportStatus.COMPLETED or applied.evaluation_run_id is None:
            raise DemoHistoryError(f"{filename} was not applied and evaluated: {applied.status}")
        self.result.imports.append(filename)

    # ------------------------------------------------------------------ the scripted morning
    def play(self) -> HistorySummary:
        db = self.db
        manager, marcus, sofia = self.ctx(MANAGER), self.ctx(STAFF_MARCUS), self.ctx(STAFF_SOFIA)
        oversold = self.product_exception(ExceptionType.INVENTORY_OVERSOLD)
        out_of_stock = self.product_exception(ExceptionType.INVENTORY_OUT_OF_STOCK)
        overdue = self.order_exception(ExceptionType.ORDER_FULFILLMENT_OVERDUE, index=-1)
        stalled_number = self.scenarios[ExceptionType.ORDER_STALLED_AFTER_PAYMENT.value][0]
        stalled = self.order_exception(ExceptionType.ORDER_STALLED_AFTER_PAYMENT)
        refund_number = self.scenarios[ExceptionType.ORDER_REFUND_PENDING.value][0]
        refund = self.order_exception(ExceptionType.ORDER_REFUND_PENDING)
        restock_sku = self.scenarios[ExceptionType.INVENTORY_BELOW_REORDER_POINT.value][1]
        restock = self.product_exception(ExceptionType.INVENTORY_BELOW_REORDER_POINT, index=1)
        rounding = self.order_exception(ExceptionType.DATA_ORDER_TOTAL_MISMATCH, index=1)

        exceptions.assign(
            db,
            manager,
            oversold,
            assignee_id=self.user_id(STAFF_MARCUS),
            expected_version=None,
            now=self.at(12),
        )
        exceptions.assign(
            db,
            manager,
            out_of_stock,
            assignee_id=self.user_id(STAFF_SOFIA),
            expected_version=None,
            now=self.at(15),
        )
        exceptions.acknowledge(db, marcus, oversold, expected_version=None, now=self.at(22))

        exceptions.start(db, marcus, overdue, expected_version=None, now=self.at(35))
        exceptions.add_note(
            db,
            marcus,
            overdue,
            expected_version=None,
            now=self.at(41),
            body="Picked and packed except one item, which is on a pallet that has not been put "
            "away yet. Shipping as soon as receiving clears it.",
        )

        exceptions.start(db, sofia, stalled, expected_version=None, now=self.at(50))

        exceptions.start(db, sofia, refund, expected_version=None, now=self.at(65))

        exceptions.start(db, marcus, restock, expected_version=None, now=self.at(100))
        exceptions.add_note(
            db,
            marcus,
            restock,
            expected_version=None,
            now=self.at(104),
            body="The supplier agreed to a rush delivery this morning.",
        )
        product = self.product(restock_sku)
        received = product.reorder_quantity or product.reorder_point * 3
        exceptions.resolve(
            db,
            marcus,
            restock,
            resolution_code=ResolutionCode.STOCK_REPLENISHED,
            resolution_note=f"Rush delivery of {received} units received and shelved.",
            expected_version=None,
            now=self.at(120),
        )
        self.run_import(
            MANAGER,
            ImportType.INVENTORY_ADJUSTMENTS,
            "inventory_adjustments_rush_delivery.csv",
            _csv(
                ["reference", "sku", "adjustment_type", "quantity", "occurred_at", "note"],
                [
                    [
                        f"RUSH-{self.at(115):%m%d}-{restock_sku}",
                        restock_sku,
                        "RECEIPT",
                        str(received),
                        _iso(self.at(115)),
                        "Rush delivery from the supplier",
                    ]
                ],
            ),
            minutes=150,
        )

        exceptions.dismiss(
            db,
            manager,
            rounding,
            dismissal_reason=DismissalReason.ACCEPTED_RISK,
            note="Rounding difference from the marketplace's tax calculation. It is below our "
            "one-dollar tolerance, so finance accepts it.",
            expected_version=None,
            now=self.at(165),
        )
        exceptions.resolve(
            db,
            sofia,
            stalled,
            resolution_code=ResolutionCode.FIXED_IN_SOURCE_SYSTEM,
            resolution_note="The payment webhook had failed, so the order never reached the "
            "warehouse queue. Released it manually in the shop admin.",
            expected_version=None,
            now=self.at(180),
        )

        exceptions.resolve(
            db,
            sofia,
            refund,
            resolution_code=ResolutionCode.REFUND_ISSUED,
            resolution_note="Refund issued in the payment provider for the full amount; the "
            "customer was notified by email.",
            expected_version=None,
            now=self.at(200),
        )

        stalled_order = self.order(stalled_number)
        refund_order = self.order(refund_number)
        header = [
            "order_number",
            "placed_at",
            "status",
            "payment_status",
            "fulfillment_status",
            "paid_at",
            "cancelled_at",
            "currency",
            "subtotal",
            "total",
        ]
        rows = [
            [
                stalled_order.order_number,
                _iso(stalled_order.placed_at),
                "PROCESSING",
                "PAID",
                "IN_PROGRESS",
                _iso(stalled_order.paid_at) if stalled_order.paid_at else "",
                "",
                stalled_order.currency,
                str(stalled_order.subtotal),
                str(stalled_order.total),
            ],
            [
                refund_order.order_number,
                _iso(refund_order.placed_at),
                refund_order.status.value,
                refund_order.payment_status.value,
                refund_order.fulfillment_status.value,
                _iso(refund_order.paid_at) if refund_order.paid_at else "",
                _iso(refund_order.cancelled_at) if refund_order.cancelled_at else "",
                refund_order.currency,
                str(refund_order.subtotal),
                str(refund_order.total),
            ],
        ]
        self.run_import(
            MANAGER, ImportType.ORDERS, "orders_export_morning.csv", _csv(header, rows), minutes=240
        )
        exceptions.add_note(
            db,
            manager,
            refund,
            expected_version=None,
            now=self.at(250),
            body="The latest payment export still shows this order as paid. Please check "
            "whether the refund failed or is still pending at the provider.",
        )
        return self.result


def play_history(db: Session, summary: DemoSummary, *, start: datetime) -> HistorySummary:
    """Run the scripted team activity. Requires one evaluation at ``start`` first."""
    return _History(db, summary, start).play()
