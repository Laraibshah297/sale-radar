"""Sale Radar scraper.

Reads public Shopify product feeds (/products.json) for every store in
stores.json and writes:
  web/data/products.json  - current catalogue used by the website
  web/data/history.json   - price history per product (one point per day)
  web/data/stores.json    - per-store summary (product count, items on sale)

Standard library only, so it runs free on GitHub Actions with no installs.
Usage: python scraper/scrape.py [--max-pages N]
"""
import argparse
import datetime as dt
import json
import pathlib
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "data"
UA = "SaleRadarBot/0.1 (+price comparison; contact via site)"
DELAY = 1.5  # seconds between requests: be polite to stores


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def to_price(v):
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def scrape_store(store, max_pages):
    base = store["url"].rstrip("/")
    items = []
    for page in range(1, max_pages + 1):
        data = fetch_json(f"{base}/products.json?limit=250&page={page}")
        products = data.get("products", [])
        if not products:
            break
        for p in products:
            variants = p.get("variants") or []
            available = [v for v in variants if v.get("available", True)]
            pool = available or variants
            if not pool:
                continue
            cheapest = min(pool, key=lambda v: to_price(v.get("price")) or 1e12)
            price = to_price(cheapest.get("price"))
            compare = to_price(cheapest.get("compare_at_price"))
            if price is None:
                continue
            on_sale = bool(compare and compare > price)
            images = p.get("images") or []
            items.append({
                "id": f"{store['name']}:{p['id']}",
                "store": store["name"],
                "category": store.get("category", ""),
                "title": p.get("title", "").strip(),
                "type": p.get("product_type") or "",
                "vendor": p.get("vendor") or "",
                "tags": p.get("tags") if isinstance(p.get("tags"), list) else
                        [t.strip() for t in (p.get("tags") or "").split(",") if t.strip()],
                "price": price,
                "compare_at": compare if on_sale else None,
                "discount": round((1 - price / compare) * 100) if on_sale else 0,
                "in_stock": bool(available),
                "image": images[0]["src"] if images else None,
                "url": f"{base}/products/{p.get('handle')}",
            })
        time.sleep(DELAY)
    return items


def load(path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pages", type=int, default=20)
    ap.add_argument("--stores", default=str(ROOT / "scraper" / "stores.json"))
    args = ap.parse_args()

    stores = json.loads(pathlib.Path(args.stores).read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    old_products = {p["id"]: p for p in load(OUT / "products.json", {}).get("products", [])}

    all_items, summary = [], []
    for s in stores:
        try:
            items = scrape_store(s, args.max_pages)
            ok, err = True, None
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
            # keep yesterday's data for this store instead of dropping it
            items = [p for p in old_products.values() if p["store"] == s["name"]]
            ok, err = False, str(e)[:200]
        all_items.extend(items)
        summary.append({
            "name": s["name"], "url": s["url"], "category": s.get("category", ""),
            "products": len(items), "on_sale": sum(1 for i in items if i["compare_at"]),
            "ok": ok, "error": err,
        })
        print(f"{s['name']:<20} {'OK ' if ok else 'ERR'} {len(items):>5} products"
              + (f"  ({err})" if err else ""))

    now = dt.datetime.now(dt.timezone.utc)
    today = now.date().isoformat()

    history = load(OUT / "history.json", {})
    for it in all_items:
        pts = history.setdefault(it["id"], [])
        if pts and pts[-1][0] == today:
            pts[-1][1] = it["price"]
        else:
            pts.append([today, it["price"]])
        del pts[:-120]  # keep ~4 months
        prices = [p for _, p in pts]
        it["lowest"] = min(prices)
        it["drop"] = len(prices) > 1 and prices[-1] < prices[-2]

    (OUT / "products.json").write_text(json.dumps(
        {"updated": now.isoformat(timespec="minutes"), "products": all_items},
        ensure_ascii=False, separators=(",", ":")))
    (OUT / "history.json").write_text(json.dumps(history, separators=(",", ":")))
    (OUT / "stores.json").write_text(json.dumps(
        {"updated": now.isoformat(timespec="minutes"), "stores": summary}, indent=1))
    print(f"Saved {len(all_items)} products from {len(stores)} stores.")


if __name__ == "__main__":
    main()
