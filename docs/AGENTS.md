# Autonomous Agents & Background Workers (`AGENTS.md`)

SaleRadar employs four specialized internal automation agents/workers plus an external **Model Context Protocol (MCP)** interface for AI shopping assistants.

---

## 1. Internal Automation Agents

### 1.1 Feed Ingestion & Sync Agent (`app/jobs.py` -> `run_all_feeds`)
- **Schedule:** Runs every 6 hours via `python -m app.cli scheduler` (or triggered on-demand from Admin / Merchant Portal).
- **Behavior:**
  - Queries all `active` retailers configured with `feed_method IN ('feed_url', 'shopify')`.
  - Uses exponential backoff (`fetch()` with `2s -> 4s -> 8s` retries on HTTP `429`/`503`) and identifies itself transparently via `User-Agent: Sale RadarBot/1.0 (+https://saleradar.pk/about)`.
  - For Shopify stores, enforces that `retailer.permission_reference` is recorded before paginating `/products.json?limit=250`.
  - Performs a `full_snapshot=True` import, automatically deactivating any previous offer SKU that disappeared from the retailer's live feed.

### 1.2 4-Tier Product Matching & Deduplication Agent (`app/matching.py` -> `match_row`)
- **Trigger:** Invoked automatically on every imported row inside an isolated database savepoint (`db.begin_nested()`).
- **Decision Hierarchy:**
  1. **Tier 1 — Exact GTIN (`confidence = 1.0`):** Matches `Variant.gtin` (8/12/13/14-digit barcode).
  2. **Tier 2 — Historical Retailer SKU (`confidence = 0.98`):** Reuses an earlier verified match for `(retailer_id, retailer_sku)`.
  3. **Tier 3 — Deterministic Brand + Model + Variant Key (`confidence = 0.90–0.95`):** Matches normalized `brand` + compacted `model_number` (`SM-A556E` == `sma556e`) and composite `variant_key` (`storage|ram|colour|size|region`).
  4. **Tier 4 — Fuzzy Candidate Generator (`status = "review"`):** Uses `RapidFuzz.token_set_ratio` across same-brand variants. Never merges different storage sizes or conflicting model numbers. Generates up to 5 `MatchCandidate` suggestions for human staff review.

### 1.3 Fake Markdown & Deal Truth Auditor (`app/services.py` -> `deal_quality`, `offer_deal_audit`)
- **Trigger:** Real-time evaluation on product views, `/deals` radar, and `/api/v1/*` responses.
- **Logic:**
  - Reconstructs a 90-day daily lowest in-stock price curve by carrying forward each offer's `PriceHistory` observations.
  - Calculates the 30-day observed median price, 30-day low, and a **0–100 Deal Truth Score**.
  - Compares each retailer's claimed crossed-out `original_price` against the 30-day observed median. If a retailer inflates `original_price` $>8\%$ above the 30-day median while charging $\ge 99\%$ of the median price, the agent flags the offer as a **Fake Markdown (`Inflated 'Was' Price`)**.

### 1.4 Price-Drop Alert Notification Agent (`app/jobs.py` -> `check_alerts`)
- **Schedule:** Runs hourly via `python -m app.cli scheduler` or `python -m app.cli check-alerts`.
- **Logic:**
  - Scans all `active=True, confirmed=True` (double opt-in) `PriceAlert` subscriptions.
  - Compares the lowest live in-stock offer for the watched `Variant` against `alert.target_price`.
  - Sends an email via `send_email()` (and logs to `email_outbox`) only when `best.price <= alert.target_price` **and** `best.price < alert.last_notified_price` (preventing duplicate spam for the same price level).

---

## 2. External AI Shopping Agent Workflow (via MCP)

External LLM agents (Claude Desktop, Cursor, Antigravity, OpenAI Agents) connect to SaleRadar's `/api/mcp` JSON-RPC 2.0 server to perform multi-step shopping research for users:
1. Call `search_products(query="iPhone 15 PTA", category="mobile-phones")` to locate canonical product slugs.
2. Call `get_product_offers_and_truth_score(slug="apple-iphone-15")` to inspect all verified store offers, delivered prices, promo codes, and fake-markdown audit flags.
3. Call `get_verified_price_drops(category="mobile-phones")` to recommend genuine history-verified discounts.
