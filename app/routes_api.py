"""REST API v1 & Model Context Protocol (MCP) JSON-RPC 2.0 Server.

Exposes structured endpoints for programmatic integrations, mobile apps,
and autonomous AI agents (Claude, Cursor, Antigravity, OpenAI) to search
products, verify 30-day price history, detect fake markdowns, and subscribe
to price-drop alerts.
"""
import secrets
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .config import settings
from .db import get_db
from .mailer import send_email
from .models import Category, PriceAlert, Product, Retailer, Variant
from .services import (card_for, deal_quality, freshness, offer_deal_audit,
                       offers_for_variant, price_history, search_products,
                       top_price_drops)

router = APIRouter()


class AlertCreateRequest(BaseModel):
    variant_id: int = Field(..., description="Target variant ID")
    email: str = Field(..., description="Shopper email address")
    target_price: float = Field(..., gt=0, description="Target price in PKR")


def _serialize_offer(o, category_slug=None, dq=None) -> dict:
    aud = offer_deal_audit(o, dq)
    return {
        "id": o.id,
        "retailer": {
            "id": o.retailer.id,
            "name": o.retailer.name,
            "slug": o.retailer.slug,
            "domain": o.retailer.domain,
            "verified": o.retailer.verified,
            "city": o.retailer.city,
        },
        "retailer_sku": o.retailer_sku,
        "retailer_title": o.retailer_title,
        "price": float(o.price),
        "original_price": float(o.original_price) if o.original_price is not None else None,
        "claimed_discount_pct": o.claimed_discount_pct,
        "promo_code": o.promo_code,
        "currency": o.currency,
        "shipping_cost": float(o.shipping_cost) if o.shipping_cost is not None else None,
        "delivered_price": float(o.delivered_price) if o.delivered_price is not None else None,
        "stock_status": o.stock_status,
        "condition": o.condition,
        "warranty_type": o.warranty_type,
        "freshness": freshness(o, category_slug),
        "checked_at": o.checked_at.isoformat(),
        "outbound_url": f"{settings.BASE_URL}/go/{o.id}?src=api",
        "deal_audit": aud,
    }


def _serialize_card(c) -> dict:
    p = c.product
    return {
        "id": p.id,
        "title": p.title,
        "slug": p.slug,
        "brand": p.brand,
        "model_number": p.model_number,
        "category": p.category.slug if p.category else None,
        "category_name": p.category.name if p.category else None,
        "lowest_price": float(c.lowest) if c.lowest is not None else None,
        "lowest_delivered_price": float(c.lowest_delivered) if c.lowest_delivered is not None else None,
        "currency": settings.DEFAULT_CURRENCY,
        "stores_count": c.stores,
        "in_stock": c.in_stock,
        "key_spec": c.key_spec,
        "updated_at": c.updated.isoformat() if c.updated else None,
        "url": f"{settings.BASE_URL}/p/{p.slug}",
    }


# ------------------------------------------------------------------ REST API v1

@router.get("/api/v1/health", tags=["System"])
def api_health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "service": settings.SITE_NAME, "currency": settings.DEFAULT_CURRENCY}


@router.get("/api/v1/categories", tags=["Catalogue"])
def api_categories(db: Session = Depends(get_db)):
    cats = db.scalars(select(Category).order_by(Category.group, Category.name)).all()
    return {
        "count": len(cats),
        "categories": [
            {"id": c.id, "name": c.name, "slug": c.slug, "group": c.group, "filters": c.filter_specs}
            for c in cats
        ],
    }


@router.get("/api/v1/stores", tags=["Retailers"])
def api_stores(verified_only: bool = False, db: Session = Depends(get_db)):
    q = select(Retailer).where(Retailer.status == "active")
    if verified_only:
        q = q.where(Retailer.verified.is_(True))
    rs = db.scalars(q.order_by(Retailer.verified.desc(), Retailer.name)).all()
    return {
        "count": len(rs),
        "stores": [
            {
                "id": r.id,
                "name": r.name,
                "slug": r.slug,
                "domain": r.domain,
                "city": r.city,
                "delivery_regions": r.delivery_regions,
                "verified": r.verified,
                "url": f"{settings.BASE_URL}/store/{r.slug}",
            }
            for r in rs
        ],
    }


