# Testing, Verification & Debugging Guide (`TESTING_AND_DEBUGGING.md`)

## 1. Automated Test Suite Architecture (`tests/`)

SaleRadar ships with a comprehensive, isolated **Pytest + FastAPI TestClient** suite (`26` end-to-end and unit tests across 3 modules) that resets an isolated SQLite database before every test via the `fresh_db` autouse fixture in `tests/conftest.py`.

| Test File | Coverage Focus | Key Assertions Verified |
| :--- | :--- | :--- |
| `tests/test_acceptance.py` | Blueprint MVP Acceptance Checklist (13 tests) | Brand/model/typo search, strict variant isolation (`128GB` vs `256GB`), delivered-price ranking with unknown shipping last, CSV row rejection reasons, idempotent `PriceHistory` logging, stale (`>48h`) and hidden (`>7d`) rules, domain allow-listed `/go/{id}` click logging, fuzzy match review routing, GTIN matching, admin TOTP MFA enforcement, CSRF protection, merchant store isolation, SEO JSON-LD/sitemap, and double opt-in price alerts. |
| `tests/test_filters.py` | Multi-Category Facets & Prospects (9 tests) | Category presets, `spec_<key>` CSV ingestion, natural clothing/shoe size sorting (`XS..XXL`, `UK 5..UK 10`), `OR` within facet / `AND` across facets, strict `new` vs `refurbished` separation, URL query filtering, `prospect` store hiding & import blocking. |
| `tests/test_api_and_deals.py` | v2.0 Deal Truth, API v1 & MCP Server (4 tests) | **Fake Markdown Detector** (`Inflated 'Was' Price` when `original_price` is artificially above 30d median), `promo_code` rendering (`BLESSED10`), `/deals` Live Deals Radar, `/compare` side-by-side matrix, `/api/v1/*` REST endpoints, and `/api/mcp` JSON-RPC 2.0 protocol (`initialize`, `tools/list`, `tools/call`). |

### Running the Tests
```bash
# Run the full test suite
python -m pytest -q

# Run with verbose test names and coverage trace
python -m pytest -v
```

---

## 2. Debugging & Operational Troubleshooting

### 2.1 Diagnosing Rejected CSV Rows
- **Symptom:** An uploaded CSV reports `rows_rejected > 0` or `status = "done_with_errors"`.
- **How to Debug:**
  1. Navigate to `/admin/imports/{run_id}` (or `/merchant/imports/{run_id}`).
  2. Click **Download rejected rows CSV** (`/admin/imports/{run_id}/rejects.csv`).
  3. Inspect the `row_number` and `reasons` columns:
     - `"unknown retailer: add the retailer first (match by retailer_domain)"` -> Ensure the retailer exists in `/admin/retailers` with a matching `domain`.
     - `"product_url host X is not the retailer domain Y"` -> Outbound security prevented an off-domain link.
     - `"duplicate retailer_sku in file (also on row N)"` -> Deduplicate SKUs inside the CSV before uploading.

### 2.2 Diagnosing Offers Missing from Public Product Pages
If an imported offer does not appear on `/p/{slug}`, check the 5 visibility gates in `services.visible_offer_filter()`:
1. `Offer.active == True` (not ignored or missing from a `full_snapshot` feed).
2. `Offer.match_status == "matched"` and `Offer.variant_id IS NOT NULL` (if `match_status` is `review` or `unmatched`, approve it in `/admin/review`).
3. `Offer.checked_at >= now() - HIDE_HOURS` (offers older than 7 days / `168 hours` are automatically hidden; click **Mark checked** in `/admin/offers` or re-upload the feed).
4. `Retailer.status == "active"` (`pending`, `prospect`, and `suspended` stores are hidden from shoppers).
5. `Offer.condition` matches the active condition tab (`new` vs `refurbished`).

### 2.3 Diagnosing TOTP MFA or Email Issues Locally
- **TOTP Time Drift:** `verify_totp()` allows `valid_window=1` ($\pm 30\text{ seconds}$). If an admin loses their authenticator device, another admin can click **Reset MFA** in `/admin/users`.
- **Inspecting Emails Without SMTP:** When `SMTP_HOST` is blank in local/dev environments, all confirmation links and price-drop alerts are captured in `/admin/outbox` (`email_outbox` table) so you can click confirmation links directly during testing.
