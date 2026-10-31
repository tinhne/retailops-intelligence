"""SQL predicates for order rules, shared by read queries, analytics and the rule engine."""

from sqlalchemy import ColumnElement, and_, not_

from app.domains.orders.models import FulfillmentStatus, Order, OrderStatus
from app.domains.orders.state import SALES_EXCLUDED_STATUSES


def counts_as_sale() -> ColumnElement[bool]:
    """BR-150: the order counts toward sales velocity.

    Excludes CANCELLED, PAYMENT_FAILED, CREATED and PAYMENT_PENDING orders, and orders refunded
    before anything shipped (status REFUNDED with fulfillment UNFULFILLED).
    """
    return and_(
        Order.status.not_in(SALES_EXCLUDED_STATUSES),
        not_(
            and_(
                Order.status == OrderStatus.REFUNDED,
                Order.fulfillment_status == FulfillmentStatus.UNFULFILLED,
            )
        ),
    )
