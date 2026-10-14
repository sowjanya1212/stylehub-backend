from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select

from app.deps import DbSession
from app.models import Product
from app.schemas import ProductList, ProductOut

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=ProductList)
def list_products(
    db: DbSession,
    q: str | None = Query(None, max_length=100, description="Search in name/description"),
    category: str | None = Query(None, max_length=80),
    sort: Literal["newest", "price_asc", "price_desc", "name"] = "newest",
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
):
    stmt = select(Product).where(Product.is_active.is_(True))

    if q:
        term = q.strip().lower()
        stmt = stmt.where(
            or_(
                func.lower(Product.name).contains(term, autoescape=True),
                func.lower(Product.description).contains(term, autoescape=True),
            )
        )
    if category:
        stmt = stmt.where(func.lower(Product.category) == category.strip().lower())

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    order_by = {
        "newest": Product.id.desc(),
        "price_asc": Product.price_cents.asc(),
        "price_desc": Product.price_cents.desc(),
        "name": Product.name.asc(),
    }[sort]

    items = db.scalars(
        stmt.order_by(order_by, Product.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ProductList(items=items, total=total, page=page, page_size=page_size)


@router.get("/categories", response_model=list[str])
def list_categories(db: DbSession):
    rows = db.scalars(
        select(Product.category)
        .where(Product.is_active.is_(True))
        .distinct()
        .order_by(Product.category)
    ).all()
    return list(rows)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: DbSession):
    product = db.get(Product, product_id)
    if product is None or not product.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product
