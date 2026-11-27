# UML Diagrams (`UML_DIAGRAMS.md`)

This document provides complete **Unified Modeling Language (UML)** diagrams for SaleRadar v2.0 across five views: **Class Diagram**, **Ingestion & 4-Tier Matching Sequence Diagram**, **Fake Markdown & Deal Truth Sequence Diagram**, **Offer Lifecycle State Machine**, and **Use-Case / Component Diagram**.

---

## 1. UML Domain Class Diagram

```mermaid
classDiagram
    class Category {
        +int id
        +str name
        +str slug
        +str group
        +list filter_specs
    }

    class Product {
        +int id
        +str title
        +str slug
        +str brand
        +str model_number
        +dict specs
        +str search_text
        +datetime created_at
    }

    class Variant {
        +int id
        +int product_id
        +str storage
        +str ram
        +str colour
        +str size
        +str region
        +str gtin
        +str variant_key
        +label() str
    }

    class Retailer {
        +int id
        +str name
        +str slug
        +str domain
        +str status
        +bool verified
        +str feed_method
        +str feed_url
        +str permission_reference
        +str plan
    }

    class Offer {
        +int id
        +int retailer_id
        +int variant_id
        +str retailer_sku
        +str retailer_title
        +str product_url
        +Decimal price
        +Decimal original_price
        +str promo_code
        +Decimal shipping_cost
        +str stock_status
        +str condition
        +str match_status
        +str match_method
        +float match_confidence
        +datetime checked_at
        +delivered_price() Decimal
        +claimed_discount_pct() int
    }

    class PriceHistory {
        +int id
        +int offer_id
        +Decimal price
        +Decimal shipping_cost
        +str stock_status
        +datetime captured_at
    }

    class MatchCandidate {
        +int id
        +int offer_id
        +int variant_id
        +float score
        +str evidence
        +str status
    }

    class PriceAlert {
        +int id
        +str email
        +int variant_id
        +Decimal target_price
        +str token
        +bool confirmed
        +bool active
        +Decimal last_notified_price
    }

    Category "1" --> "*" Product : classifies
    Product "1" *-- "1..*" Variant : contains
    Variant "1" --> "*" Offer : has_offers
    Retailer "1" --> "*" Offer : publishes
    Offer "1" *-- "1..*" PriceHistory : logs_history
    Offer "1" --> "*" MatchCandidate : generates
    Variant "1" --> "*" MatchCandidate : candidate_target
    Variant "1" --> "*" PriceAlert : watched_by
```

---

## 2. UML Sequence Diagram — Feed Ingestion & 4-Tier Matching Engine

```mermaid
sequenceDiagram
    autonumber
    actor Actor as Merchant / Admin / Scheduler
    participant Importer as app/importer.py
    participant Validator as validate()
    participant Matcher as app/matching.py
    participant DB as PostgreSQL / SQLite

    Actor->>Importer: Upload CSV or Trigger Feed Sync
    Importer->>DB: Create ImportRun (status="running")
    loop For each row in CSV/Feed
        Importer->>Validator: clean_row(raw) & validate(row, retailer)
        alt Validation Fails (Bad URL, Negative Price, Unknown Domain)
            Validator-->>Importer: Return error reasons
            Importer->>DB: Insert ImportReject (row_number, reasons)
        else Validation Succeeds
            Validator-->>Importer: Clean normalized row
            Importer->>Matcher: match_row(db, row, retailer_id, allow_create)
            alt Tier 1: Exact GTIN Barcode Match
                Matcher-->>Importer: MatchResult(status="matched", method="gtin", conf=1.0)
            else Tier 2: Existing Retailer SKU Mapping
                Matcher-->>Importer: MatchResult(status="matched", method="sku_mapping", conf=0.98)
            else Tier 3: Exact Brand + Model Number + Variant Key
                Matcher-->>Importer: MatchResult(status="matched", method="brand_model_variant", conf=0.95)
            else Tier 4: Fuzzy Title Similarity >= 70%
                Matcher-->>Importer: MatchResult(status="review", method="fuzzy", candidates=[...])
            end
            Importer->>DB: Upsert Offer within SAVEPOINT
            alt Price, Shipping, or Stock Changed
                Importer->>DB: Append immutable PriceHistory record
            end
            opt Match Status == "review"
                Importer->>DB: Insert top-5 MatchCandidate records for human review
            end
        end
    end
    Importer->>DB: Update ImportRun (status="done", finished_at=now())
```

---

## 3. UML Sequence Diagram — Shopper Search, Deal Truth & Fake Markdown Audit

```mermaid
sequenceDiagram
    autonumber
    actor Shopper as Shopper / AI Agent (MCP)
    participant Router as routes_public.py / routes_api.py
    participant Service as app/services.py
    participant DB as Database

    Shopper->>Router: GET /p/{slug}?v={variant_id} (or MCP tools/call)
    Router->>DB: Fetch Product, Variants & Active Retailer Offers
    Router->>Service: offers_for_variant(db, variant, sort="delivered")
    Service-->>Router: Offers ranked by (in_stock, known_delivered_price, item_price)
    Router->>Service: price_history(db, variant, days=90)
    Service->>DB: Query PriceHistory across all matched offers
    Service-->>Router: 90-day daily lowest in-stock price points
    Router->>Service: deal_quality(current_low, history)
    Service-->>Router: 30d Median, 30d Low & Deal Truth Score (0..100)
    loop For each Offer in Variant Offers
        Router->>Service: offer_deal_audit(offer, deal_quality)
        alt Store original_price > 1.08 * 30d_Median AND current_price >= 0.99 * 30d_Median
            Service-->>Router: Flag Fake Markdown ("Inflated 'Was' Price")
        else Current Price <= 0.95 * 30d_Median
            Service-->>Router: Badge ("Verified X% below 30d median")
        end
    end
    Router-->>Shopper: Render HTML + SVG Chart + JSON-LD (or MCP JSON-RPC response)
```

---

## 4. UML State Machine Diagram — Offer Lifecycle & Freshness Governance

```mermaid
stateDiagram-v2
    [*] --> Imported : CSV / Feed / Manual Entry

    state Imported {
        [*] --> EvaluatingMatch
        EvaluatingMatch --> Matched : GTIN / SKU / Brand+Model+Variant
        EvaluatingMatch --> InReviewQueue : Fuzzy Title Similarity (>=70%)
        EvaluatingMatch --> Unmatched : No Identifier or Similar Product
        InReviewQueue --> Matched : Admin Links or Creates Product
        InReviewQueue --> Ignored : Admin Clicks Ignore (active=False)
        Unmatched --> Matched : Admin Links Manually
    }

    Matched --> Fresh : Age <= STALE_HOURS (36h phones / 48h general)
    Fresh --> Stale : STALE_HOURS < Age <= HIDE_HOURS (168h)
    Stale --> Fresh : Feed Sync or Admin "Mark Checked"
    Stale --> Hidden : Age > HIDE_HOURS (7 days)
    Hidden --> Fresh : Feed Sync or Admin "Mark Checked"
    Fresh --> Hidden : Store Suspended or Price Report Hide
```
