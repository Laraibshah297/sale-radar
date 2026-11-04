"""Read-side business rules: which offers are shown, how they are ranked,
freshness labels, price history and deal quality, and search."""
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from rapidfuzz import fuzz
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from .config import settings, stale_hours_for
from .db import is_postgres
from .models import (Category, Offer, PriceHistory, Product, Retailer, SponsoredCampaign, Variant,
                     now)
from .text import compact, norm, synonyms, tokens


def age_hours(ts: datetime) -> float:
    return (now() - ts).total_seconds() / 3600


def freshness(offer: Offer, category_slug=None) -> str:
    """fresh | stale | hidden"""
    h = age_hours(offer.checked_at)
    if h > settings.HIDE_HOURS:
        return "hidden"
    return "stale" if h > stale_hours_for(category_slug) else "fresh"


def humanize_age(ts: datetime) -> str:
    h = age_hours(ts)
    if h < 1:
        return f"{max(1, int(h * 60))} min ago"
    if h < 48:
        return f"{int(h)} h ago"
    return f"{int(h // 24)} days ago"


def visible_offer_filter():
    return and_(Offer.active.is_(True), Offer.match_status == "matched", Offer.variant_id.is_not(None),
                Offer.checked_at >= now() - timedelta(hours=settings.HIDE_HOURS),
                Retailer.status == "active")


def offers_for_variant(db: Session, variant: Variant, sort: str = "delivered", hide_out_of_stock=False):
    q = (select(Offer).join(Retailer).where(Offer.variant_id == variant.id, visible_offer_filter())
         .options(selectinload(Offer.retailer)))
    offers = list(db.scalars(q))
    if hide_out_of_stock:
        offers = [o for o in offers if o.stock_status != "out_of_stock"]
    return rank_offers(offers, sort)


def rank_offers(offers, sort="delivered"):
    """Organic ranking only: price-based, never commission- or sponsor-based.
    In-stock offers come first. 'delivered' puts offers with a known delivered
    price first (lowest first), then offers with unknown shipping by item price."""
    def stock_rank(o):
        return 1 if o.stock_status == "out_of_stock" else 0
    if sort == "item":
        key = lambda o: (stock_rank(o), o.price)
    elif sort == "newest":
        key = lambda o: (stock_rank(o), -o.checked_at.timestamp())
    else:
        key = lambda o: (stock_rank(o), o.delivered_price is None,
                         o.delivered_price if o.delivered_price is not None else o.price)
    return sorted(offers, key=key)


def sponsored_for(db: Session, variant: Variant | None = None, category_id: int | None = None):
    t = now()
    q = (select(SponsoredCampaign).join(Retailer)
         .where(SponsoredCampaign.active.is_(True), SponsoredCampaign.starts_at <= t,
                SponsoredCampaign.ends_at >= t, Retailer.status == "active")
         .options(selectinload(SponsoredCampaign.offer), selectinload(SponsoredCampaign.retailer)))
    res = []
    for c in db.scalars(q):
        if variant and c.offer and c.offer.variant_id == variant.id and c.offer.active:
            res.append(c)
        elif category_id and c.category_id == category_id:
            res.append(c)
    return res


@dataclass
class DailyPoint:
    day: str
    price: Decimal


def price_history(db: Session, variant: Variant, days: int = 90) -> list[DailyPoint]:
    """Lowest observed item price per day across all retailers for a variant.
    Each recorded price is carried forward until it changes."""
    since = now() - timedelta(days=days)
    rows = db.execute(
        select(PriceHistory.offer_id, PriceHistory.price, PriceHistory.captured_at, PriceHistory.stock_status)
        .join(Offer, Offer.id == PriceHistory.offer_id)
        .where(Offer.variant_id == variant.id, Offer.match_status == "matched")
        .order_by(PriceHistory.captured_at)).all()
    if not rows:
        return []
    per_offer = defaultdict(list)
    for oid, price, ts, stock in rows:
        per_offer[oid].append((ts, price, stock))
    start = max(min(r[2] for r in rows), since).date()
    end = now().date()
    out, d = [], start
    while d <= end:
        best = None
        for pts in per_offer.values():
            cur = None
            for ts, price, stock in pts:
                if ts.date() <= d:
                    cur = (price, stock)
                else:
                    break
            if cur and cur[1] != "out_of_stock":
                best = cur[0] if best is None else min(best, cur[0])
        if best is not None:
            out.append(DailyPoint(d.isoformat(), best))
        d += timedelta(days=1)
    return out


def deal_quality(current: Decimal | None, history: list[DailyPoint]) -> dict | None:
    """Compares the current lowest price with the observed 30-day history,
    instead of trusting crossed-out 'was' prices."""
    if current is None or len(history) < 7:
        return None
    recent = [float(p.price) for p in history[-30:]]
    median = statistics.median(recent)
    low = min(recent)
    cur = float(current)
    if cur <= low:
        label, tone = "Lowest price seen in 30 days", "good"
    elif cur < median * 0.97:
        label, tone = "Below the usual price", "good"
    elif cur > median * 1.03:
        label, tone = "Above the usual price", "bad"
    else:
        label, tone = "Usual price", "neutral"
    return {"label": label, "tone": tone, "median": Decimal(str(round(median))), "low": Decimal(str(low))}


