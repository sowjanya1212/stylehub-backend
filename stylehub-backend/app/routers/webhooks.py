import logging

import stripe
from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import select

from app.config import get_settings
from app.deps import DbSession
from app.models import Order
from app.services import payments

logger = logging.getLogger("stylehub.webhooks")
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: DbSession,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
):
    """Stripe -> backend. Signature-verified; the source of truth for payments."""
    secret = get_settings().stripe_webhook_secret
    if not secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Webhook not configured")
    if not stripe_signature:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Missing Stripe-Signature header")

    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, secret)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid payload")
    except stripe.SignatureVerificationError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    event_type = event["type"]
    if event_type in (
        "payment_intent.succeeded",
        "payment_intent.payment_failed",
        "payment_intent.canceled",
    ):
        intent = event["data"]["object"]
        order = db.scalar(select(Order).where(Order.stripe_payment_intent_id == intent["id"]))
        if order is None:
            logger.warning("Webhook %s for unknown PaymentIntent %s", event_type, intent["id"])
        elif event_type == "payment_intent.succeeded":
            payments.mark_paid(db, order, paid_amount=intent.get("amount"))
        elif event_type == "payment_intent.payment_failed":
            payments.mark_failed(db, order)
        else:
            payments.mark_cancelled(db, order)

    # Always 200 for verified events so Stripe doesn't keep retrying ones we ignore.
    return {"received": True}
