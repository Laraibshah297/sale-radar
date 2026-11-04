"""Tests for the blueprint's MVP acceptance checklist (section 13)."""
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.importer import import_csv_text, import_rows
from app.models import ClickEvent, Offer, PriceHistory, Product, Variant, now
from app.services import offers_for_variant, search_products
from tests.conftest import csrf_of, login

HEADER = ("retailer_domain,product_url,retailer_sku,product_title,brand,model_number,gtin,category,"
          "storage_capacity,ram,price,shipping_cost,stock_status,warranty_type,checked_at\n")


def row(dom, sku, title, model, storage, price, ship="0", stock="in_stock", gtin=""):
    return (f"{dom},https://{dom}/p/{sku},{sku},{title},Samsung,{model},{gtin},Mobile Phones,"
            f"{storage},8GB,{price},{ship},{stock},1 Year Official,\n")


def seed(db):
    csv = HEADER + row("alpha.pk", "a1", "Samsung Galaxy A55 128GB", "SM-A556E", "128GB", "110000") \
        + row("alpha.pk", "a2", "Samsung Galaxy A55 256GB", "SM-A556E", "256GB", "125000") \
        + row("beta.pk", "b1", "Galaxy A55 5G (128 GB)", "SM A556E", "128 GB", "108500", ship="") \
        + row("beta.pk", "b2", "Galaxy A55 5G 256GB", "sm-a556e", "256GB", "123999", ship="500")
    return import_csv_text(db, csv, source="test")


def test_search_by_brand_model_and_typo(db, store):
    seed(db)
    for q in ["samsung a55", "SM-A556E", "sma556e", "galaxy a55 256gb", "mobile a55", "samsng a55"]:
        cards, total, _ = search_products(db, q)
        assert total == 1, q
        assert cards[0].product.title == "Samsung Galaxy A55"


def test_offers_from_two_stores_and_variants_not_mixed(db, store):
    run = seed(db)
    assert run.rows_ok == 4 and run.rows_rejected == 0
    assert db.scalar(select(func.count()).select_from(Product)) == 1
    variants = db.scalars(select(Variant)).all()
    assert sorted(v.storage for v in variants) == ["128GB", "256GB"]
    for v in variants:
        offers = offers_for_variant(db, v)
        assert {o.retailer.domain for o in offers} == {"alpha.pk", "beta.pk"}
        assert {o.variant.storage for o in offers} == {v.storage}


def test_ranking_by_delivered_price_unknown_shipping_last(db, store):
    seed(db)
    v = db.scalar(select(Variant).where(Variant.storage == "256GB"))
    offers = offers_for_variant(db, v, sort="delivered")
    # alpha: 125000 + 0 known; beta: 123999 + 500 = 124499 known -> beta first
    assert [o.retailer.domain for o in offers] == ["beta.pk", "alpha.pk"]
    v128 = db.scalar(select(Variant).where(Variant.storage == "128GB"))
    offers = offers_for_variant(db, v128, sort="delivered")
    # beta has unknown shipping, so known-delivered alpha ranks first even though beta is cheaper
    assert [o.retailer.domain for o in offers] == ["alpha.pk", "beta.pk"]
    assert offers_for_variant(db, v128, sort="item")[0].retailer.domain == "beta.pk"


def test_csv_rejects_rows_with_reasons(db, store):
    csv = HEADER + row("alpha.pk", "x1", "Phone", "M1", "64GB", "abc") \
        + row("alpha.pk", "x2", "Phone", "M1", "64GB", "-5") \
        + "unknown.pk,https://unknown.pk/p,s,T,B,M,,Cat,,,100,0,in_stock,,\n" \
        + "alpha.pk,https://evil.com/p,s2,T,B,M,,Cat,,,100,0,in_stock,,\n" \
        + "alpha.pk,https://alpha.pk/p,s3,T,B,M,123,Cat,,,100,0,maybe,,\n"
    run = import_csv_text(db, csv, source="test")
    assert run.rows_rejected == 5 and run.rows_ok == 0
    reasons = " ".join(r.reasons for r in run.rejects)
    for expected in ["price not a number", "negative amount", "unknown retailer", "not the retailer domain",
                     "gtin must be", "stock_status must be"]:
        assert expected in reasons


def test_every_offer_has_source_currency_timestamp_and_history(db, store):
    seed(db)
    for o in db.scalars(select(Offer)):
        assert o.product_url.startswith("https://") and o.currency == "PKR" and o.checked_at
        assert isinstance(o.price, Decimal)
    assert db.scalar(select(func.count()).select_from(PriceHistory)) == 4
    seed(db)  # same file again: idempotent, no new history rows
    assert db.scalar(select(func.count()).select_from(PriceHistory)) == 4
    csv = HEADER + row("alpha.pk", "a1", "Samsung Galaxy A55 128GB", "SM-A556E", "128GB", "99999")
    import_csv_text(db, csv, source="test")
    assert db.scalar(select(func.count()).select_from(PriceHistory)) == 5


def test_stale_offers_labelled_and_old_offers_hidden(db, store, client):
    seed(db)
    o = db.scalar(select(Offer).where(Offer.retailer_sku == "a1"))
    o.checked_at = now() - timedelta(hours=60)
    db.commit()
    p = db.scalar(select(Product))
    html = client.get(f"/p/{p.slug}?v={o.variant_id}").text
    assert "Stale price" in html
    o.checked_at = now() - timedelta(days=10)
    db.commit()
    assert o not in offers_for_variant(db, o.variant)


