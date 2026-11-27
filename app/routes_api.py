"""REST API v1 & Model Context Protocol (MCP) JSON-RPC 2.0 Server (v3.0).

Exposes structured endpoints for programmatic integrations, mobile apps,
and autonomous AI agents (Claude, Cursor, Antigravity, OpenAI) to search
products, verify 30-day price history, detect fake markdowns, calculate
FBR PTA smartphone taxes, optimize Bank Card / BNPL installments, and
receive budget-aware product recommendations.
"""
import json
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
from .pakistan_market import (BANK_CARDS, ai_buy_verdict, calculate_installments,
                              estimate_pta_tax, net_price_with_card)
from .services import (bank_card_deals, card_for, deal_quality, freshness,
                       offer_deal_audit, offers_for_variant, price_history,
                       search_products, smart_budget_advisor, top_price_drops)

router = APIRouter()


class AlertCreateRequest(BaseModel):
    variant_id: int = Field(..., description="Target variant ID")
    email: str = Field(..., description="Shopper email address")
    target_price: float = Field(..., gt=0, description="Target price in PKR")


def _serialize_offer(o, category_slug=None, dq=None, card_slug: str = "") -> dict:
    aud = offer_deal_audit(o, dq)
    net = net_price_with_card(o, card_slug)
    return {
        "id": o.id,
        "retailer": {
            "id": o.retailer.id,
            "name": o.retailer.name,
            "slug": o.retailer.slug,
            "domain": o.retailer.domain,
            "verified": o.retailer.verified,
            "city": o.retailer.city,
            "trust_score": o.retailer.trust_score,
            "cod_available": o.retailer.cod_available,
            "open_parcel": o.retailer.open_parcel,
            "bank_partners": (o.retailer.bank_partners or "").split(",") if o.retailer.bank_partners else [],
            "bnpl_partners": (o.retailer.bnpl_partners or "").split(",") if o.retailer.bnpl_partners else [],
        },
        "retailer_sku": o.retailer_sku,
        "retailer_title": o.retailer_title,
        "price": float(o.price),
        "original_price": float(o.original_price) if o.original_price is not None else None,
        "claimed_discount_pct": o.claimed_discount_pct,
        "promo_code": o.promo_code,
        "net_item_price": float(net["net_item_price"]),
        "total_stacked_discount": float(net["total_discount"]),
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
        "image_url": p.image_url,
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
    return {"status": "ok", "version": "3.0.0", "service": settings.SITE_NAME, "currency": settings.DEFAULT_CURRENCY}


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
                "trust_score": r.trust_score,
                "cod_available": r.cod_available,
                "open_parcel": r.open_parcel,
                "bank_partners": (r.bank_partners or "").split(",") if r.bank_partners else [],
                "bnpl_partners": (r.bnpl_partners or "").split(",") if r.bnpl_partners else [],
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
    card: str = "",
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
    verdict = ai_buy_verdict(current_low, dq, len(in_stock))
    cat_slug = p.category.slug if p.category else None
    installments = [
        {
            "provider": pl["provider"],
            "badge": pl["badge"],
            "months": pl["months"],
            "upfront_pkr": float(pl["upfront"]),
            "monthly_pkr": float(pl["monthly"]),
            "total_pkr": float(pl["total"]),
            "shariah_compliant": pl["shariah"],
        }
        for pl in (calculate_installments(current_low, cat_slug) if current_low else [])
    ]
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
        "ai_buy_verdict": verdict,
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
        "bnpl_and_emi_plans": installments,
        "offers": [_serialize_offer(o, cat_slug, dq, card_slug=card) for o in offers],
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


@router.get("/api/v1/bank-deals", tags=["Pakistan Fintech"])
def api_bank_deals(
    card: str = Query("hbl", description="hbl | alfalah | meezan | scb | ubl | nayapay | jazzcash"),
    category: str = "",
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    c_slug = card.lower().strip()
    if c_slug not in BANK_CARDS:
        raise HTTPException(400, f"Unsupported card '{card}'. Choose one of {list(BANK_CARDS.keys())}")
    rows = bank_card_deals(db, card_slug=c_slug, category_slug=category, limit=limit)
    return {
        "card": {k: (float(v) if isinstance(v, Decimal) else v) for k, v in BANK_CARDS[c_slug].items()},
        "count": len(rows),
        "deals": [
            {
                "product": _serialize_card(r["card"]),
                "retailer": r["offer"].retailer.name,
                "list_price_pkr": float(r["offer"].price),
                "net_card_price_pkr": float(r["net_price"]),
                "total_saved_pkr": float(r["saved"]),
                "promo_code": r["offer"].promo_code,
            }
            for r in rows
        ],
    }


@router.get("/api/v1/pta-tax", tags=["Pakistan Fintech"])
def api_pta_tax(
    usd_value: float | None = Query(None, gt=0, description="Device C&F USD value"),
    model_name: str = Query("", description="Phone model name, e.g. 'Apple iPhone 15'"),
    device_price_pkr: float | None = Query(None, gt=0, description="Optional Non-PTA buying price in PKR"),
):
    res = estimate_pta_tax(usd_value=usd_value, title=model_name)
    out = {
        "matched_preset": res["matched_preset"],
        "usd_value": res["usd_value"],
        "fbr_slab": res["slab"],
        "passport_tax_pkr": float(res["passport_tax"]),
        "cnic_tax_pkr": float(res["cnic_tax"]),
        "passport_savings_pkr": float(res["passport_savings"]),
    }
    if device_price_pkr:
        out["total_landed_passport_pkr"] = round(device_price_pkr + float(res["passport_tax"]), 2)
        out["total_landed_cnic_pkr"] = round(device_price_pkr + float(res["cnic_tax"]), 2)
    return out


@router.get("/api/v1/installments", tags=["Pakistan Fintech"])
def api_installments(price_pkr: float = Query(..., gt=0), category: str = ""):
    plans = calculate_installments(price_pkr, category)
    return {
        "price_pkr": price_pkr,
        "plans": [
            {
                "provider": p["provider"],
                "badge": p["badge"],
                "type": p["type"],
                "months": p["months"],
                "upfront_pkr": float(p["upfront"]),
                "monthly_pkr": float(p["monthly"]),
                "total_pkr": float(p["total"]),
                "shariah_compliant": p["shariah"],
                "note": p["markup_note"],
            }
            for p in plans
        ],
    }


@router.get("/api/v1/advisor", tags=["AI Concierge"])
def api_smart_advisor(
    budget_pkr: float = Query(120000, gt=0),
    category: str = Query("mobile-phones"),
    priority: str = Query("value", description="value | gaming | camera | battery | work"),
    card: str = Query(""),
    limit: int = Query(5, ge=1, le=12),
    db: Session = Depends(get_db),
):
    picks = smart_budget_advisor(
        db,
        budget_pkr=Decimal(str(budget_pkr)),
        category_slug=category,
        priority=priority,
        card_slug=card,
        limit=limit,
    )
    return {
        "budget_pkr": budget_pkr,
        "category": category,
        "priority": priority,
        "count": len(picks),
        "recommendations": [
            {
                "product": _serialize_card(x["card"]),
                "variant": x["variant"].label,
                "best_store": x["offer"].retailer.name,
                "effective_price_pkr": float(x["effective_price"]),
                "advisor_score": x["score"],
                "verdict": x["verdict"]["verdict"] if x["verdict"] else None,
                "reasons": x["reasons"],
                "lowest_monthly_installment_pkr": float(x["lowest_monthly"]) if x["lowest_monthly"] else None,
            }
            for x in picks
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
        "description": "Search Pakistani e-commerce products by brand, model, Roman Urdu keywords, or category and return lowest verified prices with images.",
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
        "description": "Fetch verified store offers, AI Buy/Wait verdict, bank card net prices, BNPL installments, and fake-markdown audit for a product slug.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Product slug, e.g. 'samsung-galaxy-a55-5g'"},
                "card": {"type": "string", "description": "Optional bank card/wallet slug: hbl, alfalah, meezan, scb, ubl, nayapay, jazzcash"},
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
    {
        "name": "calculate_pta_tax",
        "description": "Calculate official Pakistan FBR DIRBS PTA smartphone registration tax on Passport vs CNIC.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model_name": {"type": "string", "description": "Smartphone model name, e.g. 'Apple iPhone 15'"},
                "usd_value": {"type": "number", "description": "Optional USD value if model is custom"},
                "device_price_pkr": {"type": "number", "description": "Optional Non-PTA phone price in PKR to compute total landed cost"},
            },
        },
    },
    {
        "name": "calculate_bnpl_installments",
        "description": "Calculate Pakistani BNPL (BaadMay 3x Debit, KalPay Halal, QistBazaar CNIC) and 0% Bank EMI plans for any PKR price.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "price_pkr": {"type": "number", "description": "Product price in PKR"},
                "category": {"type": "string", "description": "Optional category slug"},
            },
            "required": ["price_pkr"],
        },
    },
    {
        "name": "recommend_best_products_for_budget",
        "description": "Smart AI shopping concierge that recommends top verified products in Pakistan for a given PKR budget, category, priority, and bank card.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "budget_pkr": {"type": "number", "description": "Max budget in PKR, e.g. 75000"},
                "category": {"type": "string", "description": "Category slug, e.g. 'mobile-phones', 'laptops'"},
                "priority": {"type": "string", "description": "value | gaming | camera | battery | work"},
                "card": {"type": "string", "description": "Optional bank card slug (hbl, alfalah, meezan, jazzcash)"},
            },
            "required": ["budget_pkr"],
        },
    },
]


