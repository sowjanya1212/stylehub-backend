"""Stripe + order-status helpers shared by the orders router and the webhook."""
import logging

import stripe
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import CartItem, Order, OrderStatus, Product

logger = logging.getLogger("stylehub.payments")


def stripe_configured() -> bool:
    return bool(get_settings().stripe_secret_key)


def _init_stripe() -> None:
    stripe.api_key = get_settings().stripe_secret_key


def create_payment_intent(order: Order):
    _init_stripe()
    return stripe.PaymentIntent.create(
        amount=order.total_cents,
        currency=order.currency,
        automatic_payment_methods={"enabled": True},
        metadata={"order_id": str(order.id), "user_id": str(order.user_id)},
        description=f"StyleHub order #{order.id}",
        idempotency_key=f"stylehub-order-{order.id}",
    )


def retrieve_payment_intent(payment_intent_id: str):
    _init_stripe()
    return stripe.PaymentIntent.retrieve(payment_intent_id)


def mark_paid(db: Session, order: Order, paid_amount: int | None = None) -> None:
    """Idempotent: safe to call from both the webhook and the confirm endpoint."""
    if order.status == OrderStatus.PAID:
        return
    if order.status == OrderStatus.CANCELLED:
        logger.warning("Payment received for cancelled order %s", order.id)
        return
    if paid_amount is not None and paid_amount != order.total_cents:
        logger.error(
            "Amount mismatch on order %s: paid=%s expected=%s",
            order.id, paid_amount, order.total_cents,
        )
        return

    order.status = OrderStatus.PAID

    # Decrement stock (never below zero).
    for item in order.items:
        if item.product_id is None:
            continue
        product = db.get(Product, item.product_id)
        if product is not None:
            product.stock = max(0, product.stock - item.quantity)

    # Empty the buyer's cart now that the purchase went through.
    db.execute(delete(CartItem).where(CartItem.user_id == order.user_id))
    db.commit()


def mark_failed(db: Session, order: Order) -> None:
    if order.status == OrderStatus.PENDING:
        order.status = OrderStatus.FAILED
        db.commit()


def mark_cancelled(db: Session, order: Order) -> None:
    if order.status in (OrderStatus.PENDING, OrderStatus.FAILED):
        order.status = OrderStatus.CANCELLED
        db.commit()


def sync_order_with_intent(db: Session, order: Order, intent) -> Order:
    """Map a Stripe PaymentIntent state onto our order status."""
    intent_status = intent["status"]
    if intent_status == "succeeded":
        mark_paid(db, order, paid_amount=intent.get("amount"))
    elif intent_status == "canceled":
        mark_cancelled(db, order)
    elif intent_status == "requires_payment_method" and intent.get("last_payment_error"):
        mark_failed(db, order)
    # 'processing' / 'requires_action' etc. -> remains pending
    db.refresh(order)
    return order
