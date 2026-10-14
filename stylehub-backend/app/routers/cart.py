from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select

from app.deps import CurrentUser, DbSession
from app.models import CartItem, Product
from app.schemas import CartItemCreate, CartItemOut, CartItemUpdate, CartOut

router = APIRouter(prefix="/cart", tags=["Cart"])


def build_cart(db, user_id: int) -> CartOut:
    items = db.scalars(
        select(CartItem).where(CartItem.user_id == user_id).order_by(CartItem.id)
    ).all()
    total_cents = sum(i.line_total_cents for i in items)
    return CartOut(
        items=[CartItemOut.model_validate(i) for i in items],
        total_items=sum(i.quantity for i in items),
        total_cents=total_cents,
        total=total_cents / 100,
    )


def _get_active_product(db, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None or not product.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


def _check_stock(product: Product, quantity: int) -> None:
    if quantity > product.stock:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Only {product.stock} unit(s) of '{product.name}' in stock",
        )


def _get_cart_item(db, user_id: int, product_id: int) -> CartItem:
    item = db.scalar(
        select(CartItem).where(CartItem.user_id == user_id, CartItem.product_id == product_id)
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item not in cart")
    return item


@router.get("", response_model=CartOut)
def get_cart(db: DbSession, user: CurrentUser):
    return build_cart(db, user.id)


@router.post("/items", response_model=CartOut, status_code=status.HTTP_201_CREATED)
def add_to_cart(payload: CartItemCreate, db: DbSession, user: CurrentUser):
    """Add a product. If it is already in the cart the quantity is increased."""
    product = _get_active_product(db, payload.product_id)

    item = db.scalar(
        select(CartItem).where(CartItem.user_id == user.id, CartItem.product_id == product.id)
    )
    new_qty = payload.quantity + (item.quantity if item else 0)
    if new_qty > 99:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Maximum 99 units per item")
    _check_stock(product, new_qty)

    if item:
        item.quantity = new_qty
    else:
        db.add(CartItem(user_id=user.id, product_id=product.id, quantity=new_qty))
    db.commit()
    return build_cart(db, user.id)


@router.put("/items/{product_id}", response_model=CartOut)
def update_quantity(product_id: int, payload: CartItemUpdate, db: DbSession, user: CurrentUser):
    """Set the quantity of a cart item (use DELETE to remove it)."""
    item = _get_cart_item(db, user.id, product_id)
    _check_stock(item.product, payload.quantity)
    item.quantity = payload.quantity
    db.commit()
    return build_cart(db, user.id)


@router.delete("/items/{product_id}", response_model=CartOut)
def remove_from_cart(product_id: int, db: DbSession, user: CurrentUser):
    item = _get_cart_item(db, user.id, product_id)
    db.delete(item)
    db.commit()
    return build_cart(db, user.id)


@router.delete("", response_model=CartOut)
def clear_cart(db: DbSession, user: CurrentUser):
    db.execute(delete(CartItem).where(CartItem.user_id == user.id))
    db.commit()
    return build_cart(db, user.id)
