import secrets
from decimal import Decimal, InvalidOperation
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .config import settings
from .filters import GROUP_ORDER
from .db import get_db
from .importer import host_allowed
from .mailer import send_email
from .models import (Category, ClickEvent, ContactMessage, Offer, PriceAlert, PriceReport, Product,
                     ProductView, Retailer, SearchLog, User, Variant)
from .security import hash_password, looks_like_bot, require_csrf, session_id
from .services import (DEFAULT_KEYS, card_for, deal_quality, facets, offers_for_variant, price_history,
                       search_products, sort_cards, sponsored_for)
from .web import current_user, flash, redirect, render

router = APIRouter()


def _dec(v):
    try:
        return Decimal(str(v).replace(",", "")) if v not in (None, "") else None
    except InvalidOperation:
        return None


@router.get("/")
def home(request: Request, db: Session = Depends(get_db), _u=Depends(current_user)):
    cats = db.scalars(select(Category).order_by(Category.name)).all()
    groups = {}
    for c in cats:
        groups.setdefault(c.group or "Other", []).append(c)
    groups = sorted(groups.items(), key=lambda g: GROUP_ORDER.index(g[0]) if g[0] in GROUP_ORDER else 99)
    retailers = db.scalars(select(Retailer).where(Retailer.status == "active", Retailer.verified)
                           .order_by(Retailer.name)).all()
    popular, _, _ = search_products(db, "", limit=8)
    return render(request, "home.html", {"categories": cats, "groups": groups, "retailers": retailers,
                                         "popular": popular})


@router.get("/search")
def search(request: Request, q: str = "", db: Session = Depends(get_db), _u=Depends(current_user)):
    return _listing(request, db, q=q, category=None)


@router.get("/c/{slug}")
def category(slug: str, request: Request, db: Session = Depends(get_db), _u=Depends(current_user)):
    cat = db.scalar(select(Category).where(Category.slug == slug))
    if not cat:
        raise HTTPException(404)
    return _listing(request, db, q="", category=cat)


def _int(v, default=None):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _listing(request, db, *, q, category):
    qp = request.query_params
    page = max(_int(qp.get("page"), 1), 1)
    per = 24
    sort = qp.get("sort") or "relevance"
    store = _int(qp.get("store"))
    brands = [b for b in qp.getlist("brand") if b]
    # which filters to offer: the category's list, or a general set when searching everywhere
    all_cards, _, _ = search_products(db, q, category=category, limit=10000)
    keys = (category.filter_specs if category and category.filter_specs else None)
    if not keys:
        cats = {c.product.category.slug for c in all_cards if c.product.category}
        keys = (db.scalar(select(Category).where(Category.slug == next(iter(cats)))).filter_specs
                if len(cats) == 1 else DEFAULT_KEYS)
    chosen = {k: [v for v in qp.getlist(k) if v] for k in keys}
    chosen = {k: v for k, v in chosen.items() if v}
    kw = dict(category=category, retailer_id=store, min_price=_dec(qp.get("min")),
              max_price=_dec(qp.get("max")), in_stock=qp.get("stock") == "1", spec_filters=chosen)
    cards, total, fuzzy = [], 0, False
    for b in (brands or [None]):  # brands are OR'd
        cs, _, fz = search_products(db, q, brand=b, sort=sort, limit=10000, **kw)
        cards += cs
        fuzzy = fuzzy or fz
    if len(brands) > 1:
        cards = sort_cards(cards, q, sort)
    total = len(cards)
    cards = cards[(page - 1) * per: page * per]
    if q and page == 1:
        db.add(SearchLog(query=q[:300], results=total, session_id=session_id(request)))
        db.commit()
    retailers = db.scalars(select(Retailer).where(Retailer.status == "active").order_by(Retailer.name)).all()
    sponsored = sponsored_for(db, category_id=category.id) if category else []
    active = [(k, v) for k, vals in chosen.items() for v in vals] + [("brand", b) for b in brands]
    base_qs = [(k, v) for k, v in qp.multi_items() if k != "page"]
    return render(request, "listing.html", {
        "q": q, "category": category, "cards": cards, "total": total, "fuzzy": fuzzy,
        "facets": facets(all_cards, keys), "retailers": retailers, "sponsored": sponsored,
        "page": page, "pages": (total + per - 1) // per, "chosen": chosen, "brands": brands, "active": active,
        "base_qs": base_qs,
        "f": {"store": store, "min": qp.get("min", ""), "max": qp.get("max", ""), "stock": qp.get("stock") == "1",
              "sort": sort}})


