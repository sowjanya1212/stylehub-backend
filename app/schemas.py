"""Pydantic schemas: validation of incoming data and shape of responses."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .models import OrderStatus


# ---------- Auth ----------
class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    # bcrypt only supports passwords up to 72 bytes, so we cap at 72.
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one letter and one number")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: EmailStr
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Products ----------
class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str
    price_cents: int
    category: str
    image_url: str
    stock: int


# ---------- Cart ----------
class CartItemAdd(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1, le=20)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1, le=20)


class CartItemOut(BaseModel):
    product: ProductOut
    quantity: int
    line_total_cents: int


class CartOut(BaseModel):
    items: list[CartItemOut]
    total_items: int
    total_cents: int


# ---------- Orders ----------
class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_id: int
    product_name: str
    unit_price_cents: int
    quantity: int


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    total_cents: int
    currency: str
    status: OrderStatus
    created_at: datetime
    items: list[OrderItemOut]


class CheckoutOut(BaseModel):
    order_id: int
    client_secret: str          # frontend gives this to Stripe Elements
    publishable_key: str
    total_cents: int
    currency: str