def test_outbound_clicks_logged_and_allow_listed(db, store, client):
    seed(db)
    o = db.scalar(select(Offer).where(Offer.retailer_sku == "a1"))
    r = client.get(f"/go/{o.id}", follow_redirects=False, headers={"user-agent": "Mozilla/5.0"})
    assert r.status_code == 302 and r.headers["location"] == o.product_url
    assert db.scalar(select(func.count()).select_from(ClickEvent)) == 1
    o.product_url = "https://evil.example/phish"
    db.commit()
    assert client.get(f"/go/{o.id}", follow_redirects=False).status_code == 400


def test_uncertain_match_goes_to_review(db, store):
    seed(db)
    run = import_rows(db, [{"retailer_domain": "beta.pk", "product_url": "https://beta.pk/p/zz",
                            "retailer_sku": "zz", "product_title": "Samsung Galaxy A55 Awesome",
                            "brand": "Samsung", "price": "100000"}], source="test", allow_create=False)
    assert run.rows_review == 1
    o = db.scalar(select(Offer).where(Offer.retailer_sku == "zz"))
    assert o.match_status == "review"
    assert all(x.id != o.id for v in db.scalars(select(Variant)) for x in offers_for_variant(db, v))


def test_gtin_match(db, store):
    import_csv_text(db, HEADER + row("alpha.pk", "g1", "Galaxy S24", "SM-S921B", "256GB", "240000",
                                     gtin="8806095300000"), source="test")
    run = import_csv_text(db, HEADER + row("beta.pk", "g2", "S24 phone", "", "", "238000",
                                           gtin="8806095300000"), source="test", allow_create=False)
    assert run.rows_ok == 1
    assert db.scalar(select(Offer).where(Offer.retailer_sku == "g2")).match_method == "gtin"


def test_admin_manual_entry_and_csv_upload(db, store, client):
    login(client, db, "admin")
    tok = csrf_of(client)
    r = client.post("/admin/products/save", data={"csrf": tok, "title": "Xiaomi Redmi 13C", "brand": "Xiaomi",
                                                  "model_number": "23100RN82L", "category_new": "Mobile Phones"})
    assert r.status_code in (200, 303)
    p = db.scalar(select(Product).where(Product.brand == "Xiaomi"))
    v = p.variants[0]
    r = client.post("/admin/offers/save", data={"csrf": tok, "retailer_id": store[0].id, "variant_id": v.id,
                                                "product_url": "https://alpha.pk/redmi-13c", "price": "32999",
                                                "shipping_cost": "0", "stock_status": "in_stock",
                                                "condition": "new", "active": "on"})
    assert db.scalar(select(Offer).where(Offer.variant_id == v.id)).price == Decimal("32999.00")
    r = client.post("/admin/imports", data={"csrf": tok, "allow_create": "1"},
                    files={"file": ("f.csv", HEADER + row("beta.pk", "q", "Redmi 13C", "23100RN82L", "", "x"))})
    assert "Rejected rows" in client.get(r.headers.get("location", "/admin/imports/1")).text or r.status_code == 200


def test_admin_requires_login_and_mfa(db, client):
    assert client.get("/admin", follow_redirects=False).status_code == 303
    from app.models import User
    from app.security import hash_password
    db.add(User(email="e@t.pk", role="editor", password_hash=hash_password("pass-12345678")))
    db.commit()
    tok = csrf_of(client)
    r = client.post("/login", data={"csrf": tok, "email": "e@t.pk", "password": "pass-12345678"},
                    follow_redirects=False)
    assert r.headers["location"] == "/login/mfa-setup"
    assert client.get("/admin", follow_redirects=False).status_code == 303  # not until MFA done


def test_csrf_required(client, store, db):
    seed(db)
    o = db.scalar(select(Offer))
    assert client.post("/report", data={"offer_id": o.id, "reason": "wrong_price"}).status_code == 400


def test_merchant_scoped_to_own_store(db, store, client):
    alpha, beta = store
    login(client, db, "merchant", retailer=alpha)
    tok = csrf_of(client)
    csv = HEADER + row("beta.pk", "m1", "Phone", "M1", "", "100") + row("alpha.pk", "m2", "Phone", "M2", "", "100")
    r = client.post("/merchant/upload", data={"csrf": tok}, files={"file": ("f.csv", csv)}, follow_redirects=False)
    assert r.status_code == 303
    assert not db.scalar(select(Offer).where(Offer.retailer_sku == "m1"))
    assert db.scalar(select(Offer).where(Offer.retailer_sku == "m2")).retailer_id == alpha.id
    assert client.get("/admin", follow_redirects=False).status_code == 403


def test_pages_published_and_indexable(client, db, store):
    seed(db)
    for path in ["/page/privacy", "/page/terms", "/page/affiliate-disclosure", "/contact", "/sitemap.xml"]:
        assert client.get(path).status_code == 200
    p = db.scalar(select(Product))
    html = client.get(f"/p/{p.slug}").text
    assert 'rel="canonical"' in html and "application/ld+json" in html
    assert f"/p/{p.slug}" in client.get("/sitemap.xml").text
    assert "Disallow: /admin" in client.get("/robots.txt").text


def test_price_alert_double_opt_in(db, store, client):
    seed(db)
    from app.jobs import check_alerts
    from app.models import EmailOutbox, PriceAlert
    v = db.scalar(select(Variant).where(Variant.storage == "128GB"))
    tok = csrf_of(client)
    client.post("/alerts", data={"csrf": tok, "variant_id": v.id, "email": "a@b.pk", "target_price": "200000",
                                 "consent": "1"})
    a = db.scalar(select(PriceAlert))
    assert not a.confirmed and check_alerts(db, log=lambda *_: None) == 0
    client.get(f"/alerts/confirm/{a.token}")
    db.expire_all()
    assert check_alerts(db, log=lambda *_: None) == 1
    assert check_alerts(db, log=lambda *_: None) == 0  # no repeat for the same price
    assert "unsubscribe" in db.scalars(select(EmailOutbox)).all()[-1].body