@router.get("/api/v1/products", tags=["Catalogue"])
def api_search_products(
    q: str = Query("", description="Search query (supports English, Roman Urdu, model numbers, typos)"),
    category: str | None = Query(None, description="Category slug, e.g. mobile-phones"),
    brand: str | None = Query(None, description="Filter by brand name"),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    in_stock: bool = Query(False),
    sort: str = Query("relevance", description="relevance | price_asc | price_desc | delivered | newest"),
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    cat = db.scalar(select(Category).where(Category.slug == category)) if category else None
    if category and not cat:
        raise HTTPException(404, f"Category '{category}' not found")
    cards, total, fuzzy = search_products(
        db,
        q,
        category=cat,
        brand=brand,
        min_price=Decimal(str(min_price)) if min_price is not None else None,
        max_price=Decimal(str(max_price)) if max_price is not None else None,
        in_stock=in_stock,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return {
        "query": q,
        "total": total,
        "fuzzy_fallback_used": fuzzy,
        "limit": limit,
        "offset": offset,
        "products": [_serialize_card(c) for c in cards],
    }


@router.get("/api/v1/products/{slug}", tags=["Catalogue"])
def api_product_detail(
    slug: str,
    variant_id: int | None = None,
    condition: str = "new",
    sort: str = "delivered",
    db: Session = Depends(get_db),
):
    p = db.scalar(
        select(Product)
        .where(Product.slug == slug)
        .options(selectinload(Product.variants), selectinload(Product.category))
    )
    if not p:
        raise HTTPException(404, "Product not found")
    variants = sorted(p.variants, key=lambda x: (len(x.storage or ""), x.storage or "", x.colour or ""))
    counts = {x.id: len(offers_for_variant(db, x)) for x in variants}
    variant = next((x for x in variants if x.id == variant_id), None) or (
        max(variants, key=lambda x: counts[x.id]) if variants else None
    )
    all_offers = offers_for_variant(db, variant, sort=sort) if variant else []
    offers = [o for o in all_offers if o.condition == condition] or all_offers
    hist = price_history(db, variant) if variant else []
    in_stock = [o for o in offers if o.stock_status != "out_of_stock"]
    current_low = min((o.price for o in in_stock), default=None)
    dq = deal_quality(current_low, hist)
    cat_slug = p.category.slug if p.category else None
    return {
        "id": p.id,
        "title": p.title,
        "slug": p.slug,
        "brand": p.brand,
        "model_number": p.model_number,
        "category": cat_slug,
        "specs": p.specs or {},
        "image_url": p.image_url,
        "selected_variant": {
            "id": variant.id,
            "label": variant.label,
            "storage": variant.storage,
            "ram": variant.ram,
            "colour": variant.colour,
            "size": variant.size,
            "region": variant.region,
            "gtin": variant.gtin,
        }
        if variant
        else None,
        "variants": [
            {"id": v.id, "label": v.label, "offers_count": counts.get(v.id, 0)} for v in variants
        ],
        "lowest_price": float(current_low) if current_low is not None else None,
        "currency": settings.DEFAULT_CURRENCY,
        "deal_quality": {
            "label": dq["label"],
            "tone": dq["tone"],
            "truth_score": dq["score"],
            "drop_pct_vs_30d_median": dq["drop_pct"],
            "median_30d": float(dq["median"]),
            "low_30d": float(dq["low"]),
            "high_30d": float(dq["high"]),
        }
        if dq
        else None,
        "offers": [_serialize_offer(o, cat_slug, dq) for o in offers],
        "price_history_90d": [{"day": pt.day, "lowest_price": float(pt.price)} for pt in hist],
    }


@router.get("/api/v1/deals", tags=["Deals & Drops"])
def api_live_deals(category: str | None = None, limit: int = Query(20, ge=1, le=50), db: Session = Depends(get_db)):
    deals = top_price_drops(db, limit=limit * 2)
    if category:
        deals = [d for d in deals if d["card"].product.category and d["card"].product.category.slug == category]
    deals = deals[:limit]
    return {
        "count": len(deals),
        "deals": [
            {
                "product": _serialize_card(d["card"]),
                "variant_id": d["variant"].id,
                "variant_label": d["variant"].label,
                "drop_pct": d["drop_pct"],
                "savings_pkr": float(d["savings"]),
                "median_30d_pkr": float(d["deal"]["median"]),
                "low_30d_pkr": float(d["deal"]["low"]),
                "truth_score": d["deal"]["score"],
                "deal_label": d["deal"]["label"],
            }
            for d in deals
        ],
    }


@router.post("/api/v1/alerts", tags=["Alerts"])
def api_create_alert(body: AlertCreateRequest, db: Session = Depends(get_db)):
    v = db.get(Variant, body.variant_id)
    if not v:
        raise HTTPException(404, "Variant not found")
    email = body.email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(400, "Invalid email address")
    try:
        target = Decimal(str(body.target_price)).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise HTTPException(400, "Invalid target price")
    a = PriceAlert(email=email, variant_id=v.id, target_price=target, token=secrets.token_urlsafe(24))
    db.add(a)
    db.flush()
    send_email(
        db,
        email,
        f"Confirm your price alert for {v.product.title}",
        f"Please confirm you want an email when {v.product.title} ({v.label}) drops to "
        f"Rs {target:,.0f} or less:\n{settings.BASE_URL}/alerts/confirm/{a.token}\n",
    )
    db.commit()
    return {
        "status": "pending_confirmation",
        "alert_id": a.id,
        "variant_id": v.id,
        "product": v.product.title,
        "target_price": float(target),
        "message": "Confirmation email sent (double opt-in required).",
    }


# ------------------------------------------------------------------ MCP Server (JSON-RPC 2.0)

MCP_TOOLS = [
    {
        "name": "search_products",
        "description": "Search Pakistani e-commerce products by brand, model, Roman Urdu keywords, or category and return lowest verified prices.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords, e.g. 'Samsung A55', 'iPhone 15 PTA', 'fon'"},
                "category": {"type": "string", "description": "Optional category slug (e.g. 'mobile-phones', 'laptops', 'shoes')"},
                "max_price": {"type": "number", "description": "Optional maximum price in PKR"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_product_offers_and_truth_score",
        "description": "Fetch all verified store offers, delivered prices, 30-day price history, and fake-markdown audit for a product slug.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Product slug, e.g. 'samsung-galaxy-a55-5g'"},
            },
            "required": ["slug"],
        },
    },
    {
        "name": "get_verified_price_drops",
        "description": "List live verified deals where the current price is strictly below the 30-day observed median price.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Optional category slug"},
                "limit": {"type": "integer", "description": "Max items to return (default 10)"},
            },
        },
    },
]


