"""Admin panel: catalogue, retailers, offers, imports, match review,
reports, sponsored campaigns, users, analytics and audit log."""
import csv
import io
import secrets
import statistics
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from .config import settings
from .db import get_db
from .importer import (export_offers_csv, host_allowed, import_csv_text, template_csv)
from .jobs import run_feed
from .matching import create_product, create_variant, get_or_create_category, unique_slug, variant_key
from .models import (AffiliateConversion, AuditLog, Category, ClickEvent, ContactMessage, EmailOutbox,
                     ImportRun, MatchCandidate, Offer, PriceAlert, PriceHistory, PriceReport, Product, ProductView,
                     Retailer, SearchLog, SponsoredCampaign, User, Variant, now)
from .security import hash_password, require_csrf
from .text import search_text_for, slugify
from .web import flash, redirect, render, require_admin, require_staff

router = APIRouter(prefix="/admin")
csrf = [Depends(require_csrf)]


def audit(db, user, action, entity=None, entity_id=None, **detail):
    db.add(AuditLog(user_id=user.id, action=action, entity=entity, entity_id=entity_id,
                    detail={k: str(v) for k, v in detail.items()}))


def dec(v, field="value"):
    if v in (None, ""):
        return None
    try:
        return Decimal(str(v).replace(",", ""))
    except InvalidOperation:
        raise HTTPException(400, f"{field} must be a number")


# ------------------------------------------------------------------ dashboard

def metrics(db: Session, days: int = 30) -> dict:
    since = now() - timedelta(days=days)
    searches = db.scalar(select(func.count()).select_from(SearchLog).where(SearchLog.created_at >= since)) or 0
    visitors = db.scalar(select(func.count(func.distinct(SearchLog.session_id))).where(SearchLog.created_at >= since)) or 0
    views = db.scalar(select(func.count()).select_from(ProductView).where(ProductView.created_at >= since)) or 0
    views_from_search = db.scalar(select(func.count()).select_from(ProductView).where(
        ProductView.created_at >= since, ProductView.from_search)) or 0
    clicks = db.scalar(select(func.count()).select_from(ClickEvent).where(
        ClickEvent.created_at >= since, ClickEvent.is_bot.is_(False))) or 0
    bot_clicks = db.scalar(select(func.count()).select_from(ClickEvent).where(
        ClickEvent.created_at >= since, ClickEvent.is_bot)) or 0
    products = db.scalar(select(func.count()).select_from(Product)) or 0
    live = db.execute(select(Variant.product_id, Offer.retailer_id, Offer.checked_at).join(Offer)
                      .join(Retailer).where(Offer.active, Offer.match_status == "matched",
                                            Retailer.status == "active")).all()
    per_product = {}
    ages = []
    for pid, rid, ts in live:
        per_product.setdefault(pid, set()).add(rid)
        ages.append((now() - ts).total_seconds() / 3600)
    covered = sum(1 for s in per_product.values() if len(s) >= 2)
    stale = sum(1 for a in ages if settings.STALE_HOURS < a <= settings.HIDE_HOURS)
    hidden = sum(1 for a in ages if a > settings.HIDE_HOURS)
    commission = db.scalar(select(func.coalesce(func.sum(AffiliateConversion.commission), 0)).where(
        AffiliateConversion.order_status == "approved", AffiliateConversion.created_at >= since)) or 0
    return {
        "days": days, "searches": searches, "visitors": visitors,
        "searches_per_visitor": round(searches / visitors, 2) if visitors else 0,
        "search_to_product": round(100 * views_from_search / searches, 1) if searches else 0,
        "views": views, "clicks": clicks, "bot_clicks": bot_clicks,
        "outbound_ctr": round(100 * clicks / views, 1) if views else 0,
        "products": products, "coverage": round(100 * covered / products, 1) if products else 0,
        "covered": covered, "offers_live": len(ages),
        "median_age_h": round(statistics.median(ages), 1) if ages else None,
        "stale": stale, "hidden": hidden,
        "alerts": db.scalar(select(func.count()).select_from(PriceAlert).where(
            PriceAlert.confirmed, PriceAlert.active)) or 0,
        "commission": commission, "epc": round(Decimal(commission) / clicks, 2) if clicks else 0,
        "review": db.scalar(select(func.count()).select_from(Offer).where(Offer.match_status.in_(["review", "unmatched"]), Offer.active)) or 0,
        "reports": db.scalar(select(func.count()).select_from(PriceReport).where(PriceReport.status == "open")) or 0,
        "messages": db.scalar(select(func.count()).select_from(ContactMessage).where(ContactMessage.status == "open")) or 0,
        "pending_retailers": db.scalar(select(func.count()).select_from(Retailer).where(Retailer.status == "pending")) or 0,
    }


