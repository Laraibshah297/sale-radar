"""Merchant portal (the retailer SaaS side): upload feeds, see feed health,
traffic analytics, and on the Pro plan, competitor price monitoring."""
from datetime import timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .config import settings
from .db import get_db
from .importer import export_offers_csv, import_csv_text, template_csv
from .jobs import run_feed
from .models import AuditLog, ClickEvent, ImportRun, Offer, Retailer, Variant, now
from .security import require_csrf
from .services import offers_for_variant
from .web import flash, redirect, render, require_merchant

router = APIRouter(prefix="/merchant")
csrf = [Depends(require_csrf)]

PLANS = {
    "free": {"name": "Free listing", "price": "PKR 0", "features": [
        "Up to 500 offers", "CSV / Google Sheet uploads", "Feed health and rejected-row reports",
        "30-day click totals"]},
    "pro": {"name": "Merchant Pro", "price": "PKR 5,000–15,000 / month (pilot pricing)", "features": [
        "Unlimited offers", "Scheduled feed URL imports", "Daily click analytics by product",
        "Competitor price monitoring", "Priority support"]},
}
FREE_OFFER_LIMIT = 500


def _retailer(u) -> Retailer:
    if not u.retailer:
        raise HTTPException(403, "Your account is not linked to a store yet. Contact support.")
    return u.retailer


@router.get("")
def dashboard(request: Request, db: Session = Depends(get_db), u=Depends(require_merchant)):
    r = _retailer(u)
    since = now() - timedelta(days=30)
    offers = db.scalars(select(Offer).where(Offer.retailer_id == r.id, Offer.active)).all()
    stale = [o for o in offers if (now() - o.checked_at).total_seconds() / 3600 > settings.STALE_HOURS]
    review = [o for o in offers if o.match_status != "matched"]
    clicks = db.scalar(select(func.count()).select_from(ClickEvent).where(
        ClickEvent.retailer_id == r.id, ClickEvent.is_bot.is_(False), ClickEvent.created_at >= since)) or 0
    daily = []
    if r.plan == "pro":
        rows = db.execute(select(func.date(ClickEvent.created_at), func.count()).where(
            ClickEvent.retailer_id == r.id, ClickEvent.is_bot.is_(False), ClickEvent.created_at >= since)
            .group_by(func.date(ClickEvent.created_at)).order_by(func.date(ClickEvent.created_at))).all()
        daily = [(str(d), c) for d, c in rows]
    top = db.execute(select(Offer.retailer_title, func.count(ClickEvent.id)).join(ClickEvent, ClickEvent.offer_id == Offer.id)
                     .where(Offer.retailer_id == r.id, ClickEvent.is_bot.is_(False), ClickEvent.created_at >= since)
                     .group_by(Offer.retailer_title).order_by(func.count(ClickEvent.id).desc()).limit(10)).all()
    runs = db.scalars(select(ImportRun).where(ImportRun.retailer_id == r.id).order_by(ImportRun.id.desc()).limit(10)).all()
    return render(request, "merchant/dashboard.html", {
        "r": r, "offers": offers, "stale": stale, "review": review, "clicks": clicks, "daily": daily,
        "top": top, "runs": runs, "plans": PLANS, "limit": FREE_OFFER_LIMIT})


@router.post("/upload", dependencies=csrf)
async def upload(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db),
                 u=Depends(require_merchant)):
    r = _retailer(u)
    raw = await file.read()
    if len(raw) > 10 * 1024 * 1024:
        flash(request, "File is larger than 10 MB.", "err")
        return redirect("/merchant")
    text = raw.decode("utf-8-sig", errors="replace")
    if r.plan != "pro" and text.count("\n") > FREE_OFFER_LIMIT + 1:
        flash(request, f"The free plan supports up to {FREE_OFFER_LIMIT} offers per file. Upgrade to Pro for more.", "err")
        return redirect("/merchant")
    # merchants can only update their own store and can't create catalogue products
    run = import_csv_text(db, text, source="csv_upload", retailer=r, user_id=u.id, filename=file.filename,
                          allow_create=False)
    db.add(AuditLog(user_id=u.id, action="merchant_import", entity="import_run", entity_id=run.id))
    db.commit()
    return redirect(f"/merchant/imports/{run.id}")


@router.get("/imports/{rid}")
def import_detail(rid: int, request: Request, db: Session = Depends(get_db), u=Depends(require_merchant)):
    run = db.get(ImportRun, rid)
    if not run or run.retailer_id != u.retailer_id:
        raise HTTPException(404)
    return render(request, "admin/import_detail.html", {"run": run, "retailer": u.retailer, "back": "/merchant"})


@router.get("/imports/{rid}/rejects.csv")
def rejects(rid: int, db: Session = Depends(get_db), u=Depends(require_merchant)):
    from .routes_admin import _rejects_csv
    run = db.get(ImportRun, rid)
    if not run or run.retailer_id != u.retailer_id:
        raise HTTPException(404)
    return _rejects_csv(run)


@router.get("/template.csv")
def template(u=Depends(require_merchant)):
    return Response(template_csv(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=offers-template.csv"})


@router.get("/export.csv")
def export(db: Session = Depends(get_db), u=Depends(require_merchant)):
    r = _retailer(u)
    return Response(export_offers_csv(db, r.id), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=my-offers.csv"})


@router.post("/feed", dependencies=csrf)
def feed_settings(request: Request, feed_url: str = Form(""), db: Session = Depends(get_db),
                  u=Depends(require_merchant)):
    r = _retailer(u)
    if r.plan != "pro":
        flash(request, "Scheduled feed URLs are a Pro feature.", "err")
        return redirect("/merchant")
    feed_url = feed_url.strip()
    if feed_url and not feed_url.startswith("https://"):
        flash(request, "Feed URL must start with https:// (a published Google Sheet CSV link works).", "err")
        return redirect("/merchant")
    r.feed_url = feed_url or None
    r.feed_method = "feed_url" if feed_url else "csv"
    db.add(AuditLog(user_id=u.id, action="merchant_feed_url", entity="retailer", entity_id=r.id))
    db.commit()
    flash(request, "Feed URL saved. It will be imported automatically every few hours.")
    return redirect("/merchant")


@router.post("/feed/run", dependencies=csrf)
def feed_run(request: Request, db: Session = Depends(get_db), u=Depends(require_merchant)):
    r = _retailer(u)
    try:
        run = run_feed(db, r)
        return redirect(f"/merchant/imports/{run.id}")
    except Exception as e:
        db.rollback()
        flash(request, f"Feed failed: {e}", "err")
        return redirect("/merchant")


@router.get("/competitors")
def competitors(request: Request, db: Session = Depends(get_db), u=Depends(require_merchant)):
    """Pro: for each of my matched offers, how my price compares to the
    lowest other verified-store price for the exact same variant."""
    r = _retailer(u)
    rows = []
    if r.plan == "pro":
        mine = db.scalars(select(Offer).where(Offer.retailer_id == r.id, Offer.active, Offer.match_status == "matched")
                          .options(selectinload(Offer.variant).selectinload(Variant.product))).all()
        for o in mine:
            others = [x for x in offers_for_variant(db, o.variant, sort="item")
                      if x.retailer_id != r.id and x.stock_status != "out_of_stock"]
            best = others[0] if others else None
            rows.append({"o": o, "best": best, "n": len(others),
                         "diff": (o.price - best.price) if best else None})
        rows.sort(key=lambda x: -(x["diff"] or 0))
    return render(request, "merchant/competitors.html", {"r": r, "rows": rows})
