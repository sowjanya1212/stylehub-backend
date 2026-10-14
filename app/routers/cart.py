from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import CartItem, Product, User
from ..schemas import CartItemAdd, CartItemOut, CartItemUpdate, CartOut

router = APIRouter(prefix="/cart", tags=["Cart"])


def build_cart(db: Session, user: User) -> CartOut:
    rows = db.scalars(
        select(CartItem).where(CartItem.user_id == user.id).order_by(CartItem.id)
    ).all()
    items = [
        CartItemOut(
            product=row.product,
            quantity=row.quantity,
            line_total_cents=row.product.price_cents * row.quantity,
        )
        for row in rows
    ]
    return CartOut(
        items=items,
        total_items=sum(i.quantity for i in items),
        total_cents=sum(i.line_total_cents for i in items),
    )


def _get_item(db: Session, user: User, product_id: int) -> CartItem:
    item = db.scalar(
        select(CartItem).where(CartItem.user_id == user.id, CartItem.product_id == product_id)
    )
    if not item:
        raise HTTPException(404, "Item not found in your cart")
    return item


@router.get("", response_model=CartOut)
def view_cart(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return build_cart(db, user)


@router.post("/items", response_model=CartOut, status_code=status.HTTP_201_CREATED)
def add_to_cart(
    data: CartItemAdd, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    product = db.get(Product, data.product_id)
    if not product:
        raise HTTPException(404, "Product not found")

    item = db.scalar(
        select(CartItem).where(CartItem.user_id == user.id, CartItem.product_id == product.id)
    )
    new_qty = data.quantity + (item.quantity if item else 0)
    if new_qty > product.stock:
        raise HTTPException(400, f"Only {product.stock} unit(s) of '{product.name}' in stock")

    if item:
        item.quantity = new_qty
    else:
        db.add(CartItem(user_id=user.id, product_id=product.id, quantity=data.quantity))
    db.commit()
    return build_cart(db, user)


@router.patch("/items/{product_id}", response_model=CartOut)
def update_quantity(
    product_id: int,
    data: CartItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = _get_item(db, user, product_id)
    if data.quantity > item.product.stock:
        raise HTTPException(400, f"Only {item.product.stock} unit(s) in stock")
    item.quantity = data.quantity
    db.commit()
    return build_cart(db, user)


@router.delete("/items/{product_id}", response_model=CartOut)
def remove_from_cart(
    product_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    db.delete(_get_item(db, user, product_id))
    db.commit()
    return build_cart(db, user)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def clear_cart(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    for item in db.scalars(select(CartItem).where(CartItem.user_id == user.id)).all():
        db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
