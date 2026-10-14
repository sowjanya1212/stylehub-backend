import logging

import stripe
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.config import get_settings
from app.deps import CurrentUser, DbSession
from app.models import CartItem, Order, OrderItem, OrderStatus
from app.schemas import CheckoutOut, OrderOut
from app.services import payments

logger = logging.getLogger("stylehub.orders")
router = APIRouter(prefix="/orders", tags=["Orders & Payments"])


def _get_user_order(db, user_id: int, order_id: int) -> Order:
    order = db.scalar(select(Order).where(Order.id == order_id, Order.user_id == user_id))
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


@router.post("/checkout", response_model=CheckoutOut, status_code=status.HTTP_201_CREATED)
def checkout(db: DbSession, user: CurrentUser):
    """Turn the current cart into a pending order and create a Stripe PaymentIntent.

    The frontend uses the returned `client_secret` with Stripe Elements.
    """
    settings = get_settings()
    if not payments.stripe_configured():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="Payments are not configured"
        )

    cart_items = db.scalars(
        select(CartItem).where(CartItem.user_id == user.id).order_by(CartItem.id)
    ).all()
    if not cart_items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Your cart is empty")

    # Re-validate against current product data (price, availability, stock).
    for ci in cart_items:
        p = ci.product
        if not p.is_active:
            raise HTTPException(400, detail=f"'{p.name}' is no longer available")
        if ci.quantity > p.stock:
            raise HTTPException(400, detail=f"Only {p.stock} unit(s) of '{p.name}' in stock")

    total_cents = sum(ci.line_total_cents for ci in cart_items)
    if total_cents <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid order total")

    order = Order(
        user_id=user.id,
        total_cents=total_cents,
        currency=settings.currency.lower(),
        status=OrderStatus.PENDING,
    )
    for ci in cart_items:
        order.items.append(
            OrderItem(
                product_id=ci.product_id,
                product_name=ci.product.name,
                unit_price_cents=ci.product.price_cents,
                quantity=ci.quantity,
            )
        )
    db.add(order)
    db.flush()  # assigns order.id

    try:
        intent = payments.create_payment_intent(order)
    except stripe.StripeError:
        db.rollback()  # do not keep an order that has no PaymentIntent
        raise

    order.stripe_payment_intent_id = intent["id"]
    db.commit()
    db.refresh(order)

    return CheckoutOut(
        order=OrderOut.model_validate(order),
        client_secret=intent["client_secret"],
        publishable_key=settings.stripe_publishable_key,
    )


@router.post("/{order_id}/confirm", response_model=OrderOut)
def confirm_payment(order_id: int, db: DbSession, user: CurrentUser):
    """Call after `stripe.confirmPayment()` finishes on the frontend.

    Asks Stripe for the real PaymentIntent state (never trusts the client) and
    updates the order. The webhook does the same thing server-side, so this is
    mainly for instant UI feedback and local development.
    """
    order = _get_user_order(db, user.id, order_id)
    if order.stripe_payment_intent_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Order has no payment attached")
    if order.status == OrderStatus.PAID:
        return order

    intent = payments.retrieve_payment_intent(order.stripe_payment_intent_id)
    return payments.sync_order_with_intent(db, order, intent)


@router.get("", response_model=list[OrderOut])
def list_orders(db: DbSession, user: CurrentUser):
    """Order history for the logged-in user (newest first)."""
    return db.scalars(
        select(Order)
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc(), Order.id.desc())
    ).all()


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: DbSession, user: CurrentUser):
    return _get_user_order(db, user.id, order_id)
