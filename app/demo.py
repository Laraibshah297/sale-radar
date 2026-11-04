"""Demo data for trying the product. Stores are FICTIONAL (domains end in
.example) and prices are made up; remove with a fresh database before launch."""
import random
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from .importer import import_rows
from .models import Category, Offer, PriceHistory, Retailer, now

STORES = [
    ("TechBazaar (demo)", "techbazaar.example", "Karachi", True, "Nationwide"),
    ("MobileHub (demo)", "mobilehub.example", "Lahore", True, "Nationwide"),
    ("GadgetGhar (demo)", "gadgetghar.example", "Islamabad", True, "Islamabad, Rawalpindi, Lahore"),
    ("PhoneWala (demo)", "phonewala.example", "Karachi", False, "Karachi"),
]
# brand, title, model, category, [(storage, ram, base price)], warranty
PRODUCTS = [
    ("Samsung", "Samsung Galaxy A55 5G", "SM-A556E", "Mobile Phones", [("128GB", "8GB", 109999), ("256GB", "8GB", 124999)]),
    ("Samsung", "Samsung Galaxy S24", "SM-S921B", "Mobile Phones", [("256GB", "8GB", 239999)]),
    ("Samsung", "Samsung Galaxy A15", "SM-A155F", "Mobile Phones", [("128GB", "6GB", 46999)]),
    ("Apple", "Apple iPhone 15", "MTP03", "Mobile Phones", [("128GB", "", 289999), ("256GB", "", 324999)]),
    ("Apple", "Apple iPhone 13", "MLPF3", "Mobile Phones", [("128GB", "", 189999)]),
    ("Xiaomi", "Xiaomi Redmi Note 13", "23129RAA4G", "Mobile Phones", [("128GB", "8GB", 52999), ("256GB", "8GB", 59999)]),
    ("Xiaomi", "Xiaomi Redmi 13C", "23100RN82L", "Mobile Phones", [("128GB", "6GB", 32999)]),
    ("Infinix", "Infinix Hot 40 Pro", "X6837", "Mobile Phones", [("256GB", "8GB", 44999)]),
    ("Tecno", "Tecno Spark 20 Pro", "KJ6", "Mobile Phones", [("256GB", "8GB", 41999)]),
    ("Vivo", "Vivo Y36", "V2247", "Mobile Phones", [("256GB", "8GB", 59999)]),
    ("Oppo", "Oppo Reno 11F 5G", "CPH2603", "Mobile Phones", [("256GB", "8GB", 89999)]),
    ("Realme", "Realme C67", "RMX3890", "Mobile Phones", [("128GB", "8GB", 45999)]),
    ("HP", "HP 250 G10 Laptop Core i5 13th Gen", "8A5D9EA", "Laptops", [("512GB", "8GB", 164999)]),
    ("Lenovo", "Lenovo IdeaPad Slim 3 Ryzen 5", "82XQ00BDPS", "Laptops", [("512GB", "8GB", 149999)]),
    ("Dell", "Dell Inspiron 3520 Core i7", "INS3520-I7", "Laptops", [("512GB", "16GB", 214999)]),
    ("Apple", "Apple MacBook Air M2 13-inch", "MLY33", "Laptops", [("256GB", "8GB", 299999)]),
    ("Audionic", "Audionic Airbud 550 Wireless Earbuds", "AIRBUD-550", "Accessories", [("", "", 5499)]),
    ("Samsung", "Samsung Galaxy Buds FE", "SM-R400N", "Accessories", [("", "", 21999)]),
    ("Anker", "Anker PowerCore 20000mAh Power Bank", "A1384", "Accessories", [("", "", 9999)]),
    ("Xiaomi", "Xiaomi Redmi Watch 4", "M2315W1", "Accessories", [("", "", 21999)]),
]
WARRANTY = ["1 Year Official Warranty", "1 Year Official Warranty", "Shop warranty 6 months", "1 Year Official Warranty"]


def seed(db):
    if db.scalar(select(Retailer).where(Retailer.domain == STORES[0][1])):
        return "demo data already loaded"
    rnd = random.Random(42)
    retailers = []
    for name, dom, city, verified, regions in STORES:
        r = Retailer(name=name, slug=dom.split(".")[0], domain=dom, city=city, status="active", verified=verified,
                     verification_notes="DEMO DATA: not a real store" if verified else None, delivery_regions=regions,
                     phone="021-0000000", email=f"sales@{dom}", feed_method="csv",
                     permission_reference="Demo data", description="Fictional demo store for testing the product.",
                     plan="pro" if dom.startswith("techbazaar") else "free")
        db.add(r)
        retailers.append(r)
    db.flush()
    for name, slug, specs in [("Mobile Phones", "mobile-phones", ["storage", "ram"]),
                              ("Laptops", "laptops", ["storage", "ram"]), ("Accessories", "accessories", [])]:
        db.add(Category(name=name, slug=slug, filter_specs=specs))
    db.flush()
    for ri, r in enumerate(retailers):
        rows = []
        for brand, title, model, cat, variants in PRODUCTS:
            for storage, ram, base in variants:
                if rnd.random() < 0.2:
                    continue  # not every store stocks everything
                price = int(base * rnd.uniform(0.95, 1.06) / 100) * 100 - 1
                ship = rnd.choice(["0", "0", "250", "350", ""])
                rows.append({
                    "product_url": f"https://{r.domain}/p/{model.lower()}-{storage.lower() or 'std'}",
                    "retailer_sku": f"{model}-{storage or 'STD'}", "brand": brand, "model_number": model,
                    "product_title": f"{title} {storage} {ram + ' RAM' if ram else ''}".strip(),
                    "category": cat, "storage_capacity": storage, "ram": ram,
                    "region": "PTA Approved" if cat == "Mobile Phones" else "",
                    "price": str(price), "shipping_cost": ship,
                    "stock_status": "out_of_stock" if rnd.random() < 0.08 else "in_stock",
                    "warranty_type": WARRANTY[ri], "condition": "new",
                })
        import_rows(db, rows, source="demo", retailer=r, filename="demo", allow_create=True)
    # back-fill 45 days of plausible price history so charts and deal labels work
    for o in db.scalars(select(Offer)):
        db.query(PriceHistory).filter(PriceHistory.offer_id == o.id).delete()
        price = float(o.price) * rnd.uniform(1.02, 1.10)
        for d in range(45, 0, -3):
            price = max(float(o.price) * 0.97, price * rnd.uniform(0.985, 1.01))
            db.add(PriceHistory(offer_id=o.id, price=Decimal(int(price / 100) * 100 - 1),
                                shipping_cost=o.shipping_cost, stock_status="in_stock",
                                captured_at=now() - timedelta(days=d)))
        db.add(PriceHistory(offer_id=o.id, price=o.price, shipping_cost=o.shipping_cost,
                            stock_status=o.stock_status, captured_at=now() - timedelta(hours=2)))
        o.checked_at = now() - timedelta(hours=rnd.choice([1, 3, 6, 20, 60]))
    db.commit()
    n = db.scalar(select(__import__("sqlalchemy").func.count()).select_from(Offer))
    return f"demo data loaded: {len(retailers)} fictional stores, {len(PRODUCTS)} products, {n} offers"
