"""Demo data for trying the product. Stores are FICTIONAL (domains end in
.example) and prices are made up; use a fresh database for production."""
import itertools
import random
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select

from .filters import CATEGORY_PRESETS
from .importer import import_rows
from .models import Category, Offer, PriceHistory, Retailer, now

# name, domain, city, verified, delivery, categories carried, warranty text
STORES = [
    ("TechBazaar (demo)", "techbazaar.example", "Karachi", True, "Nationwide",
     ["mobile-phones", "laptops", "tablets", "audio", "power", "smartwatches"], "1 Year Official Warranty"),
    ("MobileHub (demo)", "mobilehub.example", "Lahore", True, "Nationwide",
     ["mobile-phones", "tablets", "audio", "power", "smartwatches"], "1 Year Official Warranty"),
    ("GadgetGhar (demo)", "gadgetghar.example", "Islamabad", True, "Islamabad, Rawalpindi, Lahore",
     ["mobile-phones", "audio", "power", "smartwatches"], "Shop warranty 6 months"),
    ("PhoneWala (demo)", "phonewala.example", "Karachi", False, "Karachi",
     ["mobile-phones", "audio", "power"], "1 Year Official Warranty"),
    ("LaptopLane (demo)", "laptoplane.example", "Lahore", True, "Nationwide",
     ["laptops", "tablets"], "1 Year Official Warranty"),
    ("ElectroMart (demo)", "electromart.example", "Karachi", True, "Karachi, Hyderabad, Lahore",
     ["tvs", "air-conditioners"], "Official brand warranty"),
    ("CoolHome Appliances (demo)", "coolhome.example", "Faisalabad", False, "Punjab",
     ["tvs", "air-conditioners"], "Official brand warranty"),
    ("Libaas House (demo)", "libaashouse.example", "Lahore", True, "Nationwide",
     ["mens-clothing", "womens-clothing", "unstitched"], "7-day exchange"),
    ("StreetWear PK (demo)", "streetwear.example", "Karachi", True, "Nationwide",
     ["mens-clothing", "womens-clothing"], "14-day exchange"),
    ("Kapra Point (demo)", "kaprapoint.example", "Faisalabad", True, "Nationwide",
     ["unstitched", "womens-clothing"], "7-day exchange"),
    ("Joota Junction (demo)", "jootajunction.example", "Lahore", True, "Nationwide",
     ["shoes"], "30-day sole warranty"),
    ("Qadam Shoes (demo)", "qadam.example", "Sialkot", False, "Nationwide",
     ["shoes"], "7-day exchange"),
    ("Glow Beauty (demo)", "glowbeauty.example", "Karachi", True, "Nationwide",
     ["beauty"], "Authentic product guarantee"),
    ("Nikhar Store (demo)", "nikhar.example", "Lahore", False, "Lahore, Islamabad",
     ["beauty"], "Authentic product guarantee"),
]

M, W = "Men", "Women"
CLOTH = ["S", "M", "L", "XL", "XXL"]
SHOE_M = ["UK 7", "UK 8", "UK 9", "UK 10", "UK 11"]
SHOE_W = ["UK 4", "UK 5", "UK 6", "UK 7"]


def v(price, **attrs):
    return {"price": price, **attrs}


def grid(price, colours, sizes):
    return [v(price, colour=c, size=s) for c, s in itertools.product(colours, sizes)]