@router.get("")
def dashboard(request: Request, days: int = 30, db: Session = Depends(get_db), u=Depends(require_staff)):
    m = metrics(db, days)
    top_q = db.execute(select(SearchLog.query, func.count(), func.min(SearchLog.results))
                       .where(SearchLog.created_at >= now() - timedelta(days=days))
                       .group_by(SearchLog.query).order_by(func.count().desc()).limit(10)).all()
    zero_q = db.execute(select(SearchLog.query, func.count()).where(SearchLog.results == 0,
                        SearchLog.created_at >= now() - timedelta(days=days))
                        .group_by(SearchLog.query).order_by(func.count().desc()).limit(10)).all()
    runs = db.scalars(select(ImportRun).order_by(ImportRun.id.desc()).limit(8)).all()
    return render(request, "admin/dashboard.html", {"m": m, "top_q": top_q, "zero_q": zero_q, "runs": runs})


# ------------------------------------------------------------------ retailers

RETAILER_FIELDS = ["name", "domain", "city", "delivery_regions", "phone", "email", "address",
                   "return_policy_url", "warranty_policy_url", "description", "logo_url", "status",
                   "verification_notes", "feed_method", "feed_url", "permission_reference",
                   "affiliate_status", "affiliate_param", "plan"]


@router.get("/retailers")
def retailers(request: Request, db: Session = Depends(get_db), u=Depends(require_staff)):
    rs = db.scalars(select(Retailer).order_by(Retailer.status, Retailer.name)).all()
    counts = dict(db.execute(select(Offer.retailer_id, func.count()).where(Offer.active)
                             .group_by(Offer.retailer_id)).all())
    clicks = dict(db.execute(select(ClickEvent.retailer_id, func.count()).where(
        ClickEvent.is_bot.is_(False), ClickEvent.created_at >= now() - timedelta(days=30))
        .group_by(ClickEvent.retailer_id)).all())
    return render(request, "admin/retailers.html", {"retailers": rs, "counts": counts, "clicks": clicks})


@router.get("/retailers/new")
@router.get("/retailers/{rid}")
def retailer_form(request: Request, rid: int | None = None, db: Session = Depends(get_db), u=Depends(require_staff)):
    r = db.get(Retailer, rid) if rid else Retailer(status="active", feed_method="csv", plan="free",
                                                   affiliate_status="none")
    if rid and not r:
        raise HTTPException(404)
    runs = db.scalars(select(ImportRun).where(ImportRun.retailer_id == rid).order_by(ImportRun.id.desc())
                      .limit(10)).all() if rid else []
    users = db.scalars(select(User).where(User.retailer_id == rid)).all() if rid else []
    return render(request, "admin/retailer_form.html", {"r": r, "runs": runs, "users": users})


