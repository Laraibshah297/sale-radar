# SaleRadar v2.0 — Pakistan's Verified Price Comparison, Deal Truth Radar & MCP Platform

[![Tests](https://img.shields.io/badge/pytest-26%20passed-brightgreen)](#testing--verification)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](#stack--architecture)
[![FastAPI](https://img.shields.io/badge/FastAPI-REST%20%2B%20MCP%202.0-009688)](#rest-api-v1--mcp-server)
[![Vercel Ready](https://img.shields.io/badge/Vercel-Serverless%20Ready-black)](#deploy-on-vercel-or-docker)

**SaleRadar** is a production-ready, Pakistan-first **price comparison platform, fake-markdown detector, merchant SaaS portal, and AI agent MCP server** covering **mobile phones, laptops, tablets, smartwatches, earbuds, power banks, TVs, air conditioners, men's & women's fashion, unstitched fabric, shoes, and beauty**.

Shoppers search for an exact model (in English or **Roman Urdu** like `fon`, `mobail`, `ghari`), compare offers from verified Pakistani stores ranked by **lowest delivered price**, inspect **90-day SVG price history charts**, and spot artificial **"Was" price inflation (Fake Markdowns)** via our **0–100 Deal Truth Score**.

---

## 🚀 What's New in v2.0 (Market-Driven Production Upgrades)

1. **Fake Markdown Detector & Deal Truth Score (`0–100`):**
   - Stores in Pakistan frequently inflate crossed-out `"Was"` prices during *Blessed Friday, 11.11, and Eid Sales*.
   - SaleRadar tracks `original_price` ("Was" price) alongside `price` and audits every offer against the **30-day observed median price**. Artificial markups are automatically flagged with an **`Inflated 'Was' Price`** warning badge, while genuine discounts receive a **`Verified X% below 30d median`** badge.
2. **Live Verified Deals Radar (`/deals`):**
   - Dedicated deal-hunting feed showcasing in-stock products currently trading strictly below their 30-day observed median price, filterable by category.
3. **Promo & Voucher Code Badges (`promo_code`):**
   - Displays active store coupon codes (e.g., `🏷 Code: BLESSED10`, `EIDSALE`, `RADAR5`) directly in the product offer table and CSV feeds.
4. **Side-by-Side Spec & Deal Comparison Matrix (`/compare`):**
   - Compare up to 4 products side-by-side across technical/fashion specs, lowest live price, lowest delivered price, 30-day Deal Truth Score, and verified store counts.
5. **Public REST API v1 (`/api/v1/*`) & Interactive OpenAPI Docs (`/api/docs`):**
   - Programmatic JSON endpoints for product search, variant offer tables, deal audits, live price drops, and price alert subscriptions.
6. **Model Context Protocol (MCP) JSON-RPC 2.0 Server (`/api/mcp`):**
   - Native AI agent tools (`search_products`, `get_product_offers_and_truth_score`, `get_verified_price_drops`) enabling Claude, Cursor, Antigravity, and OpenAI agents to query live Pakistani prices and deal truth scores.
7. **Dual Deployment (Vercel Serverless + Docker Compose):**
   - Includes `vercel.json` + `api/index.py` with automatic demo seeding (`AUTO_SEED_DEMO=1`) and `postgres://` connection normalization alongside the full Docker Compose + Caddy HTTPS stack.

---

## 📚 Complete Documentation Suite (`docs/`)

All product, design, architectural, database, API, security, testing, and UML documents are available in the [`docs/`](./docs/) folder:

| Document | Description |
| :--- | :--- |
| [**`docs/PRD.md`**](./docs/PRD.md) | Product Requirements Document, Pakistani market research (PriceOye, Daraz, Flashi, SaleSiren), personas & KPIs |
| [**`docs/DESIGN.md`**](./docs/DESIGN.md) | UI/UX design system, light/dark color tokens, bilingual English/Urdu (`RTL`) layout, and server-side SVG chart design |
| [**`docs/ARCHITECTURE.md`**](./docs/ARCHITECTURE.md) | Modular monolith & dual-deployment architecture (Vercel Serverless + Docker Compose) and ADRs |
| [**`docs/DATABASE.md`**](./docs/DATABASE.md) | Complete 16-table PostgreSQL / SQLite schema, ERD diagram, `Numeric(12,2)` precision & zero-downtime migrations |
| [**`docs/APIS.md`**](./docs/APIS.md) | REST API v1 reference (`/api/v1/products`, `/api/v1/deals`, `/api/v1/stores`, `/api/v1/alerts`) & web routes |
| [**`docs/AGENTS.md`**](./docs/AGENTS.md) | Internal automation agents (Feed Sync, 4-Tier Product Matcher, Fake Markdown Auditor, Alert Notifier) |
| [**`docs/MCP.md`**](./docs/MCP.md) | Model Context Protocol (MCP) JSON-RPC 2.0 Server guide (`/api/mcp`) and tool schemas |
| [**`docs/AUTH.md`**](./docs/AUTH.md) | RBAC matrix (`admin`, `editor`, `merchant`), mandatory TOTP 2FA, Bcrypt, CSRF HMAC, and login throttling |
| [**`docs/PLAN.md`**](./docs/PLAN.md) | Code review summary, v2.0 architectural improvements, and 90-day pilot launch roadmap |
| [**`docs/SETUP.md`**](./docs/SETUP.md) | Local development, environment variables, Vercel serverless setup, and Linux Docker Compose guide |
| [**`docs/FEATURES.md`**](./docs/FEATURES.md) | Complete B2C shopper, B2B Merchant Pro SaaS, Admin operations, and Developer/MCP feature catalog |
| [**`docs/INTEGRATIONS.md`**](./docs/INTEGRATIONS.md) | CSV/Excel feeds, published Google Sheets sync, permissioned Shopify `/products.json`, SMTP outbox & affiliate links |
| [**`docs/TESTING_AND_DEBUGGING.md`**](./docs/TESTING_AND_DEBUGGING.md) | Pytest suite breakdown (`26` tests), feed troubleshooting, visibility gate diagnostics, and MFA/SMTP debugging |
| [**`docs/UML_DIAGRAMS.md`**](./docs/UML_DIAGRAMS.md) | UML Class Diagram, Feed Ingestion Sequence, Deal Truth Audit Sequence, and Offer Lifecycle State Machine |

---

## ⚡ Quick Start (Local Development)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m app.cli seed-demo              # Loads 14 demo stores, 50+ products, 900+ offers & 45d history
.venv/bin/python -m app.cli seed-prospects         # Adds 22 real Pakistani prospect stores (admin-only)
.venv/bin/python -m app.cli create-admin you@saleradar.pk
.venv/bin/uvicorn app.main:app --reload             # http://localhost:8000
```

Run the automated test suite (`26` passing tests):
```bash
.venv/bin/python -m pytest -q
```

---

## 🌐 Key Application URLs

- **`/`** — Shopper Homepage (Search, Live Verified Price Drops, 13 Categories in 4 Groups, Verified Stores)
- **`/deals`** — Live Verified Deals Radar (Filtered by 30-day observed median price drops)
- **`/compare`** — Side-by-Side Product & Spec Comparison Matrix (up to 4 products)
- **`/c/{slug}`** — Category Faceted Search (Multi-select storage, RAM, PTA, clothing/shoe sizes, specs)
- **`/p/{slug}`** — Product Page (Variant picker, condition isolation, delivered-price ranking, Fake Markdown Audit, 90-day SVG price history, double opt-in price alert)
- **`/merchants` & `/merchant`** — Retailer Self-Signup & Merchant SaaS Portal (CSV upload, Pro feed sync, competitor price monitoring)
- **`/admin`** — Staff Operations Dashboard (Requires TOTP 2FA; Pilot KPIs, Match Review Queue, Catalog, Retailers, Audit Log)
- **`/api/docs` & `/api/v1/*`** — OpenAPI Swagger UI & REST API v1
- **`/api/mcp`** — Model Context Protocol (MCP) JSON-RPC 2.0 Server for AI Agents

---

## ☁️ Deploy on Vercel or Docker

### Option A: Vercel Serverless
SaleRadar includes `vercel.json` and `api/index.py`. Deploy directly with:
```bash
vercel deploy --prod --yes
```
When `AUTO_SEED_DEMO=1` (default on Vercel), an ephemeral `/tmp/saleradar.db` is automatically initialized and seeded with demo stores and 45-day price history if no external `DATABASE_URL` / `POSTGRES_URL` is configured. For persistent production storage, attach a Neon or Supabase PostgreSQL database via `DATABASE_URL`.

### Option B: Self-Hosted Linux VPS (Docker Compose + Caddy HTTPS)
```bash
cp .env.example .env
# Set DOMAIN, BASE_URL, SECRET_KEY, POSTGRES_PASSWORD, DATABASE_URL in .env
docker compose up -d --build
docker compose exec web python -m app.cli create-admin admin@saleradar.pk
```