# category slug, brand, title, model, specs, variants
PRODUCTS = [
    # ---- phones
    ("mobile-phones", "Samsung", "Samsung Galaxy A55 5G", "SM-A556E",
     {"network": "5G", "screen_size": "6.6 inch", "refresh_rate": "120Hz", "battery": "5000 mAh", "main_camera": "50 MP", "processor": "Exynos 1480"},
     [v(109999, storage="128GB", ram="8GB", region="PTA Approved"), v(124999, storage="256GB", ram="8GB", region="PTA Approved")]),
    ("mobile-phones", "Samsung", "Samsung Galaxy S24", "SM-S921B",
     {"network": "5G", "screen_size": "6.2 inch", "refresh_rate": "120Hz", "battery": "4000 mAh", "main_camera": "50 MP", "processor": "Exynos 2400"},
     [v(239999, storage="256GB", ram="8GB", region="PTA Approved")]),
    ("mobile-phones", "Samsung", "Samsung Galaxy A15", "SM-A155F",
     {"network": "4G", "screen_size": "6.5 inch", "refresh_rate": "90Hz", "battery": "5000 mAh", "main_camera": "50 MP", "processor": "Helio G99"},
     [v(46999, storage="128GB", ram="6GB", region="PTA Approved")]),
    ("mobile-phones", "Apple", "Apple iPhone 15", "MTP03",
     {"network": "5G", "screen_size": "6.1 inch", "refresh_rate": "60Hz", "battery": "3349 mAh", "main_camera": "48 MP", "processor": "A16 Bionic"},
     [v(289999, storage="128GB", region="PTA Approved"), v(324999, storage="256GB", region="PTA Approved"),
      v(239999, storage="128GB", region="Non-PTA (JV)")]),
    ("mobile-phones", "Apple", "Apple iPhone 13", "MLPF3",
     {"network": "5G", "screen_size": "6.1 inch", "refresh_rate": "60Hz", "battery": "3240 mAh", "main_camera": "12 MP", "processor": "A15 Bionic"},
     [v(189999, storage="128GB", region="PTA Approved")]),
    ("mobile-phones", "Xiaomi", "Xiaomi Redmi Note 13", "23129RAA4G",
     {"network": "4G", "screen_size": "6.67 inch", "refresh_rate": "120Hz", "battery": "5000 mAh", "main_camera": "108 MP", "processor": "Snapdragon 685"},
     [v(52999, storage="128GB", ram="8GB", region="PTA Approved"), v(59999, storage="256GB", ram="8GB", region="PTA Approved")]),
    ("mobile-phones", "Infinix", "Infinix Hot 40 Pro", "X6837",
     {"network": "4G", "screen_size": "6.78 inch", "refresh_rate": "120Hz", "battery": "5000 mAh", "main_camera": "108 MP", "processor": "Helio G99"},
     [v(44999, storage="256GB", ram="8GB", region="PTA Approved")]),
    ("mobile-phones", "Tecno", "Tecno Spark 20 Pro", "KJ6",
     {"network": "4G", "screen_size": "6.78 inch", "refresh_rate": "120Hz", "battery": "5000 mAh", "main_camera": "108 MP", "processor": "Helio G99"},
     [v(41999, storage="256GB", ram="8GB", region="PTA Approved")]),
    ("mobile-phones", "Oppo", "Oppo Reno 11F 5G", "CPH2603",
     {"network": "5G", "screen_size": "6.7 inch", "refresh_rate": "120Hz", "battery": "5000 mAh", "main_camera": "64 MP", "processor": "Dimensity 7050"},
     [v(89999, storage="256GB", ram="8GB", region="PTA Approved")]),
    ("mobile-phones", "Vivo", "Vivo Y36", "V2247",
     {"network": "4G", "screen_size": "6.64 inch", "refresh_rate": "90Hz", "battery": "5000 mAh", "main_camera": "50 MP", "processor": "Snapdragon 680"},
     [v(59999, storage="256GB", ram="8GB", region="PTA Approved")]),
    # ---- laptops
    ("laptops", "HP", "HP 250 G10 Core i5 13th Gen", "8A5D9EA",
     {"processor": "Intel Core i5", "screen_size": "15.6 inch", "gpu": "Integrated", "display": "FHD IPS", "os": "Windows 11"},
     [v(164999, storage="512GB", ram="8GB"), v(179999, storage="512GB", ram="16GB")]),
    ("laptops", "Lenovo", "Lenovo IdeaPad Slim 3 Ryzen 5", "82XQ00BDPS",
     {"processor": "AMD Ryzen 5", "screen_size": "15.6 inch", "gpu": "Integrated", "display": "FHD IPS", "os": "Windows 11"},
     [v(149999, storage="512GB", ram="8GB")]),
    ("laptops", "Dell", "Dell Inspiron 3520 Core i7", "INS3520-I7",
     {"processor": "Intel Core i7", "screen_size": "15.6 inch", "gpu": "Integrated", "display": "FHD", "os": "Windows 11"},
     [v(214999, storage="512GB", ram="16GB")]),
    ("laptops", "ASUS", "ASUS TUF Gaming F15 RTX 4050", "FX507ZU4",
     {"processor": "Intel Core i7", "screen_size": "15.6 inch", "gpu": "NVIDIA RTX 4050", "display": "FHD 144Hz", "os": "Windows 11"},
     [v(339999, storage="512GB", ram="16GB")]),
    ("laptops", "Apple", "Apple MacBook Air M2 13-inch", "MLY33",
     {"processor": "Apple M2", "screen_size": "13.6 inch", "gpu": "Integrated", "display": "Liquid Retina", "os": "macOS"},
     [v(299999, storage="256GB", ram="8GB"), v(359999, storage="512GB", ram="8GB")]),
    # ---- tablets
    ("tablets", "Samsung", "Samsung Galaxy Tab A9+", "SM-X210",
     {"screen_size": "11 inch", "connectivity": "Wi-Fi", "os": "Android"},
     [v(64999, storage="64GB", ram="4GB"), v(74999, storage="128GB", ram="8GB")]),
    ("tablets", "Apple", "Apple iPad 10th Gen", "MPQ03",
     {"screen_size": "10.9 inch", "connectivity": "Wi-Fi", "os": "iPadOS"},
     [v(124999, storage="64GB"), v(159999, storage="256GB")]),
    ("tablets", "Xiaomi", "Xiaomi Redmi Pad SE", "23073RPBFG",
     {"screen_size": "11 inch", "connectivity": "Wi-Fi", "os": "Android"},
     [v(49999, storage="128GB", ram="6GB")]),
    # ---- smartwatches
    ("smartwatches", "Xiaomi", "Xiaomi Redmi Watch 4", "M2315W1",
     {"screen_size": "1.97 inch", "display": "AMOLED", "water_resistance": "5 ATM", "connectivity": "Bluetooth"},
     [v(21999, colour="Black"), v(21999, colour="Silver")]),
    ("smartwatches", "Samsung", "Samsung Galaxy Watch 6 40mm", "SM-R930",
     {"screen_size": "1.3 inch", "display": "AMOLED", "water_resistance": "5 ATM", "connectivity": "Bluetooth"},
     [v(69999, colour="Graphite"), v(69999, colour="Gold")]),
    ("smartwatches", "Amazfit", "Amazfit Bip 5", "A2215",
     {"screen_size": "1.91 inch", "display": "TFT", "water_resistance": "IP68", "connectivity": "Bluetooth"},
     [v(17999, colour="Black")]),
    # ---- audio
    ("audio", "Audionic", "Audionic Airbud 550 Wireless Earbuds", "AIRBUD-550",
     {"type": "Earbuds", "noise_cancelling": "No", "connectivity": "Bluetooth", "water_resistance": "IPX4"}, [v(5499, colour="Black")]),
    ("audio", "Samsung", "Samsung Galaxy Buds FE", "SM-R400N",
     {"type": "Earbuds", "noise_cancelling": "Yes (ANC)", "connectivity": "Bluetooth", "water_resistance": "IPX2"},
     [v(21999, colour="Graphite"), v(21999, colour="White")]),
    ("audio", "Sony", "Sony WH-CH720N Headphones", "WHCH720N",
     {"type": "Over-ear headphones", "noise_cancelling": "Yes (ANC)", "connectivity": "Bluetooth"}, [v(39999, colour="Black")]),
    ("audio", "JBL", "JBL Tune 520BT Headphones", "JBLT520BT",
     {"type": "On-ear headphones", "noise_cancelling": "No", "connectivity": "Bluetooth"}, [v(14999, colour="Black"), v(14999, colour="Blue")]),
    # ---- power
    ("power", "Anker", "Anker PowerCore 20000mAh Power Bank", "A1384",
     {"type": "Power bank", "capacity": "20000 mAh", "output_power": "20W", "port": "USB-C"}, [v(9999)]),
    ("power", "Xiaomi", "Xiaomi Redmi 10000mAh Power Bank", "PB100LZM",
     {"type": "Power bank", "capacity": "10000 mAh", "output_power": "10W", "port": "USB-A"}, [v(3999)]),
    ("power", "Samsung", "Samsung 25W USB-C Fast Charger", "EP-TA800",
     {"type": "Wall charger", "output_power": "25W", "port": "USB-C"}, [v(4499)]),
    # ---- TVs
    ("tvs", "TCL", "TCL 43 inch 4K UHD Google TV", "43P635",
     {"screen_size": "43 inch", "resolution": "4K UHD", "display": "LED", "smart_tv": "Google TV", "refresh_rate": "60Hz"}, [v(89999)]),
    ("tvs", "Samsung", "Samsung 55 inch Crystal UHD Smart TV", "UA55CU7000",
     {"screen_size": "55 inch", "resolution": "4K UHD", "display": "LED", "smart_tv": "Tizen", "refresh_rate": "60Hz"}, [v(179999)]),
    ("tvs", "Haier", "Haier 32 inch HD Android TV", "H32K66G",
     {"screen_size": "32 inch", "resolution": "HD", "display": "LED", "smart_tv": "Android TV", "refresh_rate": "60Hz"}, [v(44999)]),
    ("tvs", "TCL", "TCL 65 inch QLED 4K Google TV", "65C655",
     {"screen_size": "65 inch", "resolution": "4K UHD", "display": "QLED", "smart_tv": "Google TV", "refresh_rate": "120Hz"}, [v(259999)]),
    # ---- ACs
    ("air-conditioners", "Gree", "Gree Pular 1.5 Ton DC Inverter AC", "GS-18PITH",
     {"tonnage": "1.5 Ton", "inverter": "DC Inverter", "energy_rating": "A+", "type": "Split"}, [v(214999)]),
    ("air-conditioners", "Haier", "Haier 1 Ton Inverter AC", "HSU-12HFPCA",
     {"tonnage": "1 Ton", "inverter": "DC Inverter", "energy_rating": "A", "type": "Split"}, [v(164999)]),
    ("air-conditioners", "Dawlance", "Dawlance 1.5 Ton Non-Inverter AC", "DLX-1830",
     {"tonnage": "1.5 Ton", "inverter": "Non-inverter", "energy_rating": "B", "type": "Split"}, [v(149999)]),
    # ---- men's clothing (fictional brands)
    ("mens-clothing", "Urban Thread", "Urban Thread Men's Fleece Tracksuit", "UT-TRK-210",
     {"gender": M, "type": "Tracksuit", "fit": "Regular", "fabric": "Fleece", "sleeve": "Full sleeve", "season": "Winter"},
     grid(4990, ["Black", "Charcoal", "Navy"], CLOTH)),
    ("mens-clothing", "Urban Thread", "Urban Thread Men's Graphic T-Shirt", "UT-TEE-118",
     {"gender": M, "type": "T-Shirt", "fit": "Oversized", "fabric": "Cotton", "sleeve": "Half sleeve", "season": "Summer"},
     grid(1490, ["White", "Black"], CLOTH)),
    ("mens-clothing", "Rang", "Rang Men's Cotton Shalwar Kameez", "RG-SK-044",
     {"gender": M, "type": "Shalwar Kameez", "fit": "Regular", "fabric": "Cotton", "sleeve": "Full sleeve", "season": "All season"},
     grid(4490, ["White", "Sky Blue", "Beige"], ["S", "M", "L", "XL"])),
    ("mens-clothing", "Urban Thread", "Urban Thread Men's Slim Fit Jeans", "UT-JNS-302",
     {"gender": M, "type": "Jeans", "fit": "Slim", "fabric": "Denim", "season": "All season"},
     grid(3990, ["Mid Blue", "Black"], ["30", "32", "34", "36"])),
    ("mens-clothing", "Rang", "Rang Men's Puffer Jacket", "RG-JKT-501",
     {"gender": M, "type": "Jacket", "fit": "Regular", "fabric": "Polyester", "sleeve": "Full sleeve", "season": "Winter"},
     grid(7990, ["Black", "Olive"], ["M", "L", "XL", "XXL"])),
    # ---- women's clothing
    ("womens-clothing", "Rang", "Rang Embroidered Lawn Kurta", "RG-KRT-731",
     {"gender": W, "type": "Kurta", "pieces": "1 Piece", "fabric": "Lawn", "season": "Summer"},
     grid(3450, ["Mint", "Peach"], ["XS", "S", "M", "L"])),
    ("womens-clothing", "Rang", "Rang Printed Khaddar 3-Piece Suit", "RG-3PC-812",
     {"gender": W, "type": "Suit", "pieces": "3 Piece", "fabric": "Khaddar", "season": "Winter"},
     grid(6990, ["Maroon", "Teal"], ["S", "M", "L", "XL"])),
    ("womens-clothing", "Urban Thread", "Urban Thread Women's Knit Sweater", "UT-SWT-405",
     {"gender": W, "type": "Sweater", "pieces": "1 Piece", "fabric": "Acrylic Wool", "season": "Winter"},
     grid(3290, ["Cream", "Black", "Rose"], ["S", "M", "L"])),
    # ---- unstitched
    ("unstitched", "Kapra Studio", "Kapra Studio Unstitched Lawn 3-Piece", "KS-LWN-3P-07",
     {"gender": W, "pieces": "3 Piece", "fabric": "Lawn", "season": "Summer"}, [v(5990, colour="Pink"), v(5990, colour="Blue")]),
    ("unstitched", "Kapra Studio", "Kapra Studio Unstitched Khaddar 2-Piece", "KS-KHD-2P-11",
     {"gender": W, "pieces": "2 Piece", "fabric": "Khaddar", "season": "Winter"}, [v(3990, colour="Mustard"), v(3990, colour="Green")]),
    ("unstitched", "Rang", "Rang Men's Unstitched Wash & Wear", "RG-WW-UN-09",
     {"gender": M, "pieces": "2 Piece", "fabric": "Wash & Wear", "season": "All season"}, [v(3490, colour="White"), v(3490, colour="Grey")]),
    # ---- shoes (fictional brands)
    ("shoes", "Stepwell", "Stepwell Men's Running Shoes", "SW-RUN-220",
     {"gender": M, "shoe_type": "Sports / running", "closure": "Lace-up"}, grid(6990, ["Black", "Grey"], SHOE_M)),
    ("shoes", "Stepwell", "Stepwell Men's Leather Formal Shoes", "SW-FRM-118",
     {"gender": M, "shoe_type": "Formal", "closure": "Lace-up"}, grid(8990, ["Black", "Brown"], SHOE_M)),
    ("shoes", "Pace", "Pace Men's Peshawari Chappal", "PC-PSH-07",
     {"gender": M, "shoe_type": "Chappal / sandal", "closure": "Slip-on"}, grid(3990, ["Brown", "Black"], SHOE_M)),
    ("shoes", "Pace", "Pace Women's Block Heel Sandals", "PC-HEEL-31",
     {"gender": W, "shoe_type": "Heels", "closure": "Buckle"}, grid(4490, ["Beige", "Black"], SHOE_W)),
    ("shoes", "Stepwell", "Stepwell Women's Everyday Sneakers", "SW-SNK-W12",
     {"gender": W, "shoe_type": "Sneakers", "closure": "Lace-up"}, grid(5490, ["White", "Pink"], SHOE_W)),
    # ---- beauty
    ("beauty", "CeraVe", "CeraVe Moisturising Cream 340g", "CRV-MC-340",
     {"type": "Moisturiser", "skin_type": "Dry", "volume": "340 g", "gender": "Unisex"}, [v(6999)]),
    ("beauty", "Garnier", "Garnier Vitamin C Serum 30ml", "GRN-VC-30",
     {"type": "Serum", "skin_type": "All skin types", "volume": "30 ml", "gender": "Unisex"}, [v(2499)]),
    ("beauty", "Nivea", "Nivea Men Deep Face Wash 100ml", "NIV-MDW-100",
     {"type": "Face wash", "skin_type": "Oily", "volume": "100 ml", "gender": "Men"}, [v(899)]),
    ("beauty", "Neutrogena", "Neutrogena Ultra Sheer Sunscreen SPF 50", "NTG-SPF50-88",
     {"type": "Sunscreen", "skin_type": "All skin types", "volume": "88 ml", "gender": "Unisex"}, [v(4299)]),
]