@router.get("/api/mcp", tags=["MCP"])
def mcp_manifest():
    """Returns MCP Server capability discovery metadata."""
    return {
        "protocol": "mcp",
        "version": "2024-11-05",
        "serverInfo": {"name": "saleradar-mcp", "version": "1.0.0"},
        "tools": MCP_TOOLS,
    }


@router.post("/api/mcp", tags=["MCP"])
async def mcp_jsonrpc(request: Request, db: Session = Depends(get_db)):
    """JSON-RPC 2.0 endpoint implementing the Model Context Protocol (MCP)."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON payload")

    req_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "saleradar-mcp", "version": "1.0.0"},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": MCP_TOOLS}}

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            if name == "search_products":
                res = api_search_products(
                    q=args.get("query", ""),
                    category=args.get("category"),
                    brand=None,
                    min_price=None,
                    max_price=args.get("max_price"),
                    in_stock=False,
                    sort="relevance",
                    limit=10,
                    offset=0,
                    db=db,
                )
            elif name == "get_product_offers_and_truth_score":
                res = api_product_detail(slug=args.get("slug", ""), db=db)
            elif name == "get_verified_price_drops":
                res = api_live_deals(category=args.get("category"), limit=int(args.get("limit") or 10), db=db)
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {name}"},
                }
            import json
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(res, indent=2)}], "isError": False},
            }
        except HTTPException as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": f"Error {exc.status_code}: {exc.detail}"}], "isError": True},
            }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method '{method}' not found"},
    }
