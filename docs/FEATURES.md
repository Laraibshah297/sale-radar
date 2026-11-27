# Complete Feature Catalog (`FEATURES.md` — SaleRadar v3.0)

## 1. Market-Differentiating Pakistan Fintech & AI Features (v3.0)

| Feature | Route / Location | Competitive Advantage vs. PriceOye / Daraz / Flashi |
| :--- | :--- | :--- |
| **My Wallet / Bank Card Stacking Optimizer** | `/bank-deals` & `/p/{slug}?card=hbl` | Automatically stacks store promo vouchers (`BLESSED10`, `EIDSALE`) with **HBL, Bank Alfalah, Meezan Bank, SCB, UBL, NayaPay, and JazzCash** percentage discounts & max caps to reveal the true lowest checkout price. |
| **BNPL & Shariah Installment Planner** | `/installments` & `/p/{slug}` | Addresses `<1%` credit card penetration in Pakistan by calculating **BaadMay (3x Debit Card Split)**, **KalPay (Halal Shariah 3x)**, **QistBazaar (CNIC-only 12m)**, and **0% Bank SBS EMI (6m)** — filterable by monthly PKR budget. |
| **Official FBR DIRBS PTA Tax Calculator** | `/pta-calculator` & Non-PTA Product Pages | Calculates exact FBR USD-tier PTA taxes on **Passport vs. Local CNIC**, plus auto-displays **True PTA-Approved Landed Cost** right on `Non-PTA / JV` phone variants compared against live official PTA-approved store offers. |
| **AI Buy-Now vs. Wait Verdict** | `/p/{slug}`, `/advisor`, API | Synthesizes 30-day observed price floor, median deviation, and store stock availability into an actionable **`🟢 STRONG BUY NOW`**, **`🟡 BUY WITH BANK CARD`**, or **`🔴 WAIT / SET PRICE ALERT`** signal. |
| **Smart AI Budget Shopping Concierge** | `/advisor` | Shoppers select Category + Max PKR Budget + Use-Case Priority (`Gaming`, `Camera`, `Battery`, `University/Office`, `Overall Value`) + Bank Card to get top objective, zero-sponsor-bias recommendations. |
| **Store Trust Score & Open-Parcel Badges** | `/p/{slug}`, `/stores`, `/store/{slug}` | Displays verified **Store Trust Score (`★ 9.8/10`)**, **`📦 Open Parcel Before Payment`** guarantee, and **`💵 COD`** indicators on every offer row. |
| **1-Click WhatsApp Deal Share & Watchlist** | `/watchlist` & `/p/{slug}` | Instant WhatsApp deal summary sharing (`wa.me`) and zero-login session Watchlist with bulk WhatsApp shopping list export. |
| **54+ Real Pakistani Products with Verified Images** | Entire Catalog | Real best-selling models across Samsung, Apple, Xiaomi, Infinix, Tecno, Google Pixel, HP Victus, Lenovo ThinkPad, MacBook Air, Zero Lifestyle, Audionic, Anker, TCL, Gree, Haier, Outfitters, Khaadi, Gul Ahmed, Sapphire, Ndure, CeraVe, The Ordinary & Saeed Ghani — every item paired with verified high-res photography. |

---

## 2. Core Shopper Experience (B2C)

| Feature | Route / Location | How It Works |
| :--- | :--- | :--- |
| **Multilingual UI (English + Urdu RTL)** | `/lang/en`, `/lang/ur` | Instant session toggle switching text labels and HTML `dir="ltr"` / `dir="rtl"` with Noto Nastaliq Urdu font support. |
| **Roman Urdu & Typo-Tolerant Search** | `/search?q=...` | Understands Roman Urdu (`fon`, `mobail`, `ghari`, `handsfree`), model numbers (`SM-A556E` == `sma556e`), and typos (`samsng a55`) via `pg_trgm` / `RapidFuzz`. |
| **Live Verified Deals Radar** | `/deals` | Aggregates products currently trading strictly below their 30-day observed median price, ranked by verified `%` drop and PKR savings. |
| **Fake Markdown Detector ("Was" Audit)** | `/p/{slug}` | Compares every store's claimed `original_price` ("Was Rs X") against the 30-day observed median; flags inflated claims with an **`Inflated 'Was' Price`** warning badge. |
| **Side-by-Side Spec & Price Matrix** | `/compare?ids=1,2,3` | Compares up to 4 products side-by-side across specs, lowest live price, lowest delivered price, 30-day deal quality, and store counts. |
| **Unbiased Delivered-Price Ranking** | `/p/{slug}` | Ranks in-stock offers with known delivered price (`item + shipping`) first, then unknown-shipping offers by item price. Never biased by commissions. |
| **Server-Side SVG Price History Chart** | `/p/{slug}` | Zero-JS 90-day SVG line chart plotting daily lowest observed in-stock price across stores. |
| **Double Opt-In Price-Drop Alerts** | `POST /alerts` | Shoppers set a target PKR price; receives confirmation link first, then one-click unsubscribe alerts when price drops. |

---

## 3. Merchant SaaS Portal (`/merchant`) & Admin Operations (`/admin`)

- **Merchant Free & Pro SaaS (`/merchant`):** Self-signup, CSV / Google Sheets upload, rejected-row CSV download, 30-day outbound non-bot click attribution, **Pro** scheduled feed sync, daily click analytics, and **Competitor Price Monitoring (`/merchant/competitors`)**.
- **Admin Governance (`/admin` with Mandatory TOTP 2FA):** Pilot metrics dashboard, Human-in-the-Loop Match Review Queue (`/admin/review`), full CRUD for Products, Variants, Categories, Retailers (including Trust Score, Open-Parcel, Bank & BNPL partners), Sponsored Campaigns, Email Outbox, and Audit Log.
