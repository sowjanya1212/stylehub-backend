import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import OrderStatus


# ---------- Auth ----------
class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Full name cannot be blank")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        # bcrypt only uses the first 72 BYTES of the password.
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes")
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("Password must contain at least one letter and one digit")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


# ---------- Products ----------
class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    price: float
    price_cents: int
    category: str
    image_url: str | None
    stock: int


class ProductList(BaseModel):
    items: list[ProductOut]
    total: int
    page: int
    page_size: int


# ---------- Cart ----------
class CartItemCreate(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(default=1, ge=1, le=99)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1, le=99)


class CartItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product: ProductOut
    quantity: int
    line_total_cents: int
    line_total: float


class CartOut(BaseModel):
    items: list[CartItemOut]
    total_items: int
    total_cents: int
    total: float


# ---------- Orders ----------
class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int | None
    product_name: str
    unit_price_cents: int
    quantity: int
    line_total_cents: int


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: OrderStatus
    total_cents: int
    total: float
    currency: str
    stripe_payment_intent_id: str | None
    created_at: datetime
    items: list[OrderItemOut]


class CheckoutOut(BaseModel):
    order: OrderOut
    client_secret: str
    publishable_key: str