@router.post("/retailers/save", dependencies=csrf)
async def retailer_save(request: Request, db: Session = Depends(get_db), u=Depends(require_staff)):
    form = await request.form()
    rid = form.get("id")
    r = db.get(Retailer, int(rid)) if rid else Retailer()
    for f in RETAILER_FIELDS:
        val = (form.get(f) or "").strip()
        setattr(r, f, val or None)
    r.domain = (r.domain or "").lower().removeprefix("https://").removeprefix("http://").removeprefix("www.").split("/")[0]
    if not r.name or "." not in r.domain:
        flash(request, "Name and a valid domain are required.", "err")
        return redirect(f"/admin/retailers/{rid}" if rid else "/admin/retailers/new")
    r.status = r.status or "active"
    r.feed_method = r.feed_method or "csv"
    r.affiliate_status = r.affiliate_status or "none"
    r.plan = r.plan or "free"
    r.verified = form.get("verified") == "on"
    if r.verified and not r.verification_notes:
        flash(request, "Add verification evidence before marking a store as verified.", "err")
        r.verified = False
    if not r.slug:
        base, i = slugify(r.name), 2
        r.slug = base
        while db.scalar(select(Retailer.id).where(Retailer.slug == r.slug)):
            r.slug, i = f"{base}-{i}", i + 1
    db.add(r)
    db.flush()
    audit(db, u, "retailer_save", "retailer", r.id, status=r.status, verified=r.verified, plan=r.plan)
    db.commit()
    flash(request, f"Saved {r.name}.")
    return redirect(f"/admin/retailers/{r.id}")


@router.post("/retailers/{rid}/run-feed", dependencies=csrf)
def retailer_run_feed(rid: int, request: Request, db: Session = Depends(get_db), u=Depends(require_staff)):
    r = db.get(Retailer, rid)
    try:
        run = run_feed(db, r)
        flash(request, f"Feed imported: {run.rows_ok} ok, {run.rows_review} for review, {run.rows_rejected} rejected.")
        return redirect(f"/admin/imports/{run.id}")
    except Exception as e:
        db.rollback()
        flash(request, f"Feed failed: {e}", "err")
        return redirect(f"/admin/retailers/{rid}")


# ------------------------------------------------------------------ products & variants

@router.get("/products")
def products(request: Request, q: str = "", db: Session = Depends(get_db), u=Depends(require_staff)):
    query = select(Product).options(selectinload(Product.variants), selectinload(Product.category))
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(Product.title).like(like), func.lower(Product.brand).like(like),
                                func.lower(Product.model_number).like(like)))
    ps = db.scalars(query.order_by(Product.id.desc()).limit(200)).all()
    counts = dict(db.execute(select(Variant.product_id, func.count(Offer.id)).join(Offer)
                             .where(Offer.active, Offer.match_status == "matched")
                             .group_by(Variant.product_id)).all())
    return render(request, "admin/products.html", {"products": ps, "q": q, "counts": counts})


@router.get("/products/new")
@router.get("/products/{pid}")
def product_form(request: Request, pid: int | None = None, db: Session = Depends(get_db), u=Depends(require_staff)):
    p = db.get(Product, pid) if pid else Product(specs={})
    if pid and not p:
        raise HTTPException(404)
    cats = db.scalars(select(Category).order_by(Category.name)).all()
    offers = []
    if pid:
        offers = db.scalars(select(Offer).join(Variant).where(Variant.product_id == pid)
                            .options(selectinload(Offer.retailer))).all()
    return render(request, "admin/product_form.html", {"p": p, "cats": cats, "offers": offers})


