"""Product matching with a confidence hierarchy (blueprint section 6.3):

1. Exact GTIN/EAN/UPC on a variant.
2. Existing retailer SKU mapping (this retailer's SKU was matched before).
3. Brand + exact model number, then the exact variant (storage/RAM/colour/...).
4. Fuzzy title similarity, which only *suggests* candidates for human review.

Different storage sizes, colours, regions or conditions are never merged
because they look alike: variants are keyed on their attributes.
"""
import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .filters import CATEGORY_PRESETS, normalise_spec_key
from .models import Category, Offer, Product, Variant
from .text import compact, norm, norm_storage, search_text_for, slugify

AUTO_FUZZY_NEVER = True  # fuzzy matches always go to the review queue
REVIEW_MIN_SCORE = 70


def variant_key(storage=None, ram=None, colour=None, size=None, region=None) -> str:
    return "|".join([norm_storage(storage), norm_storage(ram), compact(colour),
                     compact(size), compact(region)])


@dataclass
class MatchResult:
    variant: Variant | None
    status: str  # matched | review | unmatched
    method: str
    confidence: float
    evidence: str
    candidates: list = field(default_factory=list)  # [(variant, score, evidence)]


def _variant_attrs(row):
    return dict(storage=row.get("storage_capacity"), ram=row.get("ram"),
                colour=row.get("variant_colour"), size=row.get("variant_size"),
                region=row.get("region"))


def has_variant_attrs(row) -> bool:
    return any(v for v in _variant_attrs(row).values())


def find_product_by_model(db: Session, brand: str, model_number: str) -> Product | None:
    if not brand or not model_number:
        return None
    cm = compact(model_number)
    for p in db.scalars(select(Product).where(func.lower(Product.brand) == brand.strip().lower())):
        if compact(p.model_number) == cm:
            return p
    return None


def _preset_for(name: str):
    n = compact(name)
    for group, pname, pslug, keys in CATEGORY_PRESETS:
        if n in (compact(pname), compact(pslug)):
            return group, pname, pslug, keys
    return None


def get_or_create_category(db: Session, name: str | None) -> Category | None:
    if not name:
        return None
    preset = _preset_for(name)
    slug = preset[2] if preset else slugify(name)
    cat = db.scalar(select(Category).where(Category.slug == slug))
    if not cat:
        if preset:
            cat = Category(group=preset[0], name=preset[1], slug=slug, filter_specs=list(preset[3]))
        else:
            cat = Category(group="Other", name=name.strip().title(), slug=slug,
                           filter_specs=["colour", "size", "condition"])
        db.add(cat)
        db.flush()
    return cat


def specs_from_row(row) -> dict:
    """CSV columns named spec_<key> (e.g. spec_processor) become product specs."""
    out = {}
    for k, v in row.items():
        if k and k.startswith("spec_") and v not in (None, ""):
            out[normalise_spec_key(k[5:])] = str(v).strip()
    return out


def merge_specs(product: Product, row) -> None:
    """Fill in specs the product doesn't have yet; never overwrite admin edits."""
    new = specs_from_row(row)
    missing = {k: v for k, v in new.items() if k not in (product.specs or {})}
    if missing:
        product.specs = {**(product.specs or {}), **missing}


def create_variant(db: Session, product: Product, row) -> Variant:
    attrs = _variant_attrs(row)
    v = Variant(product=product, gtin=(row.get("gtin") or None),
                variant_key=variant_key(**attrs),
                **{k: (val.strip() if isinstance(val, str) and val.strip() else None)
                   for k, val in attrs.items()})
    db.add(v)
    db.flush()
    product.search_text = search_text_for(product)
    return v


def unique_slug(db: Session, base: str) -> str:
    slug, i = base, 2
    while db.scalar(select(Product.id).where(Product.slug == slug)):
        slug, i = f"{base}-{i}", i + 1
    return slug


def canonical_title(row) -> str:
    """Remove variant details (storage, RAM, colour...) from a retailer title."""
    title = row["product_title"].strip()
    for key in ("storage_capacity", "ram", "variant_colour", "variant_size", "region"):
        val = (row.get(key) or "").strip()
        if len(val) >= 2:  # never strip one-letter sizes like "S" or "M" out of words
            title = re.sub(rf"\(?(?<![\w']){re.escape(val)}(?![\w'])\s*(ram)?\)?", " ", title, flags=re.I)
    title = re.sub(r"\b\d+\s?(gb|tb)(\s?ram)?\b", " ", title, flags=re.I)
    title = re.sub(r"\s+[-/|,]\s*$", "", re.sub(r"\s+", " ", title)).strip(" -/|,")
    return title or row["product_title"].strip()