@router.get("/p/{slug}")
def product(slug: str, request: Request, v: int | None = None, sort: str = "delivered", ref: str = "", cond: str = "",
            db: Session = Depends(get_db), _u=Depends(current_user)):
    p = db.scalar(select(Product).where(Product.slug == slug)
                  .options(selectinload(Product.variants), selectinload(Product.category)))
    if not p:
        raise HTTPException(404)
    variants = sorted(p.variants, key=lambda x: (len(x.storage or ""), x.storage or "", x.colour or ""))
    # default to the variant with the most offers
    counts = {x.id: len(offers_for_variant(db, x)) for x in variants}
    variant = next((x for x in variants if x.id == v), None) or (
        max(variants, key=lambda x: counts[x.id]) if variants else None)
    offers = offers_for_variant(db, variant, sort=sort) if variant else []
    # never rank new against used/refurbished: one condition at a time
    conditions = sorted({o.condition for o in offers}, key=lambda c: (c != "new", c))
    cond = cond if cond in conditions else (conditions[0] if conditions else "new")
    offers = [o for o in offers if o.condition == cond]
    pickers = variant_pickers(variants, variant, counts)
    hist = price_history(db, variant) if variant else []
    in_stock = [o for o in offers if o.stock_status != "out_of_stock"]
    current_low = min((o.price for o in in_stock), default=None)
    db.add(ProductView(product_id=p.id, session_id=session_id(request), from_search=(ref == "search")))
    db.commit()
    return render(request, "product.html", {
        "p": p, "variants": variants, "variant": variant, "counts": counts, "offers": offers, "sort": sort,
        "history": hist, "deal": deal_quality(current_low, hist), "current_low": current_low,
        "sponsored": sponsored_for(db, variant=variant) if variant else [],
        "card": card_for(p, offers),
        "pickers": pickers, "conditions": conditions, "cond": cond,
        "suggest": int(current_low * Decimal("0.95") // 100 * 100) if current_low else None})


PICK_ATTRS = [("colour", "Colour"), ("size", "Size"), ("storage", "Storage"), ("ram", "RAM"), ("region", "PTA / region")]


def variant_pickers(variants, current, counts):
    """One row of choices per attribute that differs between variants
    (e.g. Colour and Size). Each choice links to the variant that keeps the
    other current attributes; if that combination doesn't exist it links to
    the closest one and is shown faded."""
    from .filters import value_sort_key
    if not current or len(variants) < 2:
        return []
    rows = []
    for attr, label in PICK_ATTRS:
        values = {getattr(v, attr) for v in variants if getattr(v, attr)}
        if len(values) < 2:
            continue
        choices = []
        for val in sorted(values, key=lambda x: value_sort_key(attr, x)):
            same = [v for v in variants if getattr(v, attr) == val]
            exact = [v for v in same if all(getattr(v, a) == getattr(current, a) for a, _ in PICK_ATTRS if a != attr)]
            target = max(exact or same, key=lambda v: counts.get(v.id, 0))
            choices.append((val, target.id, val == getattr(current, attr),
                            bool(exact) and counts.get(target.id, 0) > 0))
        rows.append((label, choices))
    return rows


@router.get("/go/{offer_id}")
def go(offer_id: int, request: Request, src: str = "product", db: Session = Depends(get_db)):
    """Outbound redirect. Counts the click and only redirects to the offer's
    own URL when its host is the retailer's allow-listed domain."""
    o = db.get(Offer, offer_id)
    if not o or not o.active or o.retailer.status != "active":
        raise HTTPException(404)
    if not host_allowed(o.product_url, o.retailer.domain):
        raise HTTPException(400, "This link is not allowed.")
    db.add(ClickEvent(offer_id=o.id, retailer_id=o.retailer_id, session_id=session_id(request),
                      source=src[:60], referrer=(request.headers.get("referer") or "")[:500],
                      sponsored=(src == "sponsored"),
                      is_bot=looks_like_bot(request.headers.get("user-agent"))))
    db.commit()
    url = o.product_url
    if o.retailer.affiliate_status == "approved" and o.retailer.affiliate_param:
        url += ("&" if "?" in url else "?") + o.retailer.affiliate_param
    return RedirectResponse(url, status_code=302, headers={"X-Robots-Tag": "noindex"})


@router.get("/store/{slug}")
def store(slug: str, request: Request, db: Session = Depends(get_db), _u=Depends(current_user)):
    r = db.scalar(select(Retailer).where(Retailer.slug == slug, Retailer.status == "active"))
    if not r:
        raise HTTPException(404)
    cards, total, _ = search_products(db, "", retailer_id=r.id, limit=24)
    return render(request, "store.html", {"r": r, "cards": cards, "total": total})


@router.get("/stores")
def stores(request: Request, c: str = "", db: Session = Depends(get_db), _u=Depends(current_user)):
    rs = db.scalars(select(Retailer).where(Retailer.status == "active").order_by(Retailer.verified.desc(),
                                                                                  Retailer.name)).all()
    counts = dict(db.execute(select(Offer.retailer_id, func.count()).where(Offer.active)
                             .group_by(Offer.retailer_id)).all())
    # which categories each store sells, from its live offers
    rows = db.execute(select(Offer.retailer_id, Category.id).join(Variant, Variant.id == Offer.variant_id)
                      .join(Product, Product.id == Variant.product_id).join(Category, Category.id == Product.category_id)
                      .where(Offer.active, Offer.match_status == "matched").distinct()).all()
    cats = {x.id: x for x in db.scalars(select(Category).order_by(Category.name))}
    store_cats = {}
    for rid, cid in rows:
        store_cats.setdefault(rid, []).append(cats[cid])
    current = next((x for x in cats.values() if x.slug == c), None)
    if current:
        rs = [r for r in rs if current in store_cats.get(r.id, [])]
    used = sorted({x for v in store_cats.values() for x in v}, key=lambda x: (
        GROUP_ORDER.index(x.group) if x.group in GROUP_ORDER else 99, x.name))
    return render(request, "stores.html", {"retailers": rs, "counts": counts, "store_cats": store_cats,
                                           "cats": used, "current": current})


# ---------------------------------------------------------------- alerts

@router.post("/alerts", dependencies=[Depends(require_csrf)])
def create_alert(request: Request, variant_id: int = Form(...), email: str = Form(...),
                 target_price: str = Form(...), consent: str = Form(""), db: Session = Depends(get_db)):
    v = db.get(Variant, variant_id)
    target = _dec(target_price)
    email = email.strip().lower()
    if not v or not target or "@" not in email or not consent:
        flash(request, "Please enter a valid email, a target price and tick the consent box.", "err")
        return redirect(f"/p/{v.product.slug}" if v else "/")
    a = PriceAlert(email=email, variant_id=v.id, target_price=target, token=secrets.token_urlsafe(24))
    db.add(a)
    db.flush()
    send_email(db, email, f"Confirm your price alert for {v.product.title}",
               f"Please confirm you want an email when {v.product.title} ({v.label}) drops to "
               f"Rs {target:,.0f} or less:\n{settings.BASE_URL}/alerts/confirm/{a.token}\n\n"
               f"If you did not ask for this, ignore this email.")
    db.commit()
    flash(request, "Almost done: check your email and click the confirmation link.")
    return redirect(f"/p/{v.product.slug}?v={v.id}")


@router.get("/alerts/confirm/{token}")
def confirm_alert(token: str, request: Request, db: Session = Depends(get_db)):
    a = db.scalar(select(PriceAlert).where(PriceAlert.token == token))
    if not a:
        raise HTTPException(404)
    a.confirmed = True
    db.commit()
    flash(request, "Price alert confirmed. We'll email you when the price drops.")
    return redirect(f"/p/{a.variant.product.slug}?v={a.variant_id}")


@router.get("/alerts/unsubscribe/{token}")
def unsubscribe(token: str, request: Request, db: Session = Depends(get_db)):
    a = db.scalar(select(PriceAlert).where(PriceAlert.token == token))
    if a:
        a.active = False
        db.commit()
    return render(request, "pages/message.html", {"title": "Unsubscribed",
                                                   "body": "You will not get this price alert any more."})


# ---------------------------------------------------------------- reports, contact, merchant signup

@router.post("/report", dependencies=[Depends(require_csrf)])
def report(request: Request, offer_id: int = Form(...), reason: str = Form(...), note: str = Form(""),
           email: str = Form(""), db: Session = Depends(get_db)):
    o = db.get(Offer, offer_id)
    if not o:
        raise HTTPException(404)
    if reason not in {"wrong_price", "out_of_stock", "wrong_product", "other"}:
        reason = "other"
    db.add(PriceReport(offer_id=o.id, reason=reason, note=note[:2000], email=email[:200] or None))
    db.commit()
    flash(request, "Thank you. Our team will check this offer.")
    slug = o.variant.product.slug if o.variant else ""
    return redirect(f"/p/{slug}?v={o.variant_id}" if slug else "/")


@router.get("/contact")
def contact_page(request: Request, kind: str = "contact", _u=Depends(current_user)):
    return render(request, "pages/contact.html", {"kind": kind})


@router.post("/contact", dependencies=[Depends(require_csrf)])
def contact(request: Request, kind: str = Form("contact"), name: str = Form(""), email: str = Form(...),
            message: str = Form(...), db: Session = Depends(get_db)):
    if kind not in {"contact", "correction", "takedown"}:
        kind = "contact"
    db.add(ContactMessage(kind=kind, name=name[:160], email=email[:200], message=message[:5000]))
    db.commit()
    flash(request, "Message received. We usually reply within 2 working days.")
    return redirect("/contact")


@router.get("/merchants")
def merchants(request: Request, _u=Depends(current_user)):
    return render(request, "pages/merchants.html")


@router.post("/merchants/apply", dependencies=[Depends(require_csrf)])
def merchant_apply(request: Request, store_name: str = Form(...), domain: str = Form(...),
                   city: str = Form(""), contact_name: str = Form(""), email: str = Form(...),
                   phone: str = Form(""), password: str = Form(...), agree: str = Form(""),
                   db: Session = Depends(get_db)):
    from .text import slugify
    domain = domain.strip().lower().removeprefix("https://").removeprefix("http://").removeprefix("www.").split("/")[0]
    email = email.strip().lower()
    err = None
    if not agree:
        err = "Please accept the merchant data agreement."
    elif len(password) < 10:
        err = "Password must be at least 10 characters."
    elif db.scalar(select(User).where(User.email == email)):
        err = "An account with this email already exists. Please log in."
    elif "." not in domain:
        err = "Please enter your store's website domain, e.g. mystore.pk"
    if err:
        flash(request, err, "err")
        return redirect("/merchants#apply")
    slug, i = slugify(store_name), 2
    while db.scalar(select(Retailer.id).where(Retailer.slug == slug)):
        slug, i = f"{slugify(store_name)}-{i}", i + 1
    r = Retailer(name=store_name.strip(), slug=slug, domain=domain, city=city or None, email=email,
                 phone=phone or None, status="pending", feed_method="csv",
                 permission_reference=f"Merchant self-signup, data agreement accepted by {email}")
    db.add(r)
    db.flush()
    db.add(User(email=email, name=contact_name or None, password_hash=hash_password(password),
                role="merchant", retailer_id=r.id))
    db.add(ContactMessage(kind="merchant_application", name=contact_name, email=email,
                          message=f"New store application: {store_name} ({domain}), {city}, {phone}"))
    db.commit()
    flash(request, "Application received! Log in to upload your products while we verify your store.")
    return redirect("/login")


# ---------------------------------------------------------------- static pages, language, SEO

PAGES = {"about": "About", "how-prices-are-checked": "How prices are checked", "privacy": "Privacy policy",
         "terms": "Terms of use", "affiliate-disclosure": "Affiliate disclosure",
         "merchant-agreement": "Merchant data agreement"}


@router.get("/page/{name}")
def page(name: str, request: Request, _u=Depends(current_user)):
    if name not in PAGES:
        raise HTTPException(404)
    return render(request, f"pages/{name}.html", {"title": PAGES[name]})


@router.get("/lang/{code}")
def lang(code: str, request: Request):
    request.session["lang"] = "ur" if code == "ur" else "en"
    back = request.headers.get("referer") or "/"
    return redirect(back if back.startswith(settings.BASE_URL) or back.startswith("/") else "/")


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return (f"User-agent: *\nDisallow: /admin\nDisallow: /merchant\nDisallow: /go/\nDisallow: /alerts/\n"
            f"Sitemap: {settings.BASE_URL}/sitemap.xml\n")


@router.get("/sitemap.xml")
def sitemap(db: Session = Depends(get_db)):
    urls = [f"{settings.BASE_URL}/", f"{settings.BASE_URL}/stores"]
    urls += [f"{settings.BASE_URL}/c/{s}" for s in db.scalars(select(Category.slug))]
    urls += [f"{settings.BASE_URL}/p/{s}" for s in db.scalars(select(Product.slug))]
    urls += [f"{settings.BASE_URL}/store/{s}" for s in
             db.scalars(select(Retailer.slug).where(Retailer.status == "active"))]
    urls += [f"{settings.BASE_URL}/page/{n}" for n in PAGES]
    body = "".join(f"<url><loc>{escape(u)}</loc></url>" for u in urls)
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><urlset '
                    f'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>',
                    media_type="application/xml")


@router.get("/healthz", response_class=PlainTextResponse)
def healthz(db: Session = Depends(get_db)):
    db.execute(select(1))
    return "ok"
