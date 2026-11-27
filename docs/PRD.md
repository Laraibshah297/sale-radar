# Product Requirements Document (PRD) — SaleRadar v2.0

## 1. Executive Summary & Product Vision
**SaleRadar** (`saleradar.pk`) is a Pakistan-first **Verified Price Comparison, Deal Truth Radar & E-Commerce Intelligence Platform** built for consumers, retail brands, and AI shopping agents.

In Pakistan's rapidly growing e-commerce market (spanning electronics hubs like Hafeez Center & Saddar online stores, and fashion/lifestyle giants like Khaadi, Sapphire, Outfitters, Gul Ahmed, Telemart, and PriceOye), shoppers suffer from three critical pain points during events like **11.11, Blessed Friday, Eid Sales, and End-of-Season Sales (EOSS)**:
1. **Fake Markdowns ("Up to 50% OFF" Inflation):** Stores frequently inflate crossed-out `"Was"` prices right before a sale event so a normal everyday price appears heavily discounted.
2. **Hidden Delivery Costs & PTA/Warranty Confusion:** Stores advertise a low headline price (`item price`) while hiding high shipping fees, Non-PTA/JV lock status, or shop-only warranties vs. official brand warranties.
3. **Variant & Condition Mixing:** Many price aggregators mix `128GB` with `256GB`, `PTA Approved` with `Non-PTA`, or `Refurbished / Open-Box` with `New` items on the same ranking table.

**Our Solution:** SaleRadar aggregates permissioned store feeds, enforces strict variant and condition isolation, ranks organically by **lowest delivered price**, audits every store's claimed `"Was"` price against **30-day observed median price history** (exposing fake markdowns with a **0–100 Deal Truth Score**), and exposes an open **REST API v1** + **Model Context Protocol (MCP)** server for AI shopping assistants.

---

## 2. Market Research & Competitive Landscape (Pakistan)

| Platform / Segment | Key Players in Pakistan | Current Market Gaps | SaleRadar v2.0 Competitive Advantage |
| :--- | :--- | :--- | :--- |
| **Tech & Mobile Marketplaces** | PriceOye, Daraz, Mega.pk, Telemart, Shophive, iShopping | Closed single-seller or commission-biased rankings; no cross-store historical truth score. | Unbiased cross-store comparison; ranks strictly by **Lowest Delivered Price**; zero commission bias. |
| **Fashion & Brand Sale Trackers** | Saleboard, SaleSiren, PakSaleFinder, Brandizo | Static banner aggregators ("Flat 30% Off at Outfitters") without SKU-level historical price verification. | Variant-level tracking (`Size S–XXL`, `UK Shoe Sizes`, `Lawn/Khaddar 3-Piece`) + **Fake Markdown Detector**. |
| **Price Trackers & Drop Alerts** | Flashi.pk, Drop N Alert, Shopping Jin | Often rely on brittle unpermissioned scraping, lack PTA/warranty transparency, and have no B2B SaaS portal. | Permission-first CSV/Google Sheets/Shopify ingestion, double opt-in alerts, and **Merchant Pro SaaS** with competitor monitoring. |
| **AI Agent Commerce** | Global MCP / ChatGPT Shopping Plugins | No Pakistani price comparison platform offers native MCP tools or Roman Urdu search normalization. | Built-in **MCP JSON-RPC 2.0 Server (`/api/mcp`)** + Roman Urdu & typo-tolerant search (`fon`, `mobail`, `ghari`). |

---

## 3. Target User Personas

1. **The Savvy Pakistani Shopper (B2C — English & Urdu):**
   - Searches for exact models (`"Samsung A55 256GB PTA"`, `"Infinix Hot 40"`, `"Men running shoes UK 9"`).
   - Wants to know the **real delivered price** to Karachi, Lahore, Islamabad, or nationwide, whether the store is **Verified**, and whether a "Blessed Friday Deal" is genuinely below the 30-day typical price.
2. **The Local E-Commerce Merchant / Brand Manager (B2B SaaS):**
   - Runs a Shopify, WooCommerce, or custom store in Pakistan.
   - Wants high-intent buyer clicks without paying exorbitant marketplace commissions (15–25%).
   - Uses **Merchant Pro** (`PKR 5,000–15,000/month`) for automated Google Sheet / Shopify feed sync, daily click attribution, and real-time **Competitor Price Monitoring**.
3. **Catalog Editors & Platform Admins (Internal Staff):**
   - Curate canonical products and variants, verify retailer business identities, review fuzzy match candidates in the **Human-in-the-Loop Match Review Queue**, and resolve shopper price reports.