CAT_NAMES = {slug: name for _, name, slug, _ in CATEGORY_PRESETS}


def seed(db):
    if db.scalar(select(Retailer).where(Retailer.domain == STORES[0][1])):
        return "demo data already loaded"
    rnd = random.Random(42)
    for group, name, slug, keys in CATEGORY_PRESETS:
        if not db.scalar(select(Category).where(Category.slug == slug)):
            db.add(Category(group=group, name=name, slug=slug, filter_specs=list(keys)))
    db.flush()
    retailers = []
    for i, (name, dom, city, verified, regions, cats, warranty) in enumerate(STORES):
        r = Retailer(name=name, slug=dom.split(".")[0], domain=dom, city=city, status="active", verified=verified,
                     verification_notes="DEMO DATA: not a real store" if verified else None, delivery_regions=regions,
                     phone="021-0000000", email=f"sales@{dom}", feed_method="csv",
                     permission_reference="Demo data", description="Fictional demo store for testing the product.",
                     plan="pro" if i in (0, 7) else "free")
        db.add(r)
        retailers.append((r, cats, warranty))
    db.flush()
    # which stores carry each product: most stores of that category, never fewer than 2
    carriers = {}
    for idx, (cat, *_rest) in enumerate(PRODUCTS):
        sellers = [r.id for r, cats, _ in retailers if cat in cats]
        keep = [x for x in sellers if rnd.random() > 0.15]
        carriers[idx] = set(keep if len(keep) >= 2 else sellers[:2])
    for r, cats, warranty in retailers:
        rows = []
        for idx, (cat, brand, title, model, specs, variants) in enumerate(PRODUCTS):
            if r.id not in carriers[idx]:
                continue
            factor = rnd.uniform(0.93, 1.07)
            for var in variants:
                if len(variants) > 4 and rnd.random() < 0.12:
                    continue  # some sizes sold out / not carried
                price = int(var["price"] * factor / 10) * 10 - (1 if var["price"] > 20000 else 10)
                key = "-".join(str(var.get(k, "")) for k in ("storage", "ram", "colour", "size", "region")).strip("-")
                rows.append({
                    "product_url": f"https://{r.domain}/p/{model.lower()}?v={key.lower().replace(' ', '')}",
                    "retailer_sku": f"{model}-{key or 'STD'}", "brand": brand, "model_number": model,
                    "product_title": title, "category": CAT_NAMES[cat],
                    "storage_capacity": var.get("storage", ""), "ram": var.get("ram", ""),
                    "variant_colour": var.get("colour", ""), "variant_size": var.get("size", ""),
                    "region": var.get("region", ""),
                    "price": str(price), "shipping_cost": rnd.choice(["0", "0", "199", "250", "350", ""]),
                    "stock_status": "out_of_stock" if rnd.random() < 0.07 else "in_stock",
                    "warranty_type": warranty,
                    "condition": "refurbished" if cat in ("mobile-phones", "laptops") and rnd.random() < 0.06 else "new",
                    **{f"spec_{k}": val for k, val in specs.items()},
                })
        import_rows(db, rows, source="demo", retailer=r, filename="demo", allow_create=True)
    # back-fill 45 days of plausible price history so charts and deal labels work
    for o in db.scalars(select(Offer)):
        db.query(PriceHistory).filter(PriceHistory.offer_id == o.id).delete()
        price = float(o.price) * rnd.uniform(1.02, 1.12)
        for d in range(45, 0, -3):
            price = max(float(o.price) * 0.97, price * rnd.uniform(0.985, 1.01))
            db.add(PriceHistory(offer_id=o.id, price=Decimal(int(price / 10) * 10), shipping_cost=o.shipping_cost,
                                stock_status="in_stock", captured_at=now() - timedelta(days=d)))
        db.add(PriceHistory(offer_id=o.id, price=o.price, shipping_cost=o.shipping_cost,
                            stock_status=o.stock_status, captured_at=now() - timedelta(hours=2)))
        o.checked_at = now() - timedelta(hours=rnd.choice([1, 3, 6, 20, 60]))
    db.commit()
    n = db.scalar(select(func.count()).select_from(Offer))
    return f"demo data loaded: {len(retailers)} fictional stores, {len(PRODUCTS)} products, {n} offers"
