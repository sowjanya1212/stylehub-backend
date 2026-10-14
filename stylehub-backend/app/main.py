import logging
from contextlib import asynccontextmanager

import stripe
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.routers import auth, cart, orders, products, webhooks
from app.seed import seed_products

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stylehub")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    if settings.seed_products:
        with SessionLocal() as db:
            count = seed_products(db)
            if count:
                logger.info("Seeded %s demo products", count)
    yield


app = FastAPI(
    title=settings.app_name,
    description="Backend for StyleHub - Fashion Mini Store",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(stripe.StripeError)
async def stripe_error_handler(request: Request, exc: stripe.StripeError):
    logger.exception("Stripe error: %s", exc)
    return JSONResponse(
        status_code=502,
        content={"detail": "Payment provider error. Please try again."},
    )


app.include_router(auth.router)
app.include_router(products.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(webhooks.router)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
