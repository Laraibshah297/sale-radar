"""CSV / feed import: validate every row, upsert offers, keep price history,
send uncertain matches to the review queue, and record rejected rows with
reasons (blueprint 5.2 and MVP acceptance checklist)."""
import csv
import io
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from .matching import match_row, merge_specs
from .models import (ImportReject, ImportRun, MatchCandidate, Offer, PriceHistory, Retailer,
                     now)
from .text import search_text_for

CSV_COLUMNS = ["retailer_name", "retailer_domain", "product_url", "retailer_sku", "product_title",
               "brand", "model_number", "gtin", "category", "variant_colour", "variant_size",
               "storage_capacity", "ram", "region", "condition", "price", "currency",
               "shipping_cost", "stock_status", "warranty_type", "image_url", "checked_at",
               "permission_reference"]
# plus any number of spec_<key> columns, e.g. spec_processor, spec_screen_size,
# spec_fabric, spec_gender (see app/filters.py for the keys each category filters on)
REQUIRED = ["product_url", "product_title", "brand", "price"]
STOCK = {"in_stock", "out_of_stock", "preorder", "limited"}
STOCK_ALIASES = {"in stock": "in_stock", "instock": "in_stock", "available": "in_stock", "yes": "in_stock",
                 "out of stock": "out_of_stock", "outofstock": "out_of_stock", "no": "out_of_stock",
                 "sold out": "out_of_stock", "pre-order": "preorder", "pre order": "preorder"}
CONDITIONS = {"new", "used", "refurbished", "open_box"}
CURRENCIES = {"PKR", "USD", "AED", "GBP", "EUR", "INR"}


def domain_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def host_allowed(url: str, retailer_domain: str) -> bool:
    d = (retailer_domain or "").lower().removeprefix("www.")
    h = domain_of(url)
    return bool(d) and (h == d or h.endswith("." + d))


def parse_money(v) -> Decimal | None:
    if v is None or str(v).strip() == "":
        return None
    s = str(v).replace(",", "").replace("Rs.", "").replace("Rs", "").replace("PKR", "").strip()
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise ValueError(f"not a number: {v!r}")
    if d < 0:
        raise ValueError("negative amount")
    return d.quantize(Decimal("0.01"))