@router.get("/api/mcp", tags=["MCP"])
def mcp_manifest():
    """Returns MCP Server capability discovery metadata."""
    return {
        "protocol": "mcp",
        "version": "2024-11-05",
        "serverInfo": {"name": "saleradar-mcp", "version": "3.0.0"},
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
                "serverInfo": {"name": "saleradar-mcp", "version": "3.0.0"},
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
                res = api_product_detail(slug=args.get("slug", ""), card=args.get("card", ""), db=db)
            elif name == "get_verified_price_drops":
                res = api_live_deals(category=args.get("category"), limit=int(args.get("limit") or 10), db=db)
            elif name == "calculate_pta_tax":
                res = api_pta_tax(
                    usd_value=args.get("usd_value"),
                    model_name=args.get("model_name", ""),
                    device_price_pkr=args.get("device_price_pkr"),
                )
            elif name == "calculate_bnpl_installments":
                res = api_installments(price_pkr=float(args.get("price_pkr", 50000)), category=args.get("category", ""))
            elif name == "recommend_best_products_for_budget":
                res = api_smart_advisor(
                    budget_pkr=float(args.get("budget_pkr", 100000)),
                    category=args.get("category", "mobile-phones"),
                    priority=args.get("priority", "value"),
                    card=args.get("card", ""),
                    limit=5,
                    db=db,
                )
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {name}"},
                }
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
