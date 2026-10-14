"""Demo catalogue. Run manually with:  python -m app.seed"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
from app.models import Product

_IMG = "https://picsum.photos/seed/stylehub-{}/600/800"

PRODUCTS = [
    ("Classic White Tee", "Soft 100% cotton crew-neck t-shirt.", 1999, "Men", 80),
    ("Slim Fit Denim Jeans", "Stretch denim, mid-rise, slim fit.", 5999, "Men", 45),
    ("Oxford Button-Down Shirt", "Wrinkle-resistant oxford cotton shirt.", 4499, "Men", 35),
    ("Hooded Sweatshirt", "Fleece-lined pullover hoodie.", 5499, "Men", 50),
    ("Floral Summer Dress", "Lightweight midi dress with floral print.", 6999, "Women", 30),
    ("High-Waist Skinny Jeans", "Flattering high-rise stretch jeans.", 5799, "Women", 40),
    ("Knit Cardigan", "Cozy open-front cardigan in soft knit.", 4999, "Women", 25),
    ("Satin Blouse", "Elegant satin blouse with relaxed sleeves.", 3999, "Women", 28),
    ("Leather Belt", "Genuine leather belt with brushed buckle.", 2499, "Accessories", 60),
    ("Canvas Tote Bag", "Durable everyday tote with inner pocket.", 2999, "Accessories", 70),
    ("Aviator Sunglasses", "UV400 protection, metal frame.", 3499, "Accessories", 55),
    ("White Leather Sneakers", "Minimal low-top sneakers.", 8999, "Footwear", 20),
]


def seed_products(db: Session) -> int:
    if (db.scalar(select(func.count(Product.id))) or 0) > 0:
        return 0
    for i, (name, desc, price, cat, stock) in enumerate(PRODUCTS, start=1):
        db.add(
            Product(
                name=name,
                description=desc,
                price_cents=price,
                category=cat,
                stock=stock,
                image_url=_IMG.format(i),
            )
        )
    db.commit()
    return len(PRODUCTS)


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        print(f"Seeded {seed_products(session)} products")
