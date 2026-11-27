# Complete Feature Catalog (`FEATURES.md`)

## 1. Shopper Experience (B2C)

| Feature | Route / Location | How It Works |
| :--- | :--- | :--- |
| **Multilingual UI (English + Urdu RTL)** | `/lang/en`, `/lang/ur` | Instant session toggle switching text labels and HTML `dir="ltr"` / `dir="rtl"` with Noto Nastaliq Urdu font support. |
| **Roman Urdu & Typo-Tolerant Search** | `/search?q=...` | Understands Roman Urdu (`fon`, `mobail`, `ghari`, `handsfree`), model numbers (`SM-A556E` == `sma556e`), and typos (`samsng a55`) via `pg_trgm` / `RapidFuzz`. |
| **Live Verified Deals Radar** | `/deals` | Aggregates products currently trading strictly below their 30-day observed median price, ranked by verified `%` drop and PKR savings. |
| **Fake Markdown Detector ("Was" Audit)** | `/p/{slug}` | Compares every store's claimed `original_price` ("Was Rs X") against the 30-day observed median; flags inflated claims with an **`Inflated 'Was' Price`** warning badge. |
| **Deal Truth Score (0–100)** | `/p/{slug}`, `/deals`, API | Quantitative score (`35` to `95`) evaluating current price against 30-day low and 30-day median history. |
| **Promo & Voucher Code Badges** | `/p/{slug}` | Highlights active store coupon codes (`🏷 Code: BLESSED10`, `EIDSALE`) directly inside the offer row. |
| **Side-by-Side Spec & Price Matrix** | `/compare?ids=1,2,3` | Compares up to 4 products side-by-side across specs, lowest live price, lowest delivered price, 30-day deal quality, and store counts. |
| **Unbiased Delivered-Price Ranking** | `/p/{slug}` | Ranks in-stock offers with known delivered price (`item + shipping`) first, then unknown-shipping offers by item price. Never biased by commissions. |
| **Multi-Dimensional Variant Picker** | `/p/{slug}?v={id}` | Interactive attribute rows for `Colour`, `Size`, `Storage`, `RAM`, and `PTA / Region` (`PTA Approved` vs `Non-PTA JV`). |
| **Condition Isolation Tabs** | `/p/{slug}?cond=...` | Strictly separates `New`, `Refurbished`, `Used`, and `Open Box` offers so used items never undercut new items. |
| **Server-Side SVG Price History Chart** | `/p/{slug}` | Zero-JS 90-day SVG line chart plotting daily lowest observed in-stock price across stores. |
| **Double Opt-In Price-Drop Alerts** | `POST /alerts` | Shoppers set a target PKR price; receives confirmation link first, then one-click unsubscribe alerts when price drops. |
| **Crowdsourced Price Accuracy Reports** | `POST /report` | Inline drawer on every offer to report `Wrong price`, `Out of stock`, or `Wrong product / variant`. |
| **Verified Store Profiles** | `/stores`, `/store/{slug}` | Shows verification badge (`✔ Verified`), city, delivery regions, phone, email, address, return policy, and warranty policy links. |

---

## 2. Merchant SaaS Portal (B2B — `/merchant`)

| Feature | Tier | Description |
| :--- | :--- | :--- |
| **Self-Service Store Application** | Free & Pro | Apply at `/merchants#apply` with domain validation and acceptance of the Merchant Data Agreement. |
| **CSV / Google Sheets Upload** | Free (500 offers) & Pro (Unlimited) | Upload product feeds with instant validation, downloadable template (`/merchant/template.csv`), and downloadable rejected-rows CSV. |
| **Feed Health & Stale Offer Alerts** | Free & Pro | Highlights offers older than `STALE_HOURS` (48h) and offers waiting in the match review queue. |
| **30-Day Outbound Click Attribution** | Free & Pro | Shows total non-bot shoppers sent to the store and top 10 products by outbound clicks. |
| **Scheduled Automatic Feed Sync** | **Merchant Pro** | Paste a published Google Sheet CSV URL (`https://...`); background worker imports it every 6 hours with full-snapshot sync. |
| **Daily Click Time-Series Analytics** | **Merchant Pro** | Day-by-day breakdown of outbound buyer clicks. |
| **Competitor Price Monitoring** | **Merchant Pro** (`/merchant/competitors`) | Shows how each of the merchant's matched offers compares against the lowest other verified store for the exact same variant (`+Rs X` or `-Rs Y`). |

---

## 3. Admin & Catalog Operations (`/admin`)

- **Pilot Metrics Dashboard (`/admin`):** Tracks searches per visitor, search-to-product CTR, outbound CTR (with bot clicks excluded), multi-store offer coverage `%`, median offer freshness age, active alerts, EPC, top searches, and zero-result searches.
- **Human-in-the-Loop Match Review Queue (`/admin/review`):** Displays confidence-ranked fuzzy match suggestions (`score %` and evidence) with one-click `Link to Variant`, `Create New Product`, or `Ignore`.
- **Full CRUD & Audit Trail:** Manage canonical products, variants, 13+ categories & filter schemas, retailers (including 22 pre-seeded Pakistani `prospect` stores), sponsored campaigns, affiliate conversions, email outbox (`/admin/outbox`), staff users (with MFA reset), and immutable `AuditLog` (`/admin/audit`).

---

## 4. Developer & AI Agent Interfaces

- **REST API v1 (`/api/v1/*`) & OpenAPI Swagger UI (`/api/docs`)**
- **Model Context Protocol (MCP) JSON-RPC 2.0 Server (`/api/mcp`)**
- **SEO & Structured Data:** Automatic `/sitemap.xml`, `/robots.txt`, canonical tags, and `schema.org/Product` + `AggregateOffer` JSON-LD.