@router.post("/products/save", dependencies=csrf)
async def product_save(request: Request, db: Session = Depends(get_db), u=Depends(require_staff)):
    f = await request.form()
    pid = f.get("id")
    p = db.get(Product, int(pid)) if pid else Product()
    p.title = (f.get("title") or "").strip()
    p.brand = (f.get("brand") or "").strip()
    if not p.title or not p.brand:
        flash(request, "Title and brand are required.", "err")
        return redirect(f"/admin/products/{pid}" if pid else "/admin/products/new")
    p.model_number = (f.get("model_number") or "").strip() or None
    p.image_url = (f.get("image_url") or "").strip() or None
    p.description = (f.get("description") or "").strip() or None
    cat_name = (f.get("category_new") or "").strip()
    p.category = get_or_create_category(db, cat_name) if cat_name else (
        db.get(Category, int(f["category_id"])) if f.get("category_id") else None)
    specs = {}
    for line in (f.get("specs") or "").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            if k.strip():
                specs[k.strip()] = v.strip()
    p.specs = specs
    if not p.slug:
        p.slug = unique_slug(db, slugify(f"{p.brand} {p.title}" if p.brand.lower() not in p.title.lower() else p.title))
    db.add(p)
    db.flush()
    if not p.variants:
        create_variant(db, p, {})
    p.search_text = search_text_for(p)
    audit(db, u, "product_save", "product", p.id, title=p.title)
    db.commit()
    flash(request, "Product saved.")
    return redirect(f"/admin/products/{p.id}")


@router.post("/products/{pid}/variants", dependencies=csrf)
async def variant_save(pid: int, request: Request, db: Session = Depends(get_db), u=Depends(require_staff)):
    f = await request.form()
    p = db.get(Product, pid)
    vid = f.get("variant_id")
    v = db.get(Variant, int(vid)) if vid else Variant(product=p)
    for k in ("storage", "ram", "colour", "size", "region", "gtin"):
        setattr(v, k, (f.get(k) or "").strip() or None)
    v.variant_key = variant_key(v.storage, v.ram, v.colour, v.size, v.region)
    clash = [x for x in p.variants if x.variant_key == v.variant_key and x is not v]
    if clash:
        flash(request, "A variant with exactly these attributes already exists.", "err")
        db.rollback()
        return redirect(f"/admin/products/{pid}")
    db.add(v)
    db.flush()
    p.search_text = search_text_for(p)
    audit(db, u, "variant_save", "variant", v.id, label=v.label)
    db.commit()
    flash(request, "Variant saved.")
    return redirect(f"/admin/products/{pid}")


@router.post("/variants/{vid}/delete", dependencies=csrf)
def variant_delete(vid: int, request: Request, db: Session = Depends(get_db), u=Depends(require_staff)):
    v = db.get(Variant, vid)
    pid = v.product_id
    if v.offers:
        flash(request, "Move or unlink this variant's offers first.", "err")
        return redirect(f"/admin/products/{pid}")
    audit(db, u, "variant_delete", "variant", vid, label=v.label)
    db.delete(v)
    db.commit()
    return redirect(f"/admin/products/{pid}")


@router.post("/products/{pid}/delete", dependencies=csrf)
def product_delete(pid: int, request: Request, db: Session = Depends(get_db), u=Depends(require_admin)):
    p = db.get(Product, pid)
    for v in p.variants:
        for o in v.offers:
            o.variant_id, o.match_status, o.match_method = None, "unmatched", "product_deleted"
    audit(db, u, "product_delete", "product", pid, title=p.title)
    db.delete(p)
    db.commit()
    flash(request, "Product deleted; its offers moved to the review queue.")
    return redirect("/admin/products")


# ------------------------------------------------------------------ offers

@router.get("/offers")
def offers(request: Request, status: str = "", retailer: int | None = None, db: Session = Depends(get_db),
           u=Depends(require_staff)):
    q = select(Offer).options(selectinload(Offer.retailer), selectinload(Offer.variant).selectinload(Variant.product))
    if retailer:
        q = q.where(Offer.retailer_id == retailer)
    if status == "stale":
        q = q.where(Offer.active, Offer.checked_at < now() - timedelta(hours=settings.STALE_HOURS))
    elif status == "inactive":
        q = q.where(Offer.active.is_(False))
    elif status in ("review", "unmatched", "matched"):
        q = q.where(Offer.match_status == status, Offer.active)
    os_ = db.scalars(q.order_by(Offer.checked_at.asc() if status == "stale" else Offer.id.desc()).limit(300)).all()
    rs = db.scalars(select(Retailer).order_by(Retailer.name)).all()
    return render(request, "admin/offers.html", {"offers": os_, "status": status, "retailer": retailer, "retailers": rs})