def create_product(db: Session, row) -> Product:
    title = canonical_title(row)
    p = Product(title=title, brand=row["brand"].strip(), model_number=(row.get("model_number") or None),
                category=get_or_create_category(db, row.get("category")),
                image_url=row.get("image_url") or None, specs=specs_from_row(row))
    p.slug = unique_slug(db, slugify(f"{p.brand} {title}" if p.brand.lower() not in title.lower() else title))
    db.add(p)
    db.flush()
    return p


def match_row(db: Session, row, retailer_id: int, allow_create: bool) -> MatchResult:
    attrs = _variant_attrs(row)
    vkey = variant_key(**attrs)

    # 1. GTIN
    gtin = (row.get("gtin") or "").strip()
    if gtin:
        v = db.scalar(select(Variant).where(Variant.gtin == gtin))
        if v:
            return MatchResult(v, "matched", "gtin", 1.0, f"GTIN {gtin} matched exactly")

    # 2. Existing SKU mapping for this retailer
    sku = row.get("retailer_sku")
    if sku:
        prev = db.scalar(select(Offer).where(Offer.retailer_id == retailer_id, Offer.retailer_sku == sku,
                                             Offer.match_status == "matched"))
        if prev and prev.variant_id:
            return MatchResult(prev.variant, "matched", "sku_mapping", 0.98,
                               f"Retailer SKU {sku} was matched before")

    # 3. Brand + model number
    product = find_product_by_model(db, row.get("brand", ""), row.get("model_number", ""))
    if product:
        same = [v for v in product.variants if v.variant_key == vkey]
        if same:
            return MatchResult(same[0], "matched", "brand_model_variant", 0.95,
                               f"Brand + model {product.model_number} + variant attributes matched")
        if not has_variant_attrs(row) and len(product.variants) == 1:
            return MatchResult(product.variants[0], "matched", "brand_model", 0.9,
                               "Brand + model matched; product has a single variant")
        if has_variant_attrs(row) and allow_create:
            v = create_variant(db, product, row)
            return MatchResult(v, "matched", "brand_model_new_variant", 0.9,
                               f"Known model {product.model_number}; new variant {v.label} created")
        cands = [(v, 80.0, "Same brand + model; variant needs confirming") for v in product.variants]
        return MatchResult(None, "review", "brand_model_ambiguous", 0.6,
                           "Model matched but variant is ambiguous", cands)

    # 4. Fuzzy candidates (never auto-merged)
    title = norm(row.get("product_title"))
    brand = (row.get("brand") or "").strip().lower()
    cands = []
    row_model = compact(row.get("model_number"))
    q = select(Variant).join(Product)
    if brand:
        q = q.where(func.lower(Product.brand) == brand)
    for v in db.scalars(q.limit(5000)):
        score = fuzz.token_set_ratio(title, norm(f"{v.product.title} {v.label}"))
        if row_model and v.product.model_number and compact(v.product.model_number) != row_model:
            continue  # both have model numbers and they differ: a different product
        if score >= REVIEW_MIN_SCORE:
            if norm_storage(attrs["storage"]) and v.storage and norm_storage(v.storage) != norm_storage(attrs["storage"]):
                continue  # never suggest a different storage size
            cands.append((v, float(score), f"Title similarity {score:.0f}%"))
    cands.sort(key=lambda c: -c[1])
    cands = cands[:5]

    if allow_create and row.get("brand") and row.get("model_number") and not cands:
        p = create_product(db, row)
        v = create_variant(db, p, row)
        return MatchResult(v, "matched", "new_product", 1.0,
                           "No existing product with this brand + model; new canonical product created")
    if cands:
        return MatchResult(None, "review", "fuzzy", cands[0][1] / 100,
                           "Similar products found; needs human review", cands)
    return MatchResult(None, "unmatched", "none", 0.0,
                       "No identifier or similar product; an admin must create or link a product")