4. **AI Agents & External Developers (B2D / MCP):**
   - Query `/api/v1/*` and `/api/mcp` to answer user prompts like *"Find me the cheapest PTA-approved iPhone 15 in Pakistan with verified 30-day deal quality."*

---

## 4. Core Functional Requirements (FR)

### FR-1: Multilingual & Typo-Tolerant Search Engine
- Tokenized search with **Roman Urdu & English synonym expansion** (`mobile/phone/fon/mobail`, `earbuds/handsfree/tws`, `smartwatch/ghari`).
- Automatic fallback to PostgreSQL `pg_trgm` (`word_similarity > 0.35`) or `RapidFuzz` (`partial_ratio >= 80`) when a shopper makes a spelling mistake (e.g., `"samsng a55"`).
- Model number compaction (`SM-A556E` matches `sm a556e` and `sma556e`).

### FR-2: Canonical Product, Variant & Condition Isolation
- **Strict Separation:** Different storage (`128GB` vs `256GB`), RAM (`8GB` vs `16GB`), colour, clothing/shoe size (`XS` to `4XL`, `UK 4` to `UK 11`), region (`PTA Approved` vs `Non-PTA JV`), and condition (`new`, `refurbished`, `used`, `open_box`) are never merged or ranked against each other.
- Interactive **Variant Picker** on product pages and **Multi-Select Faceted Filters** on category pages.

### FR-3: Unbiased Delivered-Price Ranking & Sponsored Separation
- Default offer ranking puts **in-stock** offers with a **known delivered price** (`item_price + shipping_cost`) first (lowest to highest), followed by offers with unknown shipping sorted by item price.
- **Sponsored placements** render in a separate, clearly badged box (`Sponsored`) and never alter organic ranking.

### FR-4: 30-Day Price History & Fake Markdown Detector ("Deal Truth Score")
- Every price or stock change appends an immutable record to `price_history`.
- **Deal Truth Score (0–100):** Compares current lowest in-stock price against the 30-day observed median and 30-day low.
- **Fake Markdown Audit:** If a store claims an `original_price` ("Was Rs 149,999") that is $>8\%$ above the 30-day observed median while selling at or above the 30-day median, SaleRadar flags it with an **`Inflated 'Was' Price`** warning badge.
- **Promo / Voucher Codes:** Displays active store coupon codes (`promo_code`, e.g., `BLESSED10`, `EIDSALE`) directly in the offer row.

### FR-5: Live Deals Radar (`/deals`) & Side-by-Side Comparison (`/compare`)
- `/deals` aggregates all in-stock products currently trading strictly below their 30-day observed median price, filterable by category.
- `/compare` allows shoppers to compare up to 4 products side-by-side across specs, lowest live price, lowest delivered price, 30-day deal quality, and verified store count.

### FR-6: Permissioned Ingestion & 4-Tier Confidence Matching
- Supports CSV uploads, scheduled Google Sheets CSV URLs, manual entry, and permissioned Shopify `/products.json` feeds.
- **Matching Hierarchy:** (1) Exact GTIN/EAN barcode -> (2) Existing Retailer SKU mapping -> (3) Brand + Model Number + Exact Variant Key -> (4) Fuzzy title similarity (always routed to the **Admin Match Review Queue**, never auto-merged).

### FR-7: Outbound Click Attribution, Bot Filtering & Security
- `/go/{offer_id}` verifies the target URL host against the retailer's allow-listed domain (`host_allowed`), filters bot user-agents, logs a `ClickEvent`, appends approved affiliate parameters, and issues a `302` redirect with `X-Robots-Tag: noindex`.

---

## 5. Key Performance Indicators (KPIs) & Pilot Success Gates

| Metric | Target Gate | Measurement Source |
| :--- | :--- | :--- |
| **Catalogue Coverage** | 100+ canonical products with $\ge 2$ active stores per product | Admin Dashboard (`m.coverage`) |
| **Price Accuracy** | $\ge 90\%$ verified accurate on weekly manual audit sample | Admin Offer Recheck & Price Reports |
| **Data Freshness** | Median offer age $< 24\text{ hours}$; stale after $48\text{ hours}$ ($36\text{h}$ for phones) | `freshness()` & Worker Scheduler |
| **Search-to-Product Rate** | $\ge 35\%$ of searches result in a product view | `SearchLog` vs `ProductView.from_search` |
| **Outbound CTR** | $\ge 15\%$ of product views generate a non-bot store redirect | `ClickEvent` (`is_bot == False`) / `ProductView` |
