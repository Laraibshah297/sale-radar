"""Category filters: clothing and shoe sizes, tech specs, condition, stores."""
from sqlalchemy import select

from app.filters import value_sort_key
from app.importer import import_rows
from app.models import Category, Offer, Product, Retailer
from app.services import facets, offers_for_variant, search_products


def rows(dom, items):
    out = []
    for i, it in enumerate(items):
        base = {"retailer_domain": dom, "product_url": f"https://{dom}/p/{i}-{it.get('variant_size', '')}"
                f"-{it.get('variant_colour', '')}-{it.get('condition', 'new')}", "price": "1000"}
        base.update(it)
        base.setdefault("retailer_sku", base["product_url"])
        out.append(base)
    return out


def shoe(size, colour="Black", model="SW-RUN-1", title="Stepwell Running Shoe", gender="Men", price="5000"):
    return {"product_title": title, "brand": "Stepwell", "model_number": model, "category": "Shoes",
            "variant_size": size, "variant_colour": colour, "spec_gender": gender, "spec_shoe_type": "Running",
            "price": price}


def test_category_presets_and_spec_columns(db, store):
    import_rows(db, rows("alpha.pk", [shoe("UK 8"), shoe("UK 9")]), source="t")
    cat = db.scalar(select(Category).where(Category.slug == "shoes"))
    assert cat.group == "Fashion" and "size" in cat.filter_specs and "gender" in cat.filter_specs
    p = db.scalar(select(Product))
    assert p.specs == {"gender": "Men", "shoe_type": "Running"}
    assert sorted(v.size for v in p.variants) == ["UK 8", "UK 9"]


def test_size_filter_is_multi_select_and_sizes_sort_naturally(db, store):
    import_rows(db, rows("alpha.pk", [shoe("UK 10"), shoe("UK 8"), shoe("UK 9"),
                                      shoe("UK 5", model="PC-W-2", title="Pace Heel", gender="Women")]), source="t")
    cat = db.scalar(select(Category).where(Category.slug == "shoes"))
    titles = lambda f: sorted(c.product.title for c in search_products(db, "", category=cat, spec_filters=f)[0])
    assert titles({"size": ["UK 9"]}) == ["Stepwell Running Shoe"]
    assert titles({"size": ["UK 9", "UK 5"]}) == ["Pace Heel", "Stepwell Running Shoe"]      # OR within a filter
    assert titles({"size": ["UK 9", "UK 5"], "gender": ["Women"]}) == ["Pace Heel"]           # AND across filters
    cards, _, _ = search_products(db, "", category=cat)
    sizes = dict((k, [v for v, _ in vals]) for k, _, vals in facets(cards, cat.filter_specs)["groups"])["size"]
    assert sizes == ["UK 5", "UK 8", "UK 9", "UK 10"]
    assert sorted(["XL", "S", "XXL", "M", "XS", "L"], key=lambda v: value_sort_key("size", v)) == \
        ["XS", "S", "M", "L", "XL", "XXL"]


def test_tech_spec_filters(db, store):
    lap = lambda model, cpu, ram, price: {"product_title": f"Laptop {model}", "brand": "HP", "model_number": model,
                                          "category": "Laptops", "ram": ram, "storage_capacity": "512GB",
                                          "spec_processor": cpu, "spec_screen_size": "15.6 inch", "price": price}
    import_rows(db, rows("alpha.pk", [lap("A1", "Intel Core i5", "8GB", "150000"),
                                      lap("A2", "Intel Core i7", "16GB", "210000"),
                                      lap("A3", "AMD Ryzen 5", "16GB", "160000")]), source="t")
    cat = db.scalar(select(Category).where(Category.slug == "laptops"))
    got = lambda f: sorted(c.product.model_number for c in search_products(db, "", category=cat, spec_filters=f)[0])
    assert got({"ram": ["16GB"]}) == ["A2", "A3"]
    assert got({"ram": ["16GB"], "processor": ["Intel Core i7"]}) == ["A2"]
    assert got({"processor": ["intel core i5", "amd ryzen 5"]}) == ["A1", "A3"]  # case-insensitive


def test_new_and_refurbished_never_ranked_together(db, store, client):
    phone = lambda cond, price: {"product_title": "Galaxy A55", "brand": "Samsung", "model_number": "SM-A556E",
                                 "category": "Mobile Phones", "storage_capacity": "128GB", "condition": cond,
                                 "price": price}
    import_rows(db, rows("alpha.pk", [phone("new", "110000")]) + rows("beta.pk", [phone("refurbished", "80000")]),
                source="t")
    p = db.scalar(select(Product))
    html = client.get(f"/p/{p.slug}").text
    assert "Rs 110,000" in html and "Rs 80,000" not in html and "Refurbished" in html
    html = client.get(f"/p/{p.slug}?cond=refurbished").text
    assert "Rs 80,000" in html
    assert search_products(db, "a55")[0][0].lowest == 110000  # headline price uses new


def test_listing_page_filters_via_url(db, store, client):
    import_rows(db, rows("alpha.pk", [shoe("UK 8"), shoe("UK 9", colour="Brown"),
                                      shoe("UK 5", model="PC-W-2", title="Pace Heel", gender="Women")]), source="t")
    html = client.get("/c/shoes?size=UK+5").text
    assert "Pace Heel" in html and "Stepwell Running Shoe" not in html
    html = client.get("/c/shoes?colour=Brown&colour=Black").text
    assert "Stepwell Running Shoe" in html
    assert "UK 8" in client.get("/c/shoes").text  # size buttons rendered


def test_prospect_stores_hidden_and_never_imported(db, client):
    from app.jobs import run_feed
    from app.prospects import seed_prospects
    seed_prospects(db)
    r = db.scalar(select(Retailer).where(Retailer.domain == "outfitters.com.pk"))
    assert r.status == "prospect"
    assert "Outfitters" not in client.get("/stores").text
    assert client.get(f"/store/{r.slug}").status_code == 404
    import pytest
    with pytest.raises(PermissionError):
        run_feed(db, r)


def test_stores_filtered_by_category(db, store, client):
    import_rows(db, rows("alpha.pk", [shoe("UK 8")]), source="t")
    import_rows(db, rows("beta.pk", [{"product_title": "Galaxy A15", "brand": "Samsung", "model_number": "SM-A155F",
                                      "category": "Mobile Phones", "price": "45000"}]), source="t")
    html = client.get("/stores?c=shoes").text
    assert "Alpha Mobiles" in html and "Beta Tech" not in html
