# Setup, Installation & Deployment Guide (`SETUP.md`)

SaleRadar supports three deployment modes:
1. **Local Development** (Python 3.12+ with zero-config SQLite or PostgreSQL).
2. **Vercel Serverless Deployment** (`vercel --prod` with Neon/Supabase Postgres or built-in auto-seeded demo DB).
3. **Self-Hosted Linux Server** (`docker compose up -d --build` with PostgreSQL 16, background worker, Caddy HTTPS, and automated nightly backups).

---

## 1. Local Development Setup

### Prerequisites
- Python `3.12` or `3.13`
- Git

### Step-by-Step Commands

**Linux / macOS:**
```bash
git clone https://github.com/Laraibshah297/sale-radar.git
cd sale-radar
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

# Initialize database & load 14 fictional demo stores + 45-day price history
.venv/bin/python -m app.cli seed-demo

# Optional: load 22 real Pakistani prospect stores (admin-only status='prospect')
.venv/bin/python -m app.cli seed-prospects

# Create an admin account (prints temporary password; MFA enrolled on first login)
.venv/bin/python -m app.cli create-admin admin@saleradar.pk

# Start the development server
.venv/bin/uvicorn app.main:app --reload --port 8000
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/Laraibshah297/sale-radar.git
cd sale-radar
python -m venv .venv
.\.venv\Scripts\pip install -r requirements-dev.txt
.\.venv\Scripts\python -m app.cli seed-demo
.\.venv\Scripts\python -m app.cli create-admin admin@saleradar.pk
.\.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

Open:
- **Shopper Website:** `http://localhost:8000`
- **Live Verified Deals:** `http://localhost:8000/deals`
- **Side-by-Side Compare:** `http://localhost:8000/compare`
- **Interactive OpenAPI Docs:** `http://localhost:8000/api/docs`
- **MCP Server Discovery:** `http://localhost:8000/api/mcp`
- **Admin / Merchant Login:** `http://localhost:8000/login`

---

## 2. Environment Variables Reference (`.env`)

| Variable | Default | Description |
| :--- | :--- | :--- |
| `SITE_NAME` | `Sale Radar` | Platform brand title |
| `BASE_URL` | `http://localhost:8000` | Public canonical root URL (no trailing slash) |
| `DATABASE_URL` | `sqlite:///./saleradar.db` | SQLAlchemy connection string (`postgresql+psycopg://...` or `postgres://...`) |
| `SECRET_KEY` | `dev-only-change-me` | 48-byte random secret for signing session cookies |
| `COOKIE_SECURE` | `0` | Set to `1` in HTTPS production so cookies are `Secure` |
| `AUTO_SEED_DEMO` | `1` on Vercel, `0` otherwise | Automatically seeds demo catalog if DB is empty on startup |
| `STALE_HOURS` | `48` | Hours before an offer is badged `Stale price` (`36h` for mobile phones) |
| `HIDE_HOURS` | `168` (7 days) | Hours before an offer is hidden from live comparison tables |
| `SMTP_HOST` / `SMTP_PORT` | `""` / `587` | SMTP server for price-drop alert emails (stored in `/admin/outbox` if empty) |
| `SMTP_USER` / `SMTP_PASSWORD` | `""` | SMTP credentials (Brevo, Mailjet, Zoho, SES) |
| `MAIL_FROM` | `alerts@saleradar.pk` | Sender address for transactional emails |

---

## 3. Deploying to Vercel (Serverless)

SaleRadar includes `vercel.json` and `api/index.py` for zero-configuration Vercel deployment:
1. Install Vercel CLI or connect the GitHub repository in the Vercel Dashboard.
2. Run:
   ```bash
   vercel deploy --prod --yes
   ```
3. **Database Options on Vercel:**
   - **Instant Preview / Demo Mode (Zero Config):** When deployed without `DATABASE_URL`, SaleRadar automatically uses `/tmp/saleradar.db` and seeds the 14 demo stores, 50+ products, 900+ offers, and 45-day price history on cold start (`AUTO_SEED_DEMO=1`).
   - **Persistent Production Mode:** Attach a **Vercel Postgres (Neon)** or **Supabase Postgres** database in Vercel Project Settings. SaleRadar automatically normalizes `POSTGRES_URL` / `DATABASE_URL` (`postgres://` -> `postgresql+psycopg://`) and provisions tables + `pg_trgm` indexes on boot.

---

## 4. Deploying on a Linux VPS with Docker Compose

```bash
cp .env.example .env
# Edit .env with DOMAIN, BASE_URL, SECRET_KEY, POSTGRES_PASSWORD, DATABASE_URL
docker compose up -d --build
docker compose exec web python -m app.cli create-admin admin@saleradar.pk
```
- **Nightly Backups:** The `backup` container dumps compressed PostgreSQL backups into `./backups/saleradar-YYYYMMDD-HHMM.sql.gz` every 24 hours and prunes backups older than 14 days.