@router.get("/offers/new")
@router.get("/offers/{oid}")
def offer_form(request: Request, oid: int | None = None, variant: int | None = None,
               db: Session = Depends(get_db), u=Depends(require_staff)):
    o = db.get(Offer, oid) if oid else Offer(variant_id=variant, currency="PKR", stock_status="in_stock",
                                              condition="new")
    if oid and not o:
        raise HTTPException(404)
    rs = db.scalars(select(Retailer).order_by(Retailer.name)).all()
    hist = db.scalars(select(PriceHistory).where(PriceHistory.offer_id == oid)
                      .order_by(PriceHistory.captured_at.desc()).limit(50)).all() if oid else []
    v = db.get(Variant, o.variant_id) if o.variant_id else None
    return render(request, "admin/offer_form.html", {"o": o, "retailers": rs, "history": hist, "v": v})


@router.post("/offers/save", dependencies=csrf)
async def offer_save(request: Request, db: Session = Depends(get_db), u=Depends(require_staff)):
    f = await request.form()
    oid = f.get("id")
    o = db.get(Offer, int(oid)) if oid else Offer(source="manual")
    r = db.get(Retailer, int(f["retailer_id"]))
    url = (f.get("product_url") or "").strip()
    if not host_allowed(url, r.domain):
        flash(request, f"The product URL must be on {r.domain}.", "err")
        return redirect(f"/admin/offers/{oid}" if oid else f"/admin/offers/new?variant={f.get('variant_id', '')}")
    price = dec(f.get("price"), "price")
    ship = dec(f.get("shipping_cost"), "shipping")
    changed = (o.id is None or o.price != price or o.shipping_cost != ship
               or o.stock_status != f.get("stock_status"))
    o.retailer = r
    o.retailer_sku = (f.get("retailer_sku") or "").strip() or url
    o.retailer_title = (f.get("retailer_title") or "").strip() or o.retailer_sku
    o.product_url, o.price, o.shipping_cost = url, price, ship
    o.currency = (f.get("currency") or "PKR").upper()
    o.stock_status = f.get("stock_status") or "in_stock"
    o.condition = f.get("condition") or "new"
    o.warranty_type = (f.get("warranty_type") or "").strip() or None
    o.permission_reference = (f.get("permission_reference") or "").strip() or r.permission_reference
    o.checked_at = now()
    o.active = f.get("active", "on") == "on"
    vid = f.get("variant_id")
    if vid:
        o.variant_id = int(vid)
        o.match_status, o.match_method, o.match_confidence = "matched", "manual", 1.0
        o.match_evidence = f"Linked manually by {u.email}"
    db.add(o)
    db.flush()
    if changed:
        db.add(PriceHistory(offer_id=o.id, price=o.price, shipping_cost=o.shipping_cost,
                            stock_status=o.stock_status, captured_at=o.checked_at))
    audit(db, u, "offer_save", "offer", o.id, price=o.price, stock=o.stock_status)
    db.commit()
    flash(request, "Offer saved.")
    return redirect(f"/admin/offers/{o.id}")


@router.post("/offers/{oid}/recheck", dependencies=csrf)
def offer_recheck(oid: int, request: Request, db: Session = Depends(get_db), u=Depends(require_staff)):
    """Admin confirms the price is still correct (checked on the retailer site)."""
    o = db.get(Offer, oid)
    o.checked_at = now()
    audit(db, u, "offer_recheck", "offer", oid)
    db.commit()
    flash(request, "Marked as checked now.")
    return redirect(request.headers.get("referer") or f"/admin/offers/{oid}")


# ------------------------------------------------------------------ imports

