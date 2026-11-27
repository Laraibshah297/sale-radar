# Model Context Protocol (MCP) Server Guide (`MCP.md` — v3.0)

SaleRadar mounts a full **Model Context Protocol (MCP) JSON-RPC 2.0 Server** at `/api/mcp` (`saleradar-mcp v3.0.0`), equipping AI assistants (**Antigravity, Claude Desktop, Cursor, Windsurf, Vercel AI SDK, OpenAI Agents**) with **6 specialized Pakistani e-commerce & fintech tools**.

---

## 1. MCP Endpoints

- **`GET /api/mcp`** — Capability discovery manifest (`protocolVersion: "2024-11-05"`, `serverInfo`, and all 6 tool schemas).
- **`POST /api/mcp`** — JSON-RPC 2.0 handler supporting `initialize`, `tools/list`, and `tools/call`.

---

## 2. Available MCP Tools (6 Tools)

1. **`search_products`** (`query`, `category?`, `max_price?`)
   - Searches 54+ Pakistani products across 13 categories (supports English, model numbers, typos, and Roman Urdu keywords like `fon`, `mobail`, `ghari`), returning lowest verified prices and product image URLs.
2. **`get_product_offers_and_truth_score`** (`slug`, `card?`)
   - Returns all store offers, **AI Buy-Now vs. Wait Verdict**, **0–100 Deal Truth Score**, **Fake Markdown Audit**, **Bank Card Net Checkout Price** (`hbl`, `alfalah`, `meezan`, `scb`, `ubl`, `nayapay`, `jazzcash`), **BNPL plans**, and **90-day price history**.
3. **`get_verified_price_drops`** (`category?`, `limit?`)
   - Lists live deals strictly below their 30-day observed median price across verified Pakistani stores.
4. **`calculate_pta_tax`** (`model_name?`, `usd_value?`, `device_price_pkr?`)
   - Computes Pakistan FBR DIRBS PTA smartphone registration tax on **Passport vs. Local CNIC** and optional total landed cost in PKR.
5. **`calculate_bnpl_installments`** (`price_pkr`, `category?`)
   - Computes Pakistani **BaadMay (3x Debit Split)**, **KalPay (Halal 3x)**, **QistBazaar (CNIC 12m)**, and **0% Bank Credit Card EMI** monthly breakdowns.
6. **`recommend_best_products_for_budget`** (`budget_pkr`, `category?`, `priority?`, `card?`)
   - AI Shopping Concierge that objectively scores and recommends the best in-stock products for a shopper's PKR budget, priority (`value`, `gaming`, `camera`, `battery`, `work`), and bank card.
