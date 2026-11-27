# API Reference (`APIS.md`)

SaleRadar exposes both **Server-Rendered Web Routes** and a structured **REST API v1 (`/api/v1/*`)** + **Interactive OpenAPI Docs (`/api/docs`)** + **MCP Server (`/api/mcp`)**.

---

## 1. REST API v1 Endpoints

### 1.1 Health Check
- **`GET /api/v1/health`** (or `GET /healthz`)
- **Response (`200 OK`):**
```json
{
  "status": "ok",
  "service": "Sale Radar",
  "currency": "PKR"
}
```

### 1.2 List Categories & Filter Schemas
- **`GET /api/v1/categories`**
- **Response (`200 OK`):** Returns all 13 standard categories grouped by vertical (`Electronics`, `Home Appliances`, `Fashion`, `Beauty`) along with their active `filters` array.

### 1.3 List Active & Verified Stores
- **`GET /api/v1/stores?verified_only=true`**
- **Query Params:** `verified_only` (`bool`, default `false`).
- **Response (`200 OK`):** List of active retailers (`id`, `name`, `slug`, `domain`, `city`, `delivery_regions`, `verified`, `url`).

### 1.4 Search & Filter Products
- **`GET /api/v1/products`**
- **Query Parameters:**
  - `q` (`string`): Search query (supports brand, model number, Roman Urdu synonyms, and typo fallback).
  - `category` (`string`, optional): Category slug (e.g., `mobile-phones`, `laptops`, `shoes`).
  - `brand` (`string`, optional): Case-insensitive brand filter.
  - `min_price` / `max_price` (`number`, optional): Headline price bounds in PKR.
  - `in_stock` (`bool`, default `false`): Only return products with in-stock offers.
  - `sort` (`string`, default `relevance`): `relevance` | `price_asc` | `price_desc` | `delivered` | `newest`.
  - `limit` (`int`, `1..100`, default `24`) & `offset` (`int`, default `0`).
- **Response (`200 OK`):**
```json
{
  "query": "samsung a55",
  "total": 1,
  "fuzzy_fallback_used": false,
  "limit": 24,
  "offset": 0,
  "products": [
    {
      "id": 1,
      "title": "Samsung Galaxy A55 5G",
      "slug": "samsung-galaxy-a55-5g",
      "brand": "Samsung",
      "model_number": "SM-A556E",
      "category": "mobile-phones",
      "lowest_price": 114000.0,
      "lowest_delivered_price": 114250.0,
      "currency": "PKR",
      "stores_count": 2,
      "in_stock": true,
      "key_spec": "128GB, 256GB",
      "url": "https://saleradar.pk/p/samsung-galaxy-a55-5g"
    }
  ]
}
```

### 1.5 Product Detail, Offer Table, 30-Day Deal Truth & Fake Markdown Audit
- **`GET /api/v1/products/{slug}`**
- **Query Parameters:** `variant_id` (`int`, optional), `condition` (`new` | `refurbished` | `used`, default `new`), `sort` (`delivered` | `item` | `newest`).
- **Response (`200 OK`):**
  - Canonical product metadata and `specs` dictionary.
  - `selected_variant` and all `variants` with offer counts.
  - `deal_quality`: `label`, `tone`, `truth_score` (`0..100`), `drop_pct_vs_30d_median`, `median_30d`, `low_30d`, `high_30d`.
  - `offers`: Ranked list of offers, each containing `price`, `original_price`, `claimed_discount_pct`, `promo_code`, `shipping_cost`, `delivered_price`, `freshness`, and `deal_audit` (`fake_markdown: true/false`, `badge`).
  - `price_history_90d`: Array of `{ "day": "YYYY-MM-DD", "lowest_price": 114000.0 }`.

### 1.6 Live Verified Price Drops (Deal Radar)
- **`GET /api/v1/deals?category=mobile-phones&limit=20`**
- **Response (`200 OK`):** Products currently trading below their 30-day observed median price, sorted by percentage drop and PKR savings.

### 1.7 Create Double Opt-In Price Drop Alert
- **`POST /api/v1/alerts`**
- **Request Body (`application/json`):**
```json
{
  "variant_id": 1,
  "email": "shopper@example.pk",
  "target_price": 110000
}
```
- **Response (`200 OK`):** Returns `status: "pending_confirmation"` and sends a confirmation link to the shopper's email.

---

## 2. Web & Portal Route Map

| Route Prefix | Access Level | Key Endpoints |
| :--- | :--- | :--- |
| `/`, `/search`, `/c/{slug}`, `/p/{slug}` | Public | Homepage, search, category listings, product comparison & history |
| `/deals`, `/compare` | Public | Live Verified Deals Radar & up-to-4-product side-by-side comparison matrix |
| `/stores`, `/store/{slug}`, `/go/{offer_id}` | Public | Verified store directory, store profile, allow-listed click redirector |
| `/alerts`, `/report`, `/contact`, `/merchants` | Public (CSRF) | Price alerts, incorrect price reports, contact/takedown, store signup |
| `/login`, `/login/mfa`, `/login/mfa-setup`, `/logout` | Auth (CSRF) | Session login, TOTP authenticator verification & enrollment |
| `/merchant/*` | Role: `merchant` | CSV upload, Pro feed URL config, click analytics, competitor price monitor |
| `/admin/*` | Role: `admin`, `editor` (MFA) | Pilot KPIs, match review queue, products, variants, offers, imports, audit log |