@router.get("/imports")
def imports(request: Request, db: Session = Depends(get_db), u=Depends(require_staff)):
    runs = db.scalars(select(ImportRun).order_by(ImportRun.id.desc()).limit(100)).all()
    rs = db.scalars(select(Retailer).order_by(Retailer.name)).all()
    return render(request, "admin/imports.html", {"runs": runs, "retailers": rs,
                                                  "names": {r.id: r.name for r in rs}})


@router.post("/imports", dependencies=csrf)
async def import_upload(request: Request, file: UploadFile = File(...), retailer_id: str = Form(""),
                        allow_create: str = Form(""), db: Session = Depends(get_db), u=Depends(require_staff)):
    raw = await file.read()
    if len(raw) > 10 * 1024 * 1024:
        flash(request, "File is larger than 10 MB.", "err")
        return redirect("/admin/imports")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    r = db.get(Retailer, int(retailer_id)) if retailer_id else None
    run = import_csv_text(db, text, source="csv_upload", retailer=r, user_id=u.id, filename=file.filename,
                          allow_create=bool(allow_create))
    audit(db, u, "import", "import_run", run.id, ok=run.rows_ok, rejected=run.rows_rejected)
    db.commit()
    return redirect(f"/admin/imports/{run.id}")


@router.get("/imports/template.csv")
def import_template(u=Depends(require_staff)):
    return Response(template_csv(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=offers-template.csv"})


@router.get("/imports/{rid}")
def import_detail(rid: int, request: Request, db: Session = Depends(get_db), u=Depends(require_staff)):
    run = db.get(ImportRun, rid)
    if not run:
        raise HTTPException(404)
    r = db.get(Retailer, run.retailer_id) if run.retailer_id else None
    return render(request, "admin/import_detail.html", {"run": run, "retailer": r, "back": "/admin/imports"})


@router.get("/imports/{rid}/rejects.csv")
def import_rejects_csv(rid: int, db: Session = Depends(get_db), u=Depends(require_staff)):
    return _rejects_csv(db.get(ImportRun, rid))


def _rejects_csv(run):
    buf = io.StringIO()
    cols = sorted({k for rj in run.rejects for k in rj.row})
    w = csv.writer(buf)
    w.writerow(["row_number", "reasons"] + cols)
    for rj in run.rejects:
        w.writerow([rj.row_number, rj.reasons] + [rj.row.get(c, "") for c in cols])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=rejected-rows-{run.id}.csv"})


@router.get("/export.csv")
def export_csv(db: Session = Depends(get_db), u=Depends(require_staff)):
    return Response(export_offers_csv(db), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=offers-export.csv"})


# ------------------------------------------------------------------ match review queue

@router.get("/review")
def review(request: Request, db: Session = Depends(get_db), u=Depends(require_staff)):
    os_ = db.scalars(select(Offer).where(Offer.match_status.in_(["review", "unmatched"]), Offer.active)
                     .options(selectinload(Offer.retailer)).order_by(Offer.id).limit(50)).all()
    cands = {}
    for o in os_:
        cands[o.id] = db.scalars(select(MatchCandidate).where(MatchCandidate.offer_id == o.id,
                                 MatchCandidate.status == "open").order_by(MatchCandidate.score.desc())).all()
    return render(request, "admin/review.html", {"offers": os_, "cands": cands})


@router.post("/review/{oid}", dependencies=csrf)
async def review_decide(oid: int, request: Request, db: Session = Depends(get_db), u=Depends(require_staff)):
    f = await request.form()
    o = db.get(Offer, oid)
    action = f.get("action")
    if action == "link":
        vid = int(f.get("variant_id") or 0)
        v = db.get(Variant, vid)
        if not v:
            flash(request, "Choose a product variant (enter its ID).", "err")
            return redirect("/admin/review")
        o.variant, o.match_status, o.match_method, o.match_confidence = v, "matched", "manual", 1.0
        o.match_evidence = f"Linked by {u.email}; original title: {o.retailer_title}"
        for c in db.scalars(select(MatchCandidate).where(MatchCandidate.offer_id == oid)):
            c.status = "accepted" if c.variant_id == vid else "rejected"
        v.product.search_text = search_text_for(v.product)
    elif action == "create":
        row = dict(o.raw)
        row["product_title"] = f.get("title") or o.retailer_title
        row["brand"] = f.get("brand") or row.get("brand") or o.retailer.name
        row["model_number"] = f.get("model_number") or row.get("model_number")
        p = create_product(db, row)
        v = create_variant(db, p, row)
        o.variant, o.match_status, o.match_method, o.match_confidence = v, "matched", "manual_new", 1.0
        o.match_evidence = f"New product created by {u.email}"
        for c in db.scalars(select(MatchCandidate).where(MatchCandidate.offer_id == oid)):
            c.status = "rejected"
    elif action == "ignore":
        o.active = False
        o.match_evidence = f"Ignored by {u.email}"
    audit(db, u, f"review_{action}", "offer", oid)
    db.commit()
    flash(request, "Saved.")
    return redirect("/admin/review")


# ------------------------------------------------------------------ reports & messages

@router.get("/reports")
def reports(request: Request, db: Session = Depends(get_db), u=Depends(require_staff)):
    rp = db.scalars(select(PriceReport).order_by(PriceReport.status, PriceReport.id.desc()).limit(200)).all()
    msgs = db.scalars(select(ContactMessage).order_by(ContactMessage.status, ContactMessage.id.desc()).limit(200)).all()
    return render(request, "admin/reports.html", {"reports": rp, "messages": msgs})


@router.post("/reports/{rid}", dependencies=csrf)
async def report_update(rid: int, request: Request, db: Session = Depends(get_db), u=Depends(require_staff)):
    f = await request.form()
    rp = db.get(PriceReport, rid)
    rp.status = "resolved"
    if f.get("hide_offer"):
        rp.offer.active = False
    audit(db, u, "report_resolve", "price_report", rid, hide=bool(f.get("hide_offer")))
    db.commit()
    return redirect("/admin/reports")


@router.post("/messages/{mid}", dependencies=csrf)
def message_close(mid: int, db: Session = Depends(get_db), u=Depends(require_staff)):
    db.get(ContactMessage, mid).status = "closed"
    db.commit()
    return redirect("/admin/reports")


# ------------------------------------------------------------------ sponsored, conversions

@router.get("/campaigns")
def campaigns(request: Request, db: Session = Depends(get_db), u=Depends(require_staff)):
    cs = db.scalars(select(SponsoredCampaign).order_by(SponsoredCampaign.id.desc())).all()
    rs = db.scalars(select(Retailer).where(Retailer.status == "active").order_by(Retailer.name)).all()
    cats = db.scalars(select(Category).order_by(Category.name)).all()
    convs = db.scalars(select(AffiliateConversion).order_by(AffiliateConversion.id.desc()).limit(50)).all()
    return render(request, "admin/campaigns.html", {"campaigns": cs, "retailers": rs, "cats": cats, "convs": convs})


@router.post("/campaigns", dependencies=csrf)
async def campaign_save(request: Request, db: Session = Depends(get_db), u=Depends(require_staff)):
    f = await request.form()
    days = int(f.get("days") or 14)
    c = SponsoredCampaign(retailer_id=int(f["retailer_id"]), name=f.get("name") or "Campaign",
                          offer_id=int(f["offer_id"]) if f.get("offer_id") else None,
                          category_id=int(f["category_id"]) if f.get("category_id") else None,
                          ends_at=now() + timedelta(days=days), budget_note=f.get("budget_note") or None)
    if c.offer_id and db.get(Offer, c.offer_id).retailer_id != c.retailer_id:
        flash(request, "That offer belongs to a different retailer.", "err")
        return redirect("/admin/campaigns")
    db.add(c)
    db.flush()
    audit(db, u, "campaign_create", "campaign", c.id)
    db.commit()
    return redirect("/admin/campaigns")


@router.post("/campaigns/{cid}/toggle", dependencies=csrf)
def campaign_toggle(cid: int, db: Session = Depends(get_db), u=Depends(require_staff)):
    c = db.get(SponsoredCampaign, cid)
    c.active = not c.active
    audit(db, u, "campaign_toggle", "campaign", cid, active=c.active)
    db.commit()
    return redirect("/admin/campaigns")


@router.post("/conversions", dependencies=csrf)
async def conversion_add(request: Request, db: Session = Depends(get_db), u=Depends(require_staff)):
    f = await request.form()
    db.add(AffiliateConversion(network=f.get("network") or "direct", reference=f.get("reference") or None,
                               click_id=int(f["click_id"]) if f.get("click_id") else None,
                               order_status=f.get("order_status") or "pending",
                               commission=dec(f.get("commission"), "commission"),
                               validated_at=now() if f.get("order_status") == "approved" else None))
    audit(db, u, "conversion_add", "conversion")
    db.commit()
    return redirect("/admin/campaigns")


# ------------------------------------------------------------------ users, outbox, audit

@router.get("/users")
def users(request: Request, db: Session = Depends(get_db), u=Depends(require_admin)):
    us = db.scalars(select(User).order_by(User.role, User.email)).all()
    rs = db.scalars(select(Retailer).order_by(Retailer.name)).all()
    return render(request, "admin/users.html", {"users": us, "retailers": rs})


@router.post("/users", dependencies=csrf)
async def user_create(request: Request, db: Session = Depends(get_db), u=Depends(require_admin)):
    f = await request.form()
    email = (f.get("email") or "").strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        flash(request, "That email already has an account.", "err")
        return redirect("/admin/users")
    pw = secrets.token_urlsafe(12)
    role = f.get("role") if f.get("role") in ("admin", "editor", "merchant") else "editor"
    nu = User(email=email, name=f.get("name") or None, role=role, password_hash=hash_password(pw),
              retailer_id=int(f["retailer_id"]) if role == "merchant" and f.get("retailer_id") else None)
    db.add(nu)
    db.flush()
    audit(db, u, "user_create", "user", nu.id, role=role)
    db.commit()
    flash(request, f"User created. Temporary password (shown once): {pw}")
    return redirect("/admin/users")


@router.post("/users/{uid}", dependencies=csrf)
async def user_update(uid: int, request: Request, db: Session = Depends(get_db), u=Depends(require_admin)):
    f = await request.form()
    tu = db.get(User, uid)
    act = f.get("action")
    if act == "reset_mfa":
        tu.totp_secret = None
    elif act == "toggle":
        if tu.id == u.id:
            flash(request, "You cannot deactivate yourself.", "err")
            return redirect("/admin/users")
        tu.active = not tu.active
    elif act == "reset_password":
        pw = secrets.token_urlsafe(12)
        tu.password_hash = hash_password(pw)
        flash(request, f"New temporary password for {tu.email} (shown once): {pw}")
    audit(db, u, f"user_{act}", "user", uid)
    db.commit()
    return redirect("/admin/users")


@router.get("/outbox")
def outbox(request: Request, db: Session = Depends(get_db), u=Depends(require_staff)):
    ms = db.scalars(select(EmailOutbox).order_by(EmailOutbox.id.desc()).limit(100)).all()
    return render(request, "admin/outbox.html", {"emails": ms})


@router.get("/audit")
def audit_log(request: Request, db: Session = Depends(get_db), u=Depends(require_admin)):
    logs = db.scalars(select(AuditLog).options(selectinload(AuditLog.user)).order_by(AuditLog.id.desc()).limit(300)).all()
    return render(request, "admin/audit.html", {"logs": logs})

