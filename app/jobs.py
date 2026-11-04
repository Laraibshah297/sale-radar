"""Scheduled jobs: pull retailer feeds, send price alerts, flag stale data.
Run once with `python -m app.cli run-jobs` from cron, or continuously with
`python -m app.cli scheduler` (the Docker 'worker' service does this)."""
import time
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .importer import import_csv_text, import_rows
from .mailer import send_email
from .models import ImportRun, Offer, PriceAlert, Retailer, now
from .services import offers_for_variant

UA = f"{settings.SITE_NAME}Bot/1.0 (+{settings.BASE_URL}/about)"


def fetch(url: str, retries: int = 3) -> httpx.Response:
    delay = 2
    for attempt in range(retries):
        try:
            r = httpx.get(url, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
            if r.status_code in (429, 503) and attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            r.raise_for_status()
            return r
        except httpx.TransportError:
            if attempt == retries - 1:
                raise
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")


def shopify_rows(retailer: Retailer, max_pages: int = 20):
    """Only for retailers that gave permission (permission_reference set).
    Reads the store's public Shopify product feed."""
    base = retailer.feed_url.rstrip("/") if retailer.feed_url else f"https://{retailer.domain}"
    for page in range(1, max_pages + 1):
        data = fetch(f"{base}/products.json?limit=250&page={page}").json()
        products = data.get("products") or []
        if not products:
            return
        for p in products:
            names = [str(o.get("name", "")).lower() for o in (p.get("options") or [])]
            for v in p.get("variants") or []:
                opts = [v.get("option1"), v.get("option2"), v.get("option3")]
                named = {n: o for n, o in zip(names, opts) if o}
                imgs = p.get("images") or []
                yield {
                    "product_url": f"https://{retailer.domain}/products/{p.get('handle')}?variant={v.get('id')}",
                    "retailer_sku": str(v.get("sku") or v.get("id")),
                    "product_title": f"{p.get('title')} {v.get('title') if v.get('title') != 'Default Title' else ''}".strip(),
                    "brand": p.get("vendor") or retailer.name,
                    "model_number": v.get("sku") or "",
                    "gtin": v.get("barcode") or "",
                    "category": p.get("product_type") or "",
                    "storage_capacity": named.get("storage") or next((o for o in opts if o and "gb" in o.lower()), ""),
                    "variant_size": named.get("size") or named.get("shoe size") or "",
                    "variant_colour": named.get("color") or named.get("colour") or "",
                    "price": v.get("price"),
                    "stock_status": "in_stock" if v.get("available", True) else "out_of_stock",
                    "image_url": imgs[0]["src"] if imgs else "",
                }
        time.sleep(1.5)


def run_feed(db: Session, retailer: Retailer) -> ImportRun:
    if retailer.status != "active":
        raise PermissionError("Only active stores (that agreed to share data) can be imported")
    if retailer.feed_method == "feed_url" and retailer.feed_url:
        text = fetch(retailer.feed_url).text
        return import_csv_text(db, text, source="feed_url", retailer=retailer, filename=retailer.feed_url,
                               allow_create=False, full_snapshot=True)
    if retailer.feed_method == "shopify":
        if not retailer.permission_reference:
            raise PermissionError("Shopify import needs the retailer's written permission recorded first")
        return import_rows(db, shopify_rows(retailer), source="shopify", retailer=retailer,
                           filename=retailer.domain, allow_create=False, full_snapshot=True)
    raise ValueError("retailer has no automatic feed")


def run_all_feeds(db: Session, log=print):
    rs = db.scalars(select(Retailer).where(Retailer.status == "active",
                                           Retailer.feed_method.in_(["feed_url", "shopify"]))).all()
    for r in rs:
        try:
            run = run_feed(db, r)
            log(f"{r.name}: {run.rows_ok} ok, {run.rows_review} review, {run.rows_rejected} rejected")
        except Exception as e:
            db.rollback()
            db.add(ImportRun(retailer_id=r.id, source=r.feed_method, filename=r.feed_url, status="failed",
                             error=str(e)[:2000], finished_at=now()))
            db.commit()
            log(f"{r.name}: FAILED {e}")


def check_alerts(db: Session, log=print) -> int:
    sent = 0
    for a in db.scalars(select(PriceAlert).where(PriceAlert.active, PriceAlert.confirmed)):
        offers = [o for o in offers_for_variant(db, a.variant, sort="item") if o.stock_status != "out_of_stock"]
        if not offers:
            continue
        best = offers[0]
        if best.price <= a.target_price and (a.last_notified_price is None or best.price < a.last_notified_price):
            p = a.variant.product
            send_email(db, a.email, f"Price drop: {p.title} is now Rs {best.price:,.0f}",
                       f"Good news! {p.title} ({a.variant.label}) is Rs {best.price:,.0f} at {best.retailer.name}.\n"
                       f"Your target was Rs {a.target_price:,.0f}.\n\n"
                       f"Compare offers: {settings.BASE_URL}/p/{p.slug}?v={a.variant_id}\n\n"
                       f"Prices can change; always confirm at the retailer's checkout.\n"
                       f"Stop this alert: {settings.BASE_URL}/alerts/unsubscribe/{a.token}")
            a.last_notified_price = best.price
            sent += 1
    db.commit()
    log(f"alerts sent: {sent}")
    return sent


def stale_report(db: Session) -> dict:
    t = now()
    q = select(Offer).where(Offer.active)
    total = stale = hidden = 0
    for o in db.scalars(q):
        total += 1
        h = (t - o.checked_at).total_seconds() / 3600
        if h > settings.HIDE_HOURS:
            hidden += 1
        elif h > settings.STALE_HOURS:
            stale += 1
    return {"total": total, "stale": stale, "hidden": hidden}


def scheduler(session_factory, feed_every_hours: int = 6, alerts_every_minutes: int = 60):
    last_feed = last_alert = 0.0
    while True:
        t = time.time()
        if t - last_feed > feed_every_hours * 3600:
            with session_factory() as db:
                run_all_feeds(db)
            last_feed = t
        if t - last_alert > alerts_every_minutes * 60:
            with session_factory() as db:
                check_alerts(db)
            last_alert = t
        time.sleep(30)

