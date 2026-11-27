# External Integrations & Data Feeds (`INTEGRATIONS.md`)

SaleRadar is designed to operate with **zero paid third-party API dependencies**, integrating cleanly with standard e-commerce feeds, spreadsheets, SMTP relays, affiliate networks, and AI agent hosts.

---

## 1. Retailer Feed Integrations (`app/importer.py`, `app/jobs.py`)

### 1.1 CSV & Excel Exports (`csv_upload`)
- Accepts UTF-8 (with or without BOM) and Windows CP1252 CSV files exported from Microsoft Excel, Google Sheets, WooCommerce, or custom ERPs.
- Auto-detects delimiters (`,`, `;`, `\t`) via `csv.Sniffer`.
- Supports 25 standard columns (`retailer_name`, `retailer_domain`, `product_url`, `retailer_sku`, `product_title`, `brand`, `model_number`, `gtin`, `category`, `variant_colour`, `variant_size`, `storage_capacity`, `ram`, `region`, `condition`, `price`, `original_price`, `promo_code`, `currency`, `shipping_cost`, `stock_status`, `warranty_type`, `image_url`, `checked_at`, `permission_reference`) plus arbitrary `spec_<key>` columns (`spec_processor`, `spec_fabric`, `spec_tonnage`, etc.).

### 1.2 Published Google Sheets Live Sync (`feed_url`)
- Merchants on the **Pro plan** (or Admins) can publish a Google Sheet to the web (`File -> Share -> Publish to web -> CSV`) and save the `https://docs.google.com/spreadsheets/.../pub?output=csv` URL on the retailer record.
- `run_feed()` polls the URL every 6 hours with exponential backoff and `full_snapshot=True` (automatically deactivating discontinued SKUs).

### 1.3 Permissioned Shopify Store Feeds (`shopify`)
- Many top Pakistani fashion, footwear, and electronics brands run on Shopify (`outfitters.com.pk`, `breakout.com.pk`, `generation.com.pk`, `limelight.pk`, `gulahmedshop.com`, `alkaramstudio.com`, `nishatlinen.com`, `bonanzasatrangi.com`, `zellbury.com`, `audionic.co`).
- When a store grants written permission (`retailer.permission_reference` is populated and `retailer.status == "active"`), `shopify_rows()` paginates `https://{domain}/products.json?limit=250&page={n}` (with polite `1.5s` inter-page pacing), maps Shopify options (`Storage`, `Size`, `Shoe Size`, `Color`/`Colour`), barcode (`gtin`), SKU, vendor (`brand`), and availability into canonical SaleRadar offers.

---

## 2. Transactional Email & Outbox Integration (`app/mailer.py`)

- **Database-First Outbox (`email_outbox` table):** Every outgoing email (double opt-in price alert confirmation, price-drop alert notification) is first persisted to `email_outbox` and viewable in `/admin/outbox`.
- **STARTTLS SMTP Delivery:** When `SMTP_HOST` is configured (compatible with **Brevo, Mailjet, Zoho Mail, Amazon SES, Resend, or Postmark**), `send_email()` delivers via STARTTLS on `SMTP_PORT` (default `587`). If an SMTP error occurs, the exception is captured in `EmailOutbox.error` without crashing the user request.

---

## 3. Affiliate & Outbound Attribution Integration (`app/routes_public.py`)

- **Domain Allow-Listed Redirector (`/go/{offer_id}`):**
  - Verifies `host_allowed(offer.product_url, retailer.domain)`.
  - Filters automated crawlers (`looks_like_bot(User-Agent)`).
  - Appends `retailer.affiliate_param` (e.g., `ref=saleradar` or `utm_source=saleradar&utm_medium=cpc`) when `retailer.affiliate_status == "approved"`.
- **Conversion Reconciliation (`/admin/campaigns`):** Admins can log validated affiliate conversions (`AffiliateConversion`) linked to `click_id` to calculate **Earnings Per Click (EPC)** on the dashboard.

---

## 4. AI Agent & MCP Client Integration (`app/routes_api.py`)

- Any MCP-compatible client can connect to `https://<your-deployment-domain>/api/mcp` via HTTP JSON-RPC 2.0 to invoke `search_products`, `get_product_offers_and_truth_score`, and `get_verified_price_drops`.