# ---------------------------------------------------------------- search

@dataclass
class ProductCard:
    product: Product
    lowest: Decimal | None
    lowest_delivered: Decimal | None
    stores: int
    updated: datetime | None
    in_stock: bool
    key_spec: str


def card_for(product: Product, offers: list[Offer]) -> ProductCard:
    live = [o for o in offers if o.stock_status != "out_of_stock"] or offers
    lowest = min((o.price for o in live), default=None)
    deliv = [o.delivered_price for o in live if o.delivered_price is not None]
    spec_bits = [v for v in {v.storage for v in product.variants if v.storage}]
    key_spec = ", ".join(sorted(spec_bits)[:3]) or (product.model_number or "")
    return ProductCard(product, lowest, min(deliv) if deliv else None,
                       len({o.retailer_id for o in offers}),
                       max((o.checked_at for o in offers), default=None),
                       any(o.stock_status != "out_of_stock" for o in offers), key_spec)


def _offers_by_product(db: Session, product_ids):
    if not product_ids:
        return {}
    q = (select(Offer, Variant.product_id).join(Retailer).join(Variant, Variant.id == Offer.variant_id)
         .where(Variant.product_id.in_(product_ids), visible_offer_filter()))
    res = defaultdict(list)
    for o, pid in db.execute(q):
        res[pid].append(o)
    return res


def _token_clause(tok: str):
    alts = synonyms(tok) | ({compact(tok)} if any(c.isdigit() for c in tok) else set())
    return or_(*[Product.search_text.like(f"%{a}%") for a in alts if a])


def search_products(db: Session, q: str = "", *, category: Category | None = None, brand: str | None = None,
                    retailer_id: int | None = None, min_price=None, max_price=None, in_stock=False,
                    spec_filters: dict | None = None, sort="relevance", limit=48, offset=0):
    toks = tokens(q)
    base = select(Product).options(selectinload(Product.variants), selectinload(Product.category))
    if category:
        base = base.where(Product.category_id == category.id)
    if brand:
        base = base.where(func.lower(Product.brand) == brand.lower())
    fuzzy_used = False
    if toks:
        products = list(db.scalars(base.where(and_(*[_token_clause(t) for t in toks])).limit(2000)))
        if not products:  # typo tolerance
            fuzzy_used = True
            qn = norm(q)
            if is_postgres():
                products = list(db.scalars(
                    base.where(func.word_similarity(qn, Product.search_text) > 0.35)
                    .order_by(func.word_similarity(qn, Product.search_text).desc()).limit(200)))
            else:
                pool = list(db.scalars(base.limit(5000)))
                products = [p for p in pool if fuzz.partial_ratio(qn, p.search_text) >= 80]
    else:
        products = list(db.scalars(base.limit(5000)))

    offers = _offers_by_product(db, [p.id for p in products])
    cards = []
    for p in products:
        os_ = offers.get(p.id, [])
        if retailer_id:
            os_ = [o for o in os_ if o.retailer_id == retailer_id]
        if spec_filters:
            ok_variants = {v.id for v in p.variants
                           if all(compact(getattr(v, k, None) or "") == compact(val)
                                  for k, val in spec_filters.items() if val)}
            os_ = [o for o in os_ if o.variant_id in ok_variants]
        if not os_:
            continue
        c = card_for(p, os_)
        if in_stock and not c.in_stock:
            continue
        if min_price is not None and (c.lowest is None or c.lowest < min_price):
            continue
        if max_price is not None and (c.lowest is None or c.lowest > max_price):
            continue
        cards.append(c)

    if sort == "price_asc":
        cards.sort(key=lambda c: (c.lowest is None, c.lowest or 0))
    elif sort == "price_desc":
        cards.sort(key=lambda c: -(c.lowest or 0))
    elif sort == "delivered":
        cards.sort(key=lambda c: (c.lowest_delivered is None, c.lowest_delivered or c.lowest or 0))
    elif sort == "newest":
        cards.sort(key=lambda c: c.updated or now(), reverse=True)
    elif toks:
        qn = norm(q)
        cards.sort(key=lambda c: (-fuzz.token_set_ratio(qn, norm(f"{c.product.brand} {c.product.title}")),
                                  -c.stores))
    else:
        cards.sort(key=lambda c: (-c.stores, c.product.title))
    return cards[offset:offset + limit], len(cards), fuzzy_used


def facets(cards: list[ProductCard]):
    brands = sorted({c.product.brand for c in cards})
    storages = sorted({v.storage for c in cards for v in c.product.variants if v.storage},
                      key=lambda s: (len(s), s))
    rams = sorted({v.ram for c in cards for v in c.product.variants if v.ram}, key=lambda s: (len(s), s))
    return {"brands": brands, "storage": storages, "ram": rams}
