"""Tests for new market-driven features: REST API v1, MCP JSON-RPC 2.0 Server,
Fake Markdown Detector ('Was' price audit), Promo codes, Live Deals, and Compare Matrix."""
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from app.importer import import_rows
from app.models import Offer, PriceHistory, Product, Variant, now
from app.services import deal_quality, offer_deal_audit, price_history


def _seed_with_history(db, store):
    alpha, beta = store
    import_rows(
        db,
        [
            {
                "retailer_domain": "alpha.pk",
                "product_url": "https://alpha.pk/p/a55",
                "retailer_sku": "a55-1",
                "product_title": "Samsung Galaxy A55 5G 256GB",
                "brand": "Samsung",
                "model_number": "SM-A556E",
                "category": "Mobile Phones",
                "storage_capacity": "256GB",
                "ram": "8GB",
                "price": "120000",
                "original_price": "149999",
                "promo_code": "BLESSED10",
                "shipping_cost": "0",
                "spec_processor": "Exynos 1480",
                "spec_battery": "5000 mAh",
            },
            {
                "retailer_domain": "beta.pk",
                "product_url": "https://beta.pk/p/a55",
                "retailer_sku": "a55-2",
                "product_title": "Samsung Galaxy A55 5G 256GB",
                "brand": "Samsung",
                "model_number": "SM-A556E",
                "category": "Mobile Phones",
                "storage_capacity": "256GB",
                "ram": "8GB",
                "price": "114000",
                "original_price": "125000",
                "shipping_cost": "250",
            },
        ],
        source="test",
    )
    o1 = db.scalar(select(Offer).where(Offer.retailer_sku == "a55-1"))
    for d in range(25, 1, -2):
        db.add(
            PriceHistory(
                offer_id=o1.id,
                price=Decimal("120000"),
                shipping_cost=Decimal("0"),
                stock_status="in_stock",
                captured_at=now() - timedelta(days=d),
            )
        )
    db.commit()
    return o1


def test_fake_markdown_detection_and_promo_code(db, store, client):
    o1 = _seed_with_history(db, store)
    v = db.scalar(select(Variant))
    hist = price_history(db, v)
    dq = deal_quality(Decimal("114000"), hist)
    assert dq is not None and dq["score"] >= 85
    # alpha.pk claims 'was' 149,999 and current 120,000, while 30-day median is 120,000 -> fake markdown!
    audit_alpha = offer_deal_audit(o1, dq)
    assert audit_alpha["fake_markdown"] is True
    assert "Inflated 'Was' Price" in audit_alpha["badge"]

    p = db.scalar(select(Product))
    html = client.get(f"/p/{p.slug}").text
    assert "BLESSED10" in html
    assert "Inflated &#39;Was&#39; Price" in html or "Inflated 'Was' Price" in html


def test_deals_and_compare_pages(db, store, client):
    _seed_with_history(db, store)
    p = db.scalar(select(Product))
    r_deals = client.get("/deals")
    assert r_deals.status_code == 200
    assert "Samsung Galaxy A55" in r_deals.text

    r_cmp = client.get(f"/compare?ids={p.id}")
    assert r_cmp.status_code == 200
    assert "Exynos 1480" in r_cmp.text
    assert "Rs 114,000" in r_cmp.text


def test_rest_api_v1_endpoints(db, store, client):
    _seed_with_history(db, store)
    p = db.scalar(select(Product))

    assert client.get("/api/v1/health").json()["status"] == "ok"
    cats = client.get("/api/v1/categories").json()
    assert cats["count"] >= 1

    stores_res = client.get("/api/v1/stores?verified_only=true").json()
    assert stores_res["count"] == 1
    assert stores_res["stores"][0]["domain"] == "alpha.pk"

    search_res = client.get("/api/v1/products?q=a55").json()
    assert search_res["total"] == 1
    assert search_res["products"][0]["lowest_price"] == 114000.0

    detail = client.get(f"/api/v1/products/{p.slug}").json()
    assert detail["deal_quality"]["truth_score"] >= 85
    assert len(detail["offers"]) == 2

    deals_api = client.get("/api/v1/deals").json()
    assert deals_api["count"] >= 1

    v = db.scalar(select(Variant))
    alert_res = client.post(
        "/api/v1/alerts",
        json={"variant_id": v.id, "email": "shopper@test.pk", "target_price": 110000},
    )
    assert alert_res.status_code == 200
    assert alert_res.json()["status"] == "pending_confirmation"


def test_mcp_jsonrpc_server(db, store, client):
    _seed_with_history(db, store)
    p = db.scalar(select(Product))

    manifest = client.get("/api/mcp").json()
    assert manifest["protocol"] == "mcp"
    assert len(manifest["tools"]) == 3

    init_res = client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"}).json()
    assert init_res["result"]["serverInfo"]["name"] == "saleradar-mcp"

    list_res = client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}).json()
    assert len(list_res["result"]["tools"]) == 3

    call_res = client.post(
        "/api/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "get_product_offers_and_truth_score", "arguments": {"slug": p.slug}},
        },
    ).json()
    assert call_res["result"]["isError"] is False
    assert "114000" in call_res["result"]["content"][0]["text"]
