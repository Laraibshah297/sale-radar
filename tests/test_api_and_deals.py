"""Tests for SaleRadar v2.0 & v3.0 market-differentiating features:
- Real Pakistani catalog with verified product images
- Fake Markdown Detector ('Was' price audit) & Promo codes
- Bank Card & Digital Wallet Stacking Optimizer (/bank-deals & net_price_with_card)
- Official FBR DIRBS PTA Tax Calculator (/pta-calculator & Non-PTA landed cost alert)
- BNPL & Easy Installments Planner (/installments — BaadMay, KalPay Halal, QistBazaar, Bank EMI)
- AI Buy-Now vs Wait Verdict & Smart Budget Concierge (/advisor)
- Session Watchlist (/watchlist) & WhatsApp Share
- REST API v1 & 6-tool MCP JSON-RPC 2.0 Server
"""
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from app.demo import seed as seed_real_catalog
from app.importer import import_rows
from app.models import Offer, PriceHistory, Product, Variant, now
from app.pakistan_market import calculate_installments, estimate_pta_tax, net_price_with_card
from app.services import deal_quality, offer_deal_audit, price_history
from tests.conftest import csrf_of


def _seed_with_history(db, store):
    alpha, beta = store
    alpha.bank_partners = "hbl,alfalah,jazzcash"
    alpha.open_parcel = True
    alpha.trust_score = 9.7
    db.commit()
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
                "image_url": "https://images.unsplash.com/photo-1610945415295-d9bbf067e59c?auto=format&fit=crop&w=600&q=80",
                "storage_capacity": "256GB",
                "ram": "8GB",
                "region": "PTA Approved",
                "price": "120000",
                "original_price": "149999",
                "promo_code": "BLESSED10",
                "shipping_cost": "0",
                "spec_processor": "Exynos 1480",
                "spec_battery": "5000 mAh",
                "spec_refresh_rate": "120Hz",
            },
            {
                "retailer_domain": "beta.pk",
                "product_url": "https://beta.pk/p/a55",
                "retailer_sku": "a55-2",
                "product_title": "Samsung Galaxy A55 5G 256GB",
                "brand": "Samsung",
                "model_number": "SM-A556E",
                "category": "Mobile Phones",
                "image_url": "https://images.unsplash.com/photo-1610945415295-d9bbf067e59c?auto=format&fit=crop&w=600&q=80",
                "storage_capacity": "256GB",
                "ram": "8GB",
                "region": "PTA Approved",
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


def test_real_pakistani_catalog_has_real_products_and_images(db):
    msg = seed_real_catalog(db)
    assert "real products with images" in msg
    products = db.scalars(select(Product)).all()
    assert len(products) >= 50
    for p in products:
        assert p.image_url and p.image_url.startswith("https://images.unsplash.com/"), f"Missing real image on {p.title}"


def test_fake_markdown_detection_and_promo_code(db, store, client):
    o1 = _seed_with_history(db, store)
    v = db.scalar(select(Variant))
    hist = price_history(db, v)
    dq = deal_quality(Decimal("114000"), hist)
    assert dq is not None and dq["score"] >= 85
    audit_alpha = offer_deal_audit(o1, dq)
    assert audit_alpha["fake_markdown"] is True
    assert "Inflated 'Was' Price" in audit_alpha["badge"]

    p = db.scalar(select(Product))
    html = client.get(f"/p/{p.slug}").text
    assert "BLESSED10" in html
    assert "AI Buying Verdict" in html
    assert "Open Parcel" in html
    assert "Inflated &#39;Was&#39; Price" in html or "Inflated 'Was' Price" in html


def test_bank_card_optimizer_pta_bnpl_advisor_and_watchlist(db, store, client):
    o1 = _seed_with_history(db, store)
    # 1. Bank card stacking: 120,000 - 4,000 (BLESSED10 cap) = 116,000; Alfalah 15% capped at 7,500 -> 108,500!
    calc = net_price_with_card(o1, "alfalah")
    assert calc["card_applied"] is True
    assert calc["net_item_price"] == Decimal("108500")

    p = db.scalar(select(Product))
    r_card_p = client.get(f"/p/{p.slug}?card=alfalah")
    assert r_card_p.status_code == 200
    assert "Rs 108,500" in r_card_p.text

    r_bank = client.get("/bank-deals?card=alfalah")
    assert r_bank.status_code == 200
    assert "Samsung Galaxy A55" in r_bank.text

    # 2. Official FBR PTA Tax calculator
    pta = estimate_pta_tax(title="Apple iPhone 15")
    assert pta["passport_tax"] < pta["cnic_tax"]
    r_pta = client.get("/pta-calculator?preset=iphone-15&device_price=180000")
    assert r_pta.status_code == 200
    assert "True PTA-Approved Landed Cost" in r_pta.text

    # 3. BNPL & Installments planner
    plans = calculate_installments(Decimal("60000"), "mobile-phones")
    providers = {pl["provider"] for pl in plans}
    assert "BaadMay" in providers and "KalPay" in providers and "QistBazaar" in providers
    r_inst = client.get("/installments?monthly=45000")
    assert r_inst.status_code == 200
    assert "Samsung Galaxy A55" in r_inst.text

    # 4. Smart AI Budget Concierge
    r_adv = client.get("/advisor?budget=130000&cat=mobile-phones&priority=gaming&card=alfalah")
    assert r_adv.status_code == 200
    assert "Samsung Galaxy A55" in r_adv.text

    # 5. Session Watchlist toggle
    tok = csrf_of(client)
    r_wl = client.post("/watchlist/toggle", data={"csrf": tok, "product_id": p.id, "next_url": "/watchlist"},
                       follow_redirects=True)
    assert r_wl.status_code == 200
    assert "Samsung Galaxy A55" in r_wl.text


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


def test_rest_api_v1_and_fintech_endpoints(db, store, client):
    _seed_with_history(db, store)
    p = db.scalar(select(Product))

    assert client.get("/api/v1/health").json()["status"] == "ok"
    assert client.get("/api/v1/categories").json()["count"] >= 1
    assert client.get("/api/v1/stores?verified_only=true").json()["count"] == 1

    search_res = client.get("/api/v1/products?q=a55").json()
    assert search_res["total"] == 1
    assert search_res["products"][0]["image_url"].startswith("https://")

    detail = client.get(f"/api/v1/products/{p.slug}?card=alfalah").json()
    assert detail["deal_quality"]["truth_score"] >= 85
    assert detail["ai_buy_verdict"] is not None
    assert len(detail["bnpl_and_emi_plans"]) >= 2

    bank_api = client.get("/api/v1/bank-deals?card=alfalah").json()
    assert bank_api["count"] >= 1

    pta_api = client.get("/api/v1/pta-tax?model_name=Apple+iPhone+15&device_price_pkr=180000").json()
    assert pta_api["total_landed_passport_pkr"] > 180000

    inst_api = client.get("/api/v1/installments?price_pkr=50000&category=mobile-phones").json()
    assert len(inst_api["plans"]) >= 3

    adv_api = client.get("/api/v1/advisor?budget_pkr=130000&category=mobile-phones&priority=gaming").json()
    assert adv_api["count"] >= 1


def test_mcp_jsonrpc_server_all_6_tools(db, store, client):
    _seed_with_history(db, store)
    p = db.scalar(select(Product))

    manifest = client.get("/api/mcp").json()
    assert manifest["protocol"] == "mcp"
    assert len(manifest["tools"]) == 6

    call_pta = client.post(
        "/api/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {"name": "calculate_pta_tax", "arguments": {"model_name": "Apple iPhone 15"}},
        },
    ).json()
    assert call_pta["result"]["isError"] is False
    assert "passport_tax_pkr" in call_pta["result"]["content"][0]["text"]

    call_adv = client.post(
        "/api/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "recommend_best_products_for_budget",
                "arguments": {"budget_pkr": 130000, "category": "mobile-phones", "priority": "gaming"},
            },
        },
    ).json()
    assert call_adv["result"]["isError"] is False
    assert p.slug in call_adv["result"]["content"][0]["text"]
