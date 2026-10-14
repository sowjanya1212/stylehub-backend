"""Checkout + Stripe payments.

Flow:
 1. POST /orders/checkout        -> creates a *pending* order from the cart and a
                                    Stripe PaymentIntent; returns client_secret.
 2. Frontend confirms the payment with Stripe Elements using client_secret.
 3. Stripe calls POST /orders/webhook  -> we mark the order paid/failed.
    (POST /orders/{id}/confirm is a fallback that asks Stripe directly - handy
     in local development if you are not running the webhook listener.)
"""
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import CartItem, Order, OrderItem, OrderStatus, Product, User
from ..schemas import CheckoutOut, OrderOut

stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter(prefix="/orders", tags=["Orders & Payments"])


# ---------- helpers ----------
def mark_order_paid(db: Session, order: Order) -> None:
    """Idempotent: safe to call twice (webhook + confirm may both fire)."""
    if order.status == OrderStatus.paid:
        return
    order.status = OrderStatus.paid
    for item in order.items:
        product = db.get(Product, item.product_id)
        if product:
            product.stock = max(0, product.stock - item.quantity)
    # Empty the buyer's cart now that they've paid.
    for cart_item in db.scalars(select(CartItem).where(CartItem.user_id == order.user_id)).all():
        db.delete(cart_item)
    db.commit()


def mark_order_failed(db: Session, order: Order) -> None:
    if order.status == OrderStatus.pending:
        order.status = OrderStatus.failed
        db.commit()


def _get_order_by_intent(db: Session, intent_id: str) -> Order | None:
    return db.scalar(select(Order).where(Order.stripe_payment_intent_id == intent_id))


# ---------- endpoints ----------
@router.post("/checkout", response_model=CheckoutOut, status_code=status.HTTP_201_CREATED)
def checkout(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cart_items = db.scalars(select(CartItem).where(CartItem.user_id == user.id)).all()
    if not cart_items:
        raise HTTPException(400, "Your cart is empty")

    # Validate stock and compute the total on the SERVER (never trust the client).
    total = 0
    order_items = []
    for ci in cart_items:
        if ci.quantity > ci.product.stock:
            raise HTTPException(400, f"'{ci.product.name}' only has {ci.product.stock} in stock")
        total += ci.product.price_cents * ci.quantity
        order_items.append(
            OrderItem(
                product_id=ci.product.id,
                product_name=ci.product.name,
                unit_price_cents=ci.product.price_cents,
                quantity=ci.quantity,
            )
        )
    # Stripe's minimum charge is about 50 cents.
    if total < 50:
        raise HTTPException(400, "Order total is below the minimum payable amount")

    order = Order(
        user_id=user.id,
        total_cents=total,
        currency=settings.STRIPE_CURRENCY,
        status=OrderStatus.pending,
        items=order_items,
    )
    db.add(order)
    db.flush()  # gives us order.id without committing yet

    try:
        intent = stripe.PaymentIntent.create(
            amount=total,
            currency=settings.STRIPE_CURRENCY,
            automatic_payment_methods={"enabled": True},
            metadata={"order_id": str(order.id), "user_id": str(user.id)},
            receipt_email=user.email,
        )
    except stripe.StripeError as exc:
        db.rollback()
        raise HTTPException(502, f"Payment provider error: {exc.user_message or 'try again later'}")

    order.stripe_payment_intent_id = intent.id
    db.commit()

    return CheckoutOut(
        order_id=order.id,
        client_secret=intent.client_secret,
        publishable_key=settings.STRIPE_PUBLISHABLE_KEY,
        total_cents=total,
        currency=settings.STRIPE_CURRENCY,
    )


@router.post("/webhook", include_in_schema=True)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Called by Stripe (not by your frontend). Signature is verified."""
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(400, "Invalid webhook signature")

    obj = event["data"]["object"]
    if event["type"] in ("payment_intent.succeeded", "payment_intent.payment_failed"):
        order = _get_order_by_intent(db, obj["id"])
        if order:
            if event["type"] == "payment_intent.succeeded":
                mark_order_paid(db, order)
            else:
                mark_order_failed(db, order)
    return {"received": True}


@router.post("/{order_id}/confirm", response_model=OrderOut)
def confirm_payment(
    order_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Call this after Stripe Elements finishes. Asks Stripe for the real status."""
    order = db.scalar(select(Order).where(Order.id == order_id, Order.user_id == user.id))
    if not order or not order.stripe_payment_intent_id:
        raise HTTPException(404, "Order not found")
    try:
        intent = stripe.PaymentIntent.retrieve(order.stripe_payment_intent_id)
    except stripe.StripeError:
        raise HTTPException(502, "Could not verify payment with Stripe")

    if intent.status == "succeeded":
        mark_order_paid(db, order)
    elif intent.status == "requires_payment_method" and intent.last_payment_error:
        mark_order_failed(db, order)
    db.refresh(order)
    return order


@router.get("", response_model=list[OrderOut])
def order_history(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc())
    return db.scalars(stmt).all()


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    order = db.scalar(select(Order).where(Order.id == order_id, Order.user_id == user.id))
    if not order:
        raise HTTPException(404, "Order not found")
    return order
