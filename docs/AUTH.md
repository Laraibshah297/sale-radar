# Authentication, Authorization & Security (`AUTH.md`)

## 1. Role-Based Access Control (RBAC) Matrix

SaleRadar enforces strict role separation across three user roles stored in `users.role`:

| Capability / Route | Anonymous Shopper | `merchant` (Retailer SaaS) | `editor` (Catalog Staff) | `admin` (Superuser) |
| :--- | :---: | :---: | :---: | :---: |
| Search, Compare, Deals, Price Alerts, Price Reports | ✅ | ✅ | ✅ | ✅ |
| `/api/v1/*` & `/api/mcp` Read Endpoints | ✅ | ✅ | ✅ | ✅ |
| `/merchant` (Own Store CSV Upload, Feed Health, Clicks) | ❌ | ✅ (Scoped to `user.retailer_id`) | ❌ | ❌ |
| `/merchant/competitors` & Scheduled Feed URLs | ❌ | ✅ (`retailer.plan == "pro"`) | ❌ | ❌ |
| `/admin` (Catalog, Retailers, Offers, Match Review, Imports) | ❌ | ❌ | ✅ (Requires TOTP MFA) | ✅ (Requires TOTP MFA) |
| Delete Canonical Products (`/admin/products/{id}/delete`) | ❌ | ❌ | ❌ | ✅ (Requires TOTP MFA) |
| Manage Staff/Merchant Users & Reset MFA (`/admin/users`) | ❌ | ❌ | ❌ | ✅ (Requires TOTP MFA) |
| View Full System Audit Log (`/admin/audit`) | ❌ | ❌ | ❌ | ✅ (Requires TOTP MFA) |

---

## 2. Authentication & Mandatory Staff TOTP MFA Flow

1. **Password Hashing:** All passwords are hashed with **Bcrypt** via `passlib.context.CryptContext(schemes=["bcrypt"])`. Minimum 10-character password policy on merchant signup; cryptographically random temporary passwords (`secrets.token_urlsafe(12)`) on admin user creation.
2. **Sliding-Window Login Rate Limiting (`app/security.py`):**
   - Tracks failed login attempts per `(client_ip, email)` and failed MFA attempts per `mfa:{user_id}`.
   - Blocks brute-force attacks after **8 failed attempts within a 15-minute window** (`WINDOW = 900s, MAX_ATTEMPTS = 8`).
3. **Mandatory Two-Step Verification (TOTP MFA) for Staff:**
   - When an `admin` or `editor` logs in for the first time (`user.totp_secret is None`), their session sets `mfa_ok = False` and redirects them to `/login/mfa-setup`.
   - `/login/mfa-setup` generates a Base32 TOTP secret (`pyotp.random_base32()`), renders an inline Base64 PNG QR code for Google Authenticator / Authy / 1Password, and requires a valid 6-digit RFC 6238 code (`valid_window=1`) before granting `mfa_ok = True`.
   - No `/admin/*` route is accessible unless both `session["uid"]` and `session["mfa_ok"] == True` are verified by `current_user()`.

---

## 3. CSRF, Session & Outbound Redirect Security

- **Signed Session Cookies:** `SessionMiddleware` signs `sr_session` cookies using `SECRET_KEY` with `SameSite=Lax`, 30-day expiration, and `https_only=True` when `COOKIE_SECURE=1`.
- **Constant-Time CSRF Protection (`require_csrf`):** Every `POST` form and state-changing web endpoint validates a per-session 256-bit random token (`secrets.token_urlsafe(32)`) using `hmac.compare_digest(sent, expected)` to prevent timing attacks and Cross-Site Request Forgery.
- **Open-Redirect Prevention (`/go/{offer_id}` & `/login?next=`):**
  - Outbound offer redirects verify `host_allowed(offer.product_url, offer.retailer.domain)` so a compromised CSV row can never redirect shoppers to a phishing domain.
  - Post-login `next` URLs must start with a single `/` (`next.startswith("/") and not next.startswith("//")`).
- **HTTP Security Headers Middleware:**
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Cache-Control: no-store` and `X-Robots-Tag: noindex` on `/admin`, `/merchant`, and `/login`.
