# Product Roadmap, Execution Plan & Code Review (`PLAN.md`)

## 1. Comprehensive Code Review of Initial Repository

During our architectural and security audit of `Laraibshah297/sale-radar`, we evaluated the codebase across 6 production dimensions:

| Dimension | Strengths Found in Base Codebase | Gaps Identified & Upgraded in v2.0 |
| :--- | :--- | :--- |
| **1. Data Integrity & Matching** | `Numeric(12, 2)` money types, timezone-aware `UTCDateTime`, append-only `PriceHistory`, 4-tier matching hierarchy (`GTIN -> SKU -> Brand+Model+Variant -> Fuzzy review`). | Added `original_price` ("Was" price) and `promo_code` columns with zero-downtime auto-migration in `app/db.py` to audit store markdown claims. |
| **2. Deal Authenticity & Market Fit** | Basic 30-day median comparison (`deal_quality`) on product pages. | Upgraded with **0–100 Deal Truth Score**, **Fake Markdown Detector (`offer_deal_audit`)**, **Live Deals Radar (`/deals`)**, and **4-Way Spec Comparison Matrix (`/compare`)**. |
| **3. API & AI Agent Readiness** | Server-rendered HTML only (`docs_url=None, openapi_url=None`); no JSON API or MCP support. | Added **REST API v1 (`/api/v1/*`)**, OpenAPI Swagger/ReDoc (`/api/docs`), and a **Model Context Protocol (MCP) JSON-RPC 2.0 Server (`/api/mcp`)**. |
| **4. Security & Governance** | Bcrypt passwords, mandatory TOTP MFA for staff, per-session HMAC CSRF tokens, login throttling, domain allow-listed `/go/{id}` redirects, bot click filtering. | Added JSON-aware exception handling for `/api/*` routes while preserving clean HTML error pages for browser routes. |
| **5. Cloud & Serverless Deployment** | Docker Compose + Caddy setup for Linux VPS only. | Added **Vercel Serverless ASGI adapter (`api/index.py`, `vercel.json`)**, `postgres://` URL normalization, and `AUTO_SEED_DEMO` for instant zero-config serverless previews. |
| **6. Documentation & Diagrams** | Single `README.md`. | Authored full 14-document engineering suite in `docs/` (`PRD`, `DESIGN`, `ARCHITECTURE`, `DATABASE`, `APIS`, `AGENTS`, `MCP`, `AUTH`, `PLAN`, `SETUP`, `FEATURES`, `INTEGRATIONS`, `TESTING_AND_DEBUGGING`, `UML_DIAGRAMS`). |

---

## 2. Phased Delivery & Launch Roadmap

### Phase 1: Foundation & Core Platform (Completed ✅)
- Canonical Product -> Variant -> Offer data model with `Numeric(12,2)` PKR precision.
- 13 standard Pakistani categories across Electronics, Home Appliances, Fashion, and Beauty.
- English + Urdu (`RTL`) bilingual UI and Roman Urdu synonym search (`fon`, `mobail`, `ghari`).
- Admin panel with TOTP MFA, Match Review Queue, and Merchant SaaS Portal (`/merchant`).

### Phase 2: Deal Truth Radar, API v1 & MCP Server (Completed in v2.0 ✅)
- **Fake Markdown Detector:** Cross-checks retailer `"Was"` prices (`original_price`) against 30-day observed median history.
- **Promo / Voucher Code Support:** Displays coupon codes (`BLESSED10`, `EIDSALE`) directly in offer comparison rows.
- **Live Deals Radar (`/deals`) & Side-by-Side Comparison (`/compare`)**.
- **REST API v1 (`/api/v1/*`) & MCP JSON-RPC 2.0 Server (`/api/mcp`)**.
- **Vercel Serverless Deployment** alongside Docker Compose + Caddy.

### Phase 3: Closed Pilot with Verified Pakistani Stores (Next 30 Days)
1. **Merchant Outreach (`python -m app.cli seed-prospects`):** Approach the 22 pre-vetted Pakistani stores (Outfitters, Breakout, Generation, Limelight, Gul Ahmed, Alkaram, Nishat Linen, Bonanza Satrangi, Zellbury, Audionic, Telemart, Shophive, Mega.pk, etc.).
2. **Written Permission Onboarding:** Onboard 5–10 pilot stores via Google Sheets CSV URLs or permissioned Shopify `/products.json` feeds.
3. **Pilot Gate Validation:** Achieve $\ge 100$ multi-store products, $\ge 90\%$ weekly audited price accuracy, and $<24\text{h}$ median offer age.

### Phase 4: Monetization & Scale (Days 60–90)
- **Merchant Pro SaaS Subscriptions:** Upgrade retailers to `PKR 5,000–15,000/month` for scheduled feed polling, daily click analytics, and real-time competitor price monitoring (`/merchant/competitors`).
- **Sponsored Placements:** Launch fixed-budget sponsored boxes on high-traffic category and product pages (strictly separated from organic price rankings).
- **WhatsApp / Web Push Price Alerts:** Expand double opt-in email alerts to WhatsApp Business API notifications.
