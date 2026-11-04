"""Real Pakistani stores to approach for the pilot, by category.

They are added with status "prospect": visible only in the admin panel and
never shown to shoppers, and nothing is imported from them. Change a store to
"active" only after it agrees to share data (record that in "Permission
reference").

"tested" means the store's public Shopify product feed answered on
2026-11-04 (from the old prototype's GitHub run). Domains not marked tested
should be checked before contacting the store.
"""
from sqlalchemy import select

from .models import Retailer
from .text import slugify

# name, domain, categories, tested Shopify feed, products seen
PROSPECTS = [
    # fashion (Shopify feeds confirmed reachable)
    ("Outfitters", "outfitters.com.pk", "Men's & women's clothing, shoes", True, 3766),
    ("Breakout", "breakout.com.pk", "Men's & women's clothing", True, 2159),
    ("Generation", "generation.com.pk", "Women's clothing", True, 5000),
    ("Limelight", "limelight.pk", "Women's clothing, unstitched", True, 5000),
    ("Gul Ahmed", "gulahmedshop.com", "Unstitched, women's & men's clothing", True, 5000),
    ("Alkaram Studio", "alkaramstudio.com", "Unstitched, women's clothing", True, 1586),
    ("Nishat Linen", "nishatlinen.com", "Unstitched, women's clothing, home", True, 2747),
    ("Bonanza Satrangi", "bonanzasatrangi.com", "Women's & men's clothing", True, 5000),
    ("Zellbury", "zellbury.com", "Women's & men's clothing", True, 5000),
    ("Sapphire", "pk.sapphireonline.pk", "Women's clothing, unstitched", False, 0),
    # shoes
    ("Ndure", "ndure.com", "Shoes", False, 0),
    ("Stylo", "stylo.pk", "Women's shoes", False, 0),
    ("Borjan", "borjan.com.pk", "Shoes", False, 0),
    ("Servis", "servis.pk", "Shoes", False, 0),
    ("Bata Pakistan", "bata.com.pk", "Shoes", False, 0),
    # electronics
    ("Audionic", "audionic.co", "Earbuds, headphones, speakers", True, 99),
    ("Telemart", "telemart.pk", "Phones, laptops, electronics", False, 0),
    ("Shophive", "shophive.com", "Phones, laptops, electronics", False, 0),
    ("iShopping.pk", "ishopping.pk", "Electronics, appliances, fashion", False, 0),
    ("Mega.pk", "mega.pk", "Phones, laptops, appliances", False, 0),
    ("HomeShopping", "homeshopping.pk", "Phones, electronics, appliances", False, 0),
    # beauty
    ("Saeed Ghani", "saeedghani.pk", "Beauty & personal care", False, 0),
]


def seed_prospects(db) -> str:
    added = 0
    for name, dom, cats, tested, seen in PROSPECTS:
        if db.scalar(select(Retailer).where(Retailer.domain == dom)):
            continue
        slug, i = slugify(name), 2
        while db.scalar(select(Retailer.id).where(Retailer.slug == slug)):
            slug, i = f"{slugify(name)}-{i}", i + 1
        note = (f"Sells: {cats}. " + (f"Public Shopify feed reachable (about {seen} products seen on 2026-11-04). "
                                       "Ask for permission to use it, or for a CSV / Google Sheet."
                                       if tested else "Domain not yet checked. Confirm before contacting."))
        db.add(Retailer(name=name, slug=slug, domain=dom, status="prospect", verified=False,
                        feed_method="shopify" if tested else "csv", verification_notes=note,
                        description=None, permission_reference=None))
        added += 1
    db.commit()
    return f"{added} prospect stores added (admin only, status 'prospect')"
