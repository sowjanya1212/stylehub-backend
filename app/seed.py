"""Run once:  python -m app.seed   -> fills the products table with sample data."""
from sqlalchemy import select

from .database import Base, SessionLocal, engine
from .models import Product

PRODUCTS = [
    ("Classic White T-Shirt", "100% cotton regular-fit tee.", 1999, "men", 50),
    ("Slim Fit Blue Jeans", "Stretch denim, mid-rise.", 4999, "men", 30),
    ("Leather Biker Jacket", "Genuine leather, zip front.", 12999, "men", 10),
    ("Floral Summer Dress", "Lightweight knee-length dress.", 5999, "women", 25),
    ("High-Waist Trousers", "Tailored office-ready trousers.", 4499, "women", 20),
    ("Knit Cardigan", "Soft oversized knit cardigan.", 3999, "women", 15),
    ("Canvas Sneakers", "Everyday low-top sneakers.", 3499, "shoes", 40),
    ("Running Shoes", "Breathable mesh, cushioned sole.", 7999, "shoes", 18),
    ("Leather Belt", "Brown full-grain leather belt.", 1599, "accessories", 60),
    ("Aviator Sunglasses", "UV400 metal-frame sunglasses.", 2499, "accessories", 35),
]


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.scalar(select(Product).limit(1)):
            print("Products already exist - skipping.")
            return
        for i, (name, desc, price, cat, stock) in enumerate(PRODUCTS, start=1):
            db.add(Product(
                name=name, description=desc, price_cents=price, category=cat, stock=stock,
                image_url=f"https://picsum.photos/seed/stylehub{i}/400/500",
            ))
        db.commit()
        print(f"Seeded {len(PRODUCTS)} products.")


if __name__ == "__main__":
    seed()