def parse_time(v) -> datetime | None:
    if not v or not str(v).strip():
        return None
    s = str(v).strip().replace("Z", "+00:00")
    for fmt in (None, "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            d = datetime.fromisoformat(s) if fmt is None else datetime.strptime(s, fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone(timedelta(hours=5)))  # PKT
        except ValueError:
            continue
    raise ValueError(f"unreadable date: {v!r}")


def clean_row(raw: dict) -> dict:
    row = {}
    for k, v in raw.items():
        if k is None:
            continue
        key = k.strip().lower().replace(" ", "_")
        row[key] = v.strip() if isinstance(v, str) else v
    return row


def validate(row: dict, retailer: Retailer | None) -> tuple[dict, list[str]]:
    errs = [f"missing {c}" for c in REQUIRED if not row.get(c)]
    out = dict(row)
    try:
        out["price"] = parse_money(row.get("price"))
        if out["price"] is not None and out["price"] <= 0:
            errs.append("price must be greater than 0")
    except ValueError as e:
        errs.append(f"price {e}")
    try:
        out["shipping_cost"] = parse_money(row.get("shipping_cost"))
    except ValueError as e:
        errs.append(f"shipping_cost {e}")
    cur = (row.get("currency") or "PKR").upper()
    if cur not in CURRENCIES:
        errs.append(f"unsupported currency {cur}")
    out["currency"] = cur
    url = row.get("product_url") or ""
    if url and urlparse(url).scheme not in ("http", "https"):
        errs.append("product_url must start with http:// or https://")
    elif url and retailer and not host_allowed(url, retailer.domain):
        errs.append(f"product_url host {domain_of(url)} is not the retailer domain {retailer.domain}")
    stock = (row.get("stock_status") or "in_stock").lower().strip()
    stock = STOCK_ALIASES.get(stock, stock.replace(" ", "_"))
    if stock not in STOCK:
        errs.append(f"stock_status must be one of {sorted(STOCK)}")
    out["stock_status"] = stock
    cond = (row.get("condition") or "new").lower().replace(" ", "_").replace("-", "_")
    if cond not in CONDITIONS:
        errs.append(f"condition must be one of {sorted(CONDITIONS)}")
    out["condition"] = cond
    try:
        ts = parse_time(row.get("checked_at"))
        if ts and ts > now() + timedelta(hours=1):
            errs.append("checked_at is in the future")
        out["checked_at"] = ts or now()
    except ValueError as e:
        errs.append(str(e))
    gtin = (row.get("gtin") or "").replace(" ", "")
    if gtin and not (gtin.isdigit() and len(gtin) in (8, 12, 13, 14)):
        errs.append("gtin must be 8, 12, 13 or 14 digits")
    out["gtin"] = gtin or None
    if not out.get("retailer_sku"):
        out["retailer_sku"] = url
    return out, errs


def resolve_retailer(db: Session, row: dict) -> Retailer | None:
    dom = (row.get("retailer_domain") or "").lower().removeprefix("www.")
    if not dom and row.get("product_url"):
        dom = domain_of(row["product_url"])
    if dom:
        for r in db.scalars(select(Retailer)):
            rd = r.domain.lower().removeprefix("www.")
            if dom == rd or dom.endswith("." + rd):
                return r
    name = (row.get("retailer_name") or "").strip().lower()
    if name:
        for r in db.scalars(select(Retailer)):
            if r.name.lower() == name:
                return r
    return None


def upsert_offer(db: Session, retailer: Retailer, row: dict, run: ImportRun | None, source: str,
                 allow_create: bool) -> str:
    """Returns 'ok' or 'review'."""
    offer = db.scalar(select(Offer).where(Offer.retailer_id == retailer.id,
                                          Offer.retailer_sku == row["retailer_sku"]))
    m = match_row(db, row, retailer.id, allow_create)
    changed = offer is None
    if offer is None:
        offer = Offer(retailer=retailer, retailer_sku=row["retailer_sku"])
        db.add(offer)
    else:
        changed = (offer.price != row["price"] or offer.shipping_cost != row["shipping_cost"]
                   or offer.stock_status != row["stock_status"])
    offer.retailer_title = row["product_title"]
    offer.product_url = row["product_url"]
    offer.price = row["price"]
    offer.currency = row["currency"]
    offer.shipping_cost = row["shipping_cost"]
    offer.stock_status = row["stock_status"]
    offer.condition = row["condition"]
    offer.warranty_type = row.get("warranty_type") or None
    offer.image_url = row.get("image_url") or None
    offer.checked_at = row["checked_at"]
    offer.source = source
    offer.import_run_id = run.id if run else None
    offer.permission_reference = row.get("permission_reference") or retailer.permission_reference
    offer.active = True
    offer.raw = {k: (str(v) if v is not None else None) for k, v in row.items()}
    # an admin's earlier manual decision wins over the automatic matcher
    if not (offer.match_method == "manual" and offer.variant_id):
        offer.variant = m.variant
        offer.match_status = m.status
        offer.match_method = m.method
        offer.match_confidence = m.confidence
        offer.match_evidence = m.evidence
    db.flush()
    if changed:
        db.add(PriceHistory(offer_id=offer.id, price=offer.price, shipping_cost=offer.shipping_cost,
                            stock_status=offer.stock_status, captured_at=offer.checked_at))
    if offer.match_status == "review" and m.candidates:
        existing = {c.variant_id for c in db.scalars(
            select(MatchCandidate).where(MatchCandidate.offer_id == offer.id, MatchCandidate.status == "open"))}
        for v, score, ev in m.candidates:
            if v.id not in existing:
                db.add(MatchCandidate(offer_id=offer.id, variant_id=v.id, score=score, evidence=ev))
    if offer.variant and offer.variant.product and not offer.variant.product.image_url and offer.image_url:
        offer.variant.product.image_url = offer.image_url
    if offer.variant:
        merge_specs(offer.variant.product, row)
        offer.variant.product.search_text = search_text_for(offer.variant.product)
    return "ok" if offer.match_status == "matched" else "review"


def import_rows(db: Session, rows, *, source: str, retailer: Retailer | None = None,
                user_id: int | None = None, filename: str | None = None,
                allow_create: bool = True, full_snapshot: bool = False) -> ImportRun:
    """Import an iterable of dict rows. If `retailer` is given (merchant portal
    or feed), every row is forced to that retailer. `full_snapshot` marks this
    retailer's offers missing from the file as inactive."""
    run = ImportRun(retailer_id=retailer.id if retailer else None, source=source,
                    filename=filename, user_id=user_id)
    db.add(run)
    db.flush()
    seen = {}
    try:
        for i, raw in enumerate(rows, start=2):  # row 1 = header
            run.rows_total += 1
            row = clean_row(raw)
            r = retailer or resolve_retailer(db, row)
            if retailer and row.get("retailer_domain") and resolve_retailer(db, row) not in (None, retailer):
                errs = ["row belongs to a different retailer"]
                clean = row
            elif not r:
                clean, errs = row, ["unknown retailer: add the retailer first (match by retailer_domain)"]
            else:
                clean, errs = validate(row, r)
            key = (r.id if r else None, clean.get("retailer_sku"))
            if not errs and key in seen:
                errs = [f"duplicate retailer_sku in file (also on row {seen[key]})"]
            if errs:
                run.rows_rejected += 1
                db.add(ImportReject(run_id=run.id, row_number=i, reasons="; ".join(errs),
                                    row={k: (str(v) if v is not None else None) for k, v in row.items()}))
                continue
            seen[key] = i
            with db.begin_nested():
                res = upsert_offer(db, r, clean, run, source, allow_create)
            if res == "ok":
                run.rows_ok += 1
            else:
                run.rows_review += 1
            r.last_import_at = now()
        if full_snapshot and retailer:
            skus = {k[1] for k in seen}
            for o in db.scalars(select(Offer).where(Offer.retailer_id == retailer.id, Offer.active)):
                if o.retailer_sku not in skus:
                    o.active = False
        run.status = "done" if run.rows_rejected == 0 else "done_with_errors"
    except Exception as e:  # keep the run record so admins see the failure
        run.status = "failed"
        run.error = str(e)[:2000]
        raise
    finally:
        run.finished_at = now()
        db.commit()
    return run


def import_csv_text(db: Session, text: str, **kw) -> ImportRun:
    text = text.lstrip("﻿")
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    return import_rows(db, reader, **kw)


def template_csv() -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_COLUMNS)
    w.writerow(["Example Store", "example.pk", "https://example.pk/products/galaxy-a55-256", "A55-256-BLK",
                "Samsung Galaxy A55 5G 256GB Awesome Navy", "Samsung", "SM-A556E", "", "Mobile Phones",
                "Awesome Navy", "", "256GB", "8GB", "PTA Approved", "new", "124999", "PKR", "0",
                "in_stock", "1 Year Official Warranty", "https://example.pk/img/a55.jpg",
                "2026-11-04 10:00", "Email from owner 2026-11-01"])
    return buf.getvalue()


def export_offers_csv(db: Session, retailer_id: int | None = None) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_COLUMNS + ["match_status", "product_slug"])
    q = select(Offer)
    if retailer_id:
        q = q.where(Offer.retailer_id == retailer_id)
    for o in db.scalars(q.order_by(Offer.id)):
        v = o.variant
        p = v.product if v else None
        w.writerow([o.retailer.name, o.retailer.domain, o.product_url, o.retailer_sku, o.retailer_title,
                     p.brand if p else o.raw.get("brand"), p.model_number if p else o.raw.get("model_number"),
                     v.gtin if v else "", p.category.name if p and p.category else "",
                     v.colour if v else "", v.size if v else "", v.storage if v else "", v.ram if v else "",
                     v.region if v else "", o.condition, o.price, o.currency,
                     "" if o.shipping_cost is None else o.shipping_cost, o.stock_status,
                     o.warranty_type or "", o.image_url or "", o.checked_at.isoformat(),
                     o.permission_reference or "", o.match_status, p.slug if p else ""])
    return buf.getvalue()
