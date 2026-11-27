# API Reference (`APIS.md` — SaleRadar v3.0)

SaleRadar exposes **Server-Rendered Web Routes**, a structured **REST API v1 (`/api/v1/*`)**, **Interactive OpenAPI Docs (`/api/docs`)**, and a **6-Tool MCP Server (`/api/mcp`)**.

---

## 1. REST API v1 Endpoints

### 1.1 System & Catalogue
- **`GET /api/v1/health`** — Health check (`{"status": "ok", "version": "3.0.0", "service": "Sale Radar", "currency": "PKR"}`).
- **`GET /api/v1/categories`** — Returns all 13 categories grouped by vertical (`Electronics`, `Home Appliances`, `Fashion`, `Beauty`) and their facet keys.
- **`GET /api/v1/stores?verified_only=true`** — Returns active retailers including `trust_score`, `cod_available`, `open_parcel`, `bank_partners`, and `bnpl_partners`.
- **`GET /api/v1/products?q=...&category=...&brand=...&min_price=...&max_price=...&in_stock=true&sort=relevance`** — Typo-tolerant & Roman Urdu product search returning `image_url`, `lowest_price`, `lowest_delivered_price`, and `stores_count`.
- **`GET /api/v1/products/{slug}?variant_id=...&condition=new&card=alfalah`** — Full product comparison payload including:
  - `ai_buy_verdict` (`STRONG BUY NOW` | `GOOD TIME TO BUY` | `BUY WITH BANK CARD` | `WAIT / SET PRICE ALERT`)
  - `deal_quality` (`truth_score`, `median_30d`, `low_30d`, `drop_pct_vs_30d_median`)
  - `bnpl_and_emi_plans` (`BaadMay`, `KalPay`, `AlfaMall / Bank SBS`, `QistBazaar`)
  - `offers` (each with `net_item_price`, `total_stacked_discount`, `deal_audit.fake_markdown`, and retailer trust metadata)
  - `price_history_90d`

### 1.2 Deals, Pakistan Fintech & AI Concierge Endpoints
- **`GET /api/v1/deals?category=mobile-phones&limit=20`** — Live verified price drops below 30-day observed median.
- **`GET /api/v1/bank-deals?card=alfalah&category=mobile-phones`** — Biggest stacked discounts for `hbl`, `alfalah`, `meezan`, `scb`, `ubl`, `nayapay`, or `jazzcash`.
- **`GET /api/v1/pta-tax?model_name=Apple+iPhone+15&device_price_pkr=180000`** — Official FBR DIRBS PTA tax on Passport vs CNIC plus total landed cost in PKR.
- **`GET /api/v1/installments?price_pkr=65000&category=mobile-phones`** — Monthly BNPL & Bank EMI schedules (`BaadMay`, `KalPay`, `AlfaMall`, `QistBazaar`).
- **`GET /api/v1/advisor?budget_pkr=120000&category=mobile-phones&priority=gaming&card=hbl`** — Smart AI shopping concierge returning top scored recommendations and reasoning bullets.
- **`POST /api/v1/alerts`** — Create double opt-in price-drop alert (`{"variant_id": 1, "email": "user@example.pk", "target_price": 105000}`).

---

## 2. Web & Portal Route Map

| Route | Access | Purpose |
| :--- | :--- | :--- |
| `/`, `/search`, `/c/{slug}`, `/p/{slug}` | Public | Homepage, search, faceted category listings, product comparison & wallet optimizer |
| `/deals`, `/bank-deals` | Public | Verified 30-day price drops & Bank Card / Mobile Wallet stacked deals |
| `/pta-calculator`, `/installments` | Public | Official FBR DIRBS PTA Tax Calculator & BNPL / Monthly Budget Planner |
| `/advisor`, `/compare`, `/watchlist` | Public | AI Budget Shopping Concierge, 4-way spec comparison, and zero-login Watchlist |
| `/stores`, `/store/{slug}`, `/go/{offer_id}` | Public | Store directory with Trust Scores & Open-Parcel badges, allow-listed click redirect |
| `/merchant/*` | `merchant` | CSV upload, Pro scheduled feed sync, click analytics, competitor price monitor |
| `/admin/*` | `admin`, `editor` (MFA) | Pilot KPIs, Match Review Queue, Catalog, Retailers, Campaigns, Outbox, Audit Log |
