# UI/UX & System Design Specification (`DESIGN.md`)

## 1. Design Philosophy & Principles
SaleRadar is engineered for **high-trust, low-bandwidth, mobile-first shopping in Pakistan**:
1. **Zero-Bloat Server-Rendered HTML + SVG:** No heavy client-side JavaScript bundles. Pages render in $<50\text{ ms}$ on 3G/4G connections using semantic HTML5, modern CSS Grid/Flexbox (`/static/app.css`), and server-rendered SVG price history charts (`chart_svg()`).
2. **Bilingual & Bidirectional First (English `LTR` + Urdu `RTL`):** Instant session toggle between English (`/lang/en`) and Urdu (`/lang/ur`) with automatic `dir="rtl"` layout flipping, Nastaliq typography fallback (`"Noto Nastaliq Urdu"`), and Roman Urdu search query understanding.
3. **Radical Price Transparency:** Visual hierarchy prioritizes **Delivered Price**, **30-Day Deal Truth Badge**, **Fake Markdown Warnings**, and **Last Checked Freshness** over flashy promotional banners.
4. **Automatic Dark Mode:** Built-in `prefers-color-scheme: dark` CSS custom properties for comfortable night browsing.

---

## 2. Design Tokens & Visual Language (`app/static/app.css`)

### Color Palette
| Token | Light Mode | Dark Mode | Semantic Usage |
| :--- | :--- | :--- | :--- |
| `--bg` | `#f5f7fa` | `#0f141a` | App canvas background |
| `--card` | `#ffffff` | `#171d25` | Elevated surfaces, tables, filter panels |
| `--ink` | `#14202e` | `#e8edf3` | Primary typography & prices |
| `--mute` | `#5b6878` | `#9aa7b6` | Secondary metadata, timestamps, specs |
| `--line` | `#e1e6ec` | `#28313c` | Hairline borders & dividers |
| `--brand` | `#17365d` | `#9cc3ff` | Deep navy brand identity & header accents |
| `--brand2` | `#1f6feb` | `#6aa6ff` | Interactive links, active chips, primary CTAs |
| `--good` / `--good-bg` | `#137a3f` / `#e6f5ec` | `#5fd38d` / `#14301f` | In-stock badge, lowest offer highlight, verified price drop |
| `--warn` / `--warn-bg` | `#8a5a00` / `#fff4d6` | `#ffd27a` / `#3a2d0c` | Stale price warning, inflated 'Was' price alert, pre-order |
| `--bad` / `--bad-bg` | `#b42318` / `#fdecea` | `#ff8a80` / `#3a1714` | Out of stock, above usual 30-day price, validation error |
| `--spon` / `--spon-bg` | `#6b3fa0` / `#f3ecfb` | `#cfa8ff` / `#2a1d3b` | Sponsored placement box & promo voucher badges |

### Typography & Spacing
- **Font Stack:** `system-ui, -apple-system, "Segoe UI", Roboto, "Noto Nastaliq Urdu", sans-serif`
- **Base Scale:** `15px/1.5` body, `26px–30px` H1, `20px` H2, `16px` H3, `18px–26px` extrabold (`800`) price figures.
- **Container & Grid:** Max width `1180px` with `16px` horizontal padding; responsive product card grid (`repeat(auto-fill, minmax(210px, 1fr))` on desktop, 2-column compact grid on `<640px` mobile screens).

---

## 3. Core UI Components & UX Flows

### 3.1 Product Card (`_card.html`)
- **1:1 Aspect-Ratio Image Box:** White background with lazy-loaded product image or clean SVG placeholder (`/static/placeholder.svg`).
- **Key Spec Pill:** Automatically surfaces storage range (`128GB, 256GB`) for tech or natural size range (`Sizes S–XXL`, `Sizes UK 7–UK 11`) for fashion/shoes.
- **Headline Price:** Always reflects the lowest **in-stock, new-condition** offer across verified stores.

### 3.2 Product Comparison & Deal Audit Page (`product.html`)
- **Multi-Dimensional Variant Picker:** Separate interactive rows for `Colour`, `Size`, `Storage`, `RAM`, and `PTA / Region`. Unavailable combinations are visually faded (`.na`) while linking to the closest available variant.
- **Condition Isolation Tabs:** If a product has both `New` and `Refurbished` offers, tabs separate them so refurbished prices never undercut new prices in the same table.
- **Deal Truth Summary Banner:** Shows lowest price, store count, **Deal Truth Score (`0–100`)**, 30-day typical median price, and quick actions (`Compare specs`, `Price alert`).
- **Responsive Offer Table:**
  - Highlights the `#1` lowest delivered-price in-stock row in green (`.offer-best`).
  - Displays store verification checkmark (`✔ Verified`), promo voucher chip (`🏷 Code: BLESSED10`), crossed-out store `'was'` price alongside our **Deal Audit Badge** (`Verified X% below 30d median` vs `Inflated 'Was' Price`), and inline collapsible `"Report incorrect price"` drawer.
  - On mobile (`<640px`), the table automatically transforms into stacked cards via CSS media queries.

### 3.3 Server-Side SVG Price History Chart (`chart_svg` in `app/web.py`)
- Pure `<svg viewBox="0 0 640 180">` line chart generated on the server with zero client JS dependencies.
- Plots the lowest observed in-stock price per day across all stores over the last 90 days, with accessible `aria-label` attributes.

### 3.4 Faceted Category & Search Filtering (`listing.html`)
- Collapsible `<details class="filters-mobile">` drawer on mobile, sticky `250px` sidebar on desktop.
- Multi-select checkboxes with live facet counts (`OR` within a facet group like `Size: M or L`, `AND` across facet groups like `Size + Fabric + Brand`).
- Size facets render as tactile size tiles (`.sz`) sorted naturally (`XS < S < M < L < XL < XXL`, `UK 4 < UK 5 ... < UK 11`).
