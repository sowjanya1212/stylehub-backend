from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401  (makes sure tables are registered)
from .config import settings
from .database import Base, engine
from .routers import auth, cart, orders, products


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)  # creates tables if they don't exist
    yield


app = FastAPI(title="StyleHub - Fashion Mini Store API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(cart.router)
app.include_router(orders.router)


@app.get("/", tags=["Health"])
def health():
    return {"status": "ok", "app": "StyleHub API"}
