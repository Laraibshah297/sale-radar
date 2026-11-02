# Sale Radar

Search clothing and electronics from many Pakistani online stores in one place: compare prices, see live sales, track price history and watch items for price drops.

Built on free tools only: the Python standard library, a static site, GitHub Actions and GitHub Pages.

## How it works
1. `scraper/scrape.py` reads each store's public Shopify feed (`/products.json`) listed in `scraper/stores.json`.
2. It writes `web/data/products.json`, `history.json` (daily price per product) and `stores.json` (per-store status).
3. `web/` is a static site that searches all products in the browser. It has filters, sale and "lowest price" badges, a price chart, "similar at other stores" and a watchlist that shows price drops.
4. `.github/workflows/scrape.yml` runs the scraper every 6 hours, commits the data so the history grows, and deploys the site to GitHub Pages.

## Run locally
```bash
python scraper/scrape.py
cd web && python -m http.server 8000   # open http://localhost:8000
```

## Deploy for free
1. Push this folder to a new GitHub repository on branch `main`.
2. Settings → Pages → Source: **GitHub Actions**.
3. Actions → "Scrape and deploy" → Run workflow.

## Adding stores
Add `{"name": ..., "url": ..., "category": ...}` to `scraper/stores.json`. First check the store runs on Shopify by opening `https://<store>/products.json` in a browser. A store that fails is reported, and its last saved data is kept.

## Next steps
- Daraz affiliate links and non-Shopify stores (PriceOye, Telemart)
- Better product matching (model numbers, fuzzy matching)
- Posting new sales to a Telegram or WhatsApp channel
