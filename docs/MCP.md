# Model Context Protocol (MCP) Server Guide (`MCP.md`)

SaleRadar includes a built-in, standards-compliant **Model Context Protocol (MCP) JSON-RPC 2.0 Server** mounted at `/api/mcp`. This allows AI assistants (such as **Antigravity, Claude Desktop, Cursor, Windsurf, and custom LangChain / Vercel AI SDK agents**) to query live Pakistani e-commerce prices, verify 30-day deal authenticity, and spot fake markdowns without scraping HTML.

---

## 1. MCP Endpoints

| Endpoint | Method | Purpose |
| :--- | :--- | :--- |
| `/api/mcp` | `GET` | Discovery manifest returning server info, protocol version (`2024-11-05`), and available tool schemas. |
| `/api/mcp` | `POST` | JSON-RPC 2.0 endpoint handling `initialize`, `tools/list`, and `tools/call`. |

---

## 2. Available MCP Tools

### 2.1 `search_products`
Searches Pakistani e-commerce products by brand, model number, Roman Urdu keywords (`fon`, `mobail`, `ghari`), or category and returns the lowest verified prices.
- **Arguments:**
  - `query` (`string`, required): Search keywords (e.g., `"Samsung A55"`, `"MacBook Air M2"`).
  - `category` (`string`, optional): Category slug (`mobile-phones`, `laptops`, `tablets`, `smartwatches`, `audio`, `power`, `tvs`, `air-conditioners`, `mens-clothing`, `womens-clothing`, `unstitched`, `shoes`, `beauty`).
  - `max_price` (`number`, optional): Maximum price filter in PKR.

### 2.2 `get_product_offers_and_truth_score`
Fetches all verified store offers, delivered prices, warranty info, promo codes, 90-day price history, 30-day **Deal Truth Score (`0–100`)**, and **Fake Markdown Audit** for an exact product slug.
- **Arguments:**
  - `slug` (`string`, required): Canonical product slug (e.g., `"samsung-galaxy-a55-5g"`).

### 2.3 `get_verified_price_drops`
Lists live verified deals where the current lowest in-stock price is strictly below the 30-day observed median price across Pakistani retailers.
- **Arguments:**
  - `category` (`string`, optional): Filter deals by category slug.
  - `limit` (`integer`, optional, default `10`): Maximum number of deals to return.

---

## 3. Example JSON-RPC 2.0 Request & Response

### Request (`POST /api/mcp`)
```json
{
  "jsonrpc": "2.0",
  "id": 101,
  "method": "tools/call",
  "params": {
    "name": "get_product_offers_and_truth_score",
    "arguments": {
      "slug": "samsung-galaxy-a55-5g"
    }
  }
}
```

### Response
```json
{
  "jsonrpc": "2.0",
  "id": 101,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\n  \"id\": 1,\n  \"title\": \"Samsung Galaxy A55 5G\",\n  \"lowest_price\": 105989.0,\n  \"deal_quality\": {\n    \"label\": \"Lowest price seen in 30 days\",\n    \"truth_score\": 95,\n    \"median_30d\": 111545.0\n  },\n  \"offers\": [...]\n}"
      }
    ],
    "isError": false
  }
}
```
