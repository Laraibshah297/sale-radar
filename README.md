# Sale Radar

A Pakistan-first **price comparison platform** for phones, laptops, TVs, appliances, clothing, shoes and beauty, built to the *Price Comparison Shopping Platform: Business & Product Blueprint*.

Shoppers search for an exact model and compare offers from verified local stores: item price, delivered price, warranty, stock, condition and when each price was last checked. Retailers keep their own checkout. We send them traffic.

It costs nothing to run beyond your server: no paid APIs, and everything is open source.

## What's included

**Shopper website (SEO-friendly, mobile-first, English / Urdu)**
- Search by brand, model or model number. It understands synonyms and Roman Urdu (*mobile / phone / fon*) and tolerates typos.
- Category pages with filters (brand, store, price range, storage, RAM, in stock) and sorting.
- Product pages: variant picker (storage / RAM / colour / PTA), and an offer table ranked by **lowest delivered price**, with unknown shipping clearly labelled.
- Price history chart and an honest deal label ("Lowest in 30 days", "Above the usual price") based on observed prices, not crossed-out "was" prices.
- "Last checked" on every offer. Stale prices are labelled, and very old prices are hidden.
- Price-drop email alerts with double opt-in and unsubscribe.
- "Report incorrect price" on every offer.
- Store profiles with a verification badge, contact details, delivery regions, and return / warranty links.
- Sponsored placements in a separate, labelled box that never changes the price ranking.
- About, how-prices-are-checked, privacy, terms, affiliate disclosure, merchant agreement, and contact / correction / takedown pages.
- Sitemap, robots.txt, canonical URLs and Product structured data (JSON-LD).

**Admin panel** (`/admin`, with two-step verification required for staff)
- Dashboard with the blueprint's pilot metrics: searches per visitor, search-to-product rate, outbound CTR, offer coverage, freshness, stale offers, alerts and EPC. Also top searches and searches with no results.
- Products and variants, retailers (verification evidence, permission records, feed settings, affiliate parameters, plan), and offers (manual entry, "mark checked").
- CSV import with per-row validation, rejected rows with reasons (downloadable), and a template. Re-importing the same file is safe.
- Match review queue: confidence-ranked suggestions, link / create / ignore.
- Price reports, contact messages, store applications, sponsored campaigns, affiliate conversions, users, email outbox and audit log.

**Merchant portal** (`/merchant`: the SaaS side)
- Self-signup ("List your store") with acceptance of the data agreement. Admin verifies the store before it goes live.
- Upload CSV or Google Sheet, feed health, rejected rows, stale offers, and clicks sent.
- **Pro plan:** scheduled feed URL imports, daily click analytics, and **competitor price monitoring**.

**How data gets in (zero paid APIs, with permission)**
- CSV / Excel / Google Sheets uploads (admin or merchant).
- A scheduled CSV feed URL, such as a published Google Sheet.
- Manual entry in the admin panel.
- A Shopify product feed, only when the retailer's written permission is recorded.

**Product matching** follows the blueprint's confidence hierarchy: GTIN → this retailer's earlier SKU match → brand + model number + exact variant → fuzzy suggestions that **always go to human review**. Different storage, RAM, colour, region or condition are never merged.

**Engineering:** PostgreSQL (`pg_trgm` search), DECIMAL prices with explicit currency, full price history, import-run records, allow-listed outbound redirects, bot-click filtering, CSRF protection, bcrypt passwords, TOTP MFA, login throttling, audit log, security headers, nightly backups and automatic HTTPS.

## Categories and filters

13 standard categories in 4 groups, each with its own filters (edit them in **Admin → Categories**):

| Group | Categories | Example filters |
|---|---|---|
| Electronics | Mobile Phones, Laptops, Tablets, Smartwatches, Earbuds & Headphones, Power Banks & Chargers, TVs | storage, RAM, PTA, 5G, screen size, refresh rate, processor, GPU, noise cancelling, resolution |
| Home Appliances | Air Conditioners | tonnage, inverter, energy rating |
| Fashion | Men's Clothing, Women's Clothing, Unstitched Fabric, Shoes | size (S–XXL, waist, UK shoe sizes), colour, fit, fabric, pieces, season, shoe type |
| Beauty | Beauty & Personal Care | type, skin type, volume |

Filters are multi-select (e.g. size M **or** L), combine across groups, and show counts. Sizes sort naturally (XS < S < M…, UK 6 < UK 10). New, used and refurbished offers are never ranked together.

Specs come from CSV columns named `spec_<key>` (e.g. `spec_processor`, `spec_fabric`, `spec_gender`); sizes and colours from `variant_size` / `variant_colour`.

**Real stores to approach:** `python -m app.cli seed-prospects` adds 22 Pakistani stores (fashion, shoes, electronics, beauty) as admin-only *prospects*. They are never shown or imported until you set them to active after they agree. 10 of them were confirmed to have a reachable Shopify product feed.

## Stack

Python 3.12 · FastAPI · SQLAlchemy · PostgreSQL 16 · Jinja templates (server-rendered for SEO, no JavaScript build) · Docker Compose · Caddy (free HTTPS).

The blueprint lists Next.js + FastAPI as options. A single FastAPI app with server-rendered pages is simpler to run on one server and is just as indexable by Google.

## Try it locally

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m app.cli seed-demo              # fictional demo stores and prices
.venv/bin/python -m app.cli create-admin you@example.com
.venv/bin/uvicorn app.main:app --reload             # http://localhost:8000
```

Without `DATABASE_URL` it uses a local SQLite file. Log in at `/login`, and you'll set up two-step verification with an authenticator app.

Run the tests:

```bash
.venv/bin/pytest -q
```

## Deploy on your server

1. Point your domain's DNS (an A record) at the server, and install Docker.
2. `cp .env.example .env`, then set `DOMAIN`, `BASE_URL`, `SECRET_KEY`, `POSTGRES_PASSWORD` (also inside `DATABASE_URL`) and, optionally, SMTP for alert emails.
3. Start everything:
   ```bash
   docker compose up -d --build
   docker compose exec web python -m app.cli create-admin you@yourdomain.pk
   ```
4. Open `https://yourdomain/login`.

Services: `web` (site), `worker` (feeds every 6 h, alerts hourly), `db`, `caddy` (HTTPS) and `backup` (nightly dumps in `./backups`, kept 14 days; copy them off the server).

**Before launch:** don't load the demo data on production. Have the privacy, terms and merchant agreement pages reviewed by a Pakistani legal professional, and set up email (SMTP).

## CSV columns

`retailer_name, retailer_domain, product_url, retailer_sku, product_title, brand, model_number, gtin, category, variant_colour, variant_size, storage_capacity, ram, region, condition, price, currency, shipping_cost, stock_status, warranty_type, image_url, checked_at, permission_reference`

Required: `product_url, product_title, brand, price`. Leave `shipping_cost` blank for unknown, or use `0` for free. You can download a filled-in template from the admin or merchant import page.

## Recommended launch plan (from the blueprint)

1. Interview 10–20 shoppers and 10 retailers. Get 3–5 stores to agree to share a CSV or Google Sheet.
2. Load 100–500 phone products with 2–5 offers each, then run a closed pilot.
3. Watch the dashboard. Success gates: 100+ well-matched products, 3+ active stores, 90%+ price accuracy, a measurable outbound click rate.
4. Then add affiliate programmes, sponsored campaigns, Merchant Pro subscriptions and new categories.
