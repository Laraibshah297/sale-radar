# SaleRadar v3.0 — Pakistan's Smart Price Truth, Bank Discount & BNPL Intelligence Platform

[![Tests](https://img.shields.io/badge/pytest-28%20passed-brightgreen)](#testing--verification)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](#stack--architecture)
[![FastAPI](https://img.shields.io/badge/FastAPI-REST%20%2B%20MCP%203.0-009688)](#rest-api-v1--mcp-server)
[![Vercel Live](https://img.shields.io/badge/Vercel-Live%20Production-black)](https://sale-radar-tau.vercel.app)

**SaleRadar** (`https://sale-radar-tau.vercel.app`) is a production-ready, Pakistan-first **price comparison engine, fake-markdown detector, bank-card & BNPL optimizer, FBR PTA tax calculator, and AI shopping concierge** covering **54+ real best-selling products with high-resolution product images** across **16 Pakistani retail stores** (*PriceOye, Telemart, Mega.pk, CZone, PakLap, Friends Home, Metro Online, Zero Lifestyle, Audionic, Outfitters, Khaadi, Gul Ahmed Ideas, Sapphire, Ndure, Naheed.pk, Vegas.pk*).

---

## 🏆 Why SaleRadar Beats Market Competitors (v3.0 Differentiators)

| Market Pain Point in Pakistan | Competitor Reality (PriceOye, Daraz, Flashi, SaleSiren) | SaleRadar v3.0 Unfair Advantage |
| :--- | :--- | :--- |
| **Fake "Up to 50% OFF" Sales** | Stores inflate crossed-out `"Was"` prices right before 11.11 / Blessed Friday. | **Fake Markdown Detector & 0–100 Deal Truth Score:** Audits every store's `"Was"` price against 30-day observed median history (`Inflated 'Was' Price` badge). |
| **Hidden Bank & Wallet Discounts** | Shoppers must manually check HBL, Alfalah, Meezan, or JazzCash promos per store. | **My Wallet Net Price Optimizer (`/bank-deals` & `?card=hbl`):** Stacks store promo codes + HBL, Bank Alfalah, Meezan, SCB, UBL, NayaPay & JazzCash caps automatically. |
| **`<1%` Credit Card Penetration** | Traditional EMIs exclude 70%+ debit-card & cash shoppers. | **BNPL & Halal Installment Planner (`/installments`):** Calculates **BaadMay (3x Debit Split)**, **KalPay (Shariah Halal 3x)**, **QistBazaar (CNIC-only 12m)** & **0% Bank EMI**. |
| **PTA DIRBS Tax Shock** | Cheap `"Non-PTA / JV"` phone listings hide Rs 70k–180k FBR taxes. | **Official FBR PTA Tax Calculator (`/pta-calculator` + Inline Non-PTA Alert):** Shows Passport vs CNIC tax & compares **True Landed Cost** against official PTA-approved variants. |
| **Trust Deficit & Counterfeit Fear** | Unverified marketplace sellers ship repacked or fake goods. | **Store Trust Score (`★ 9.8/10`) + `📦 Open Parcel` & `💵 COD` Badges** on every single offer row. |
| **Decision Overload & Model Confusion** | Shoppers don't know which model fits their exact PKR budget. | **AI Buy-Now vs. Wait Verdict + Smart Budget Concierge (`/advisor`)** + **1-Click WhatsApp Deal Share & Zero-Login Watchlist (`/watchlist`)**. |

---

## 🌐 Key Live Application Routes

- **`/`** — Shopper Homepage (Search in English / Roman Urdu, Fintech Quick Tools, Verified Price Drops, 13 Categories, Popular Comparisons)
- **`/deals`** — Live Verified Deals Radar (Strictly below 30-day observed median price)
- **`/bank-deals`** — Bank Card & Mobile Wallet Stacked Discount Optimizer (`HBL`, `Alfalah`, `Meezan`, `SCB`, `UBL`, `NayaPay`, `JazzCash`)
- **`/pta-calculator`** — Official FBR DIRBS Smartphone Tax Calculator (Passport vs CNIC + True Landed Cost)
- **`/installments`** — Pakistan BNPL (`BaadMay`, `KalPay Halal`, `QistBazaar CNIC`) & `0% Bank EMI` Monthly Budget Planner
- **`/advisor`** — Smart AI Budget & Use-Case Shopping Concierge (`Gaming`, `Camera`, `Battery`, `Work`, `Value`)
- **`/compare`** — Side-by-Side 4-Product Spec & Deal Truth Matrix
- **`/watchlist`** — Zero-Signup Saved Watchlist with 1-Click WhatsApp List Sharing
- **`/p/{slug}`** — Product Detail Page (Variant Picker, AI Buy/Wait Verdict, Wallet Optimizer, Non-PTA Landed Cost Box, BNPL Splits, 90-day SVG Chart, Price Alerts)
- **`/merchants` & `/merchant`** — Retailer Self-Signup & Merchant SaaS Portal (CSV upload, Pro feed sync, competitor price monitoring)
- **`/admin`** — Staff Operations Dashboard (Mandatory TOTP 2FA; Pilot KPIs, Match Review Queue, Catalog, Retailers, Audit Log)
- **`/api/docs` & `/api/v1/*`** — OpenAPI Swagger UI & REST API v1
- **`/api/mcp`** — Model Context Protocol (MCP) JSON-RPC 2.0 Server (6 AI Agent Tools)

---

## 📚 Complete Documentation Suite (`docs/`)

| Document | Description |
| :--- | :--- |
| [**`docs/PRD.md`**](./docs/PRD.md) | Product Requirements Document, Pakistani market research, personas & KPIs |
| [**`docs/DESIGN.md`**](./docs/DESIGN.md) | UI/UX design system, light/dark color tokens, bilingual English/Urdu (`RTL`) layout, and server-side SVG charts |
| [**`docs/ARCHITECTURE.md`**](./docs/ARCHITECTURE.md) | Modular monolith & dual-deployment architecture (Vercel Serverless + Docker Compose) and ADRs |
| [**`docs/DATABASE.md`**](./docs/DATABASE.md) | Complete 16-table PostgreSQL / SQLite schema, ERD diagram, `Numeric(12,2)` precision & zero-downtime migrations |
| [**`docs/APIS.md`**](./docs/APIS.md) | REST API v1 reference (`/api/v1/products`, `/api/v1/deals`, `/api/v1/bank-deals`, `/api/v1/pta-tax`, `/api/v1/installments`, `/api/v1/advisor`) |
| [**`docs/AGENTS.md`**](./docs/AGENTS.md) | Internal automation agents (Feed Sync, 4-Tier Product Matcher, Fake Markdown Auditor, AI Verdict & Alert Notifier) |
| [**`docs/MCP.md`**](./docs/MCP.md) | Model Context Protocol (MCP) JSON-RPC 2.0 Server guide (`/api/mcp`) with 6 specialized tools |
| [**`docs/AUTH.md`**](./docs/AUTH.md) | RBAC matrix (`admin`, `editor`, `merchant`), mandatory TOTP 2FA, Bcrypt, CSRF HMAC, and login throttling |
| [**`docs/PLAN.md`**](./docs/PLAN.md) | Code review summary, v2.0/v3.0 upgrades, and 90-day pilot launch roadmap |
| [**`docs/SETUP.md`**](./docs/SETUP.md) | Local development, environment variables, Vercel serverless setup, and Linux Docker Compose guide |
| [**`docs/FEATURES.md`**](./docs/FEATURES.md) | Complete B2C shopper, Pakistan Fintech, B2B Merchant Pro SaaS, Admin, and MCP feature catalog |
| [**`docs/INTEGRATIONS.md`**](./docs/INTEGRATIONS.md) | CSV/Excel feeds, published Google Sheets sync, permissioned Shopify `/products.json`, SMTP outbox & affiliate links |
| [**`docs/TESTING_AND_DEBUGGING.md`**](./docs/TESTING_AND_DEBUGGING.md) | Pytest suite breakdown (`28` tests), feed troubleshooting, visibility gate diagnostics, and MFA/SMTP debugging |
| [**`docs/UML_DIAGRAMS.md`**](./docs/UML_DIAGRAMS.md) | UML Class Diagram, Feed Ingestion Sequence, Deal Truth Audit Sequence, and Offer Lifecycle State Machine |

---

## ⚡ Quick Start (Local Development)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m app.cli seed-demo --force      # Loads 16 verified PK stores & 54 real products with images
.venv/bin/python -m app.cli create-admin you@saleradar.pk
.venv/bin/uvicorn app.main:app --reload             # http://localhost:8000
```

Run the automated test suite (`28` passing tests):
```bash
.venv/bin/python -m pytest -q
```
