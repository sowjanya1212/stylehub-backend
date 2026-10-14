from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Product
from ..schemas import ProductOut

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=list[ProductOut])
def list_products(
    category: str | None = None,
    search: str | None = Query(default=None, max_length=100),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    stmt = select(Product)
    if category:
        stmt = stmt.where(Product.category == category)
    if search:
        stmt = stmt.where(Product.name.ilike(f"%{search}%"))
    stmt = stmt.order_by(Product.id).offset(skip).limit(limit)
    return db.scalars(stmt).all()


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    return product
