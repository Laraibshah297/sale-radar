"""Templates, i18n (English / Urdu) and request helpers shared by all routes."""
from decimal import Decimal
from pathlib import Path

from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import User
from .security import csrf_token
from .services import freshness, humanize_age

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

UR = {
    "Search": "تلاش", "Search phones, laptops, clothes, shoes…": "موبائل، لیپ ٹاپ، کپڑے، جوتے تلاش کریں…",
    "Compare real prices from verified Pakistani stores": "تصدیق شدہ پاکستانی اسٹورز کی اصل قیمتوں کا موازنہ کریں",
    "Categories": "زمرے", "Verified stores": "تصدیق شدہ اسٹورز", "How prices are checked": "قیمتیں کیسے چیک ہوتی ہیں",
    "Popular comparisons": "مقبول موازنے", "Lowest price": "کم ترین قیمت", "stores": "اسٹورز",
    "Visit store": "اسٹور پر جائیں", "Price alert": "قیمت الرٹ", "Report incorrect price": "غلط قیمت کی اطلاع دیں",
    "Shipping": "ڈیلیوری", "Warranty": "وارنٹی", "Stock": "اسٹاک", "Last checked": "آخری بار چیک",
    "In stock": "دستیاب", "Out of stock": "دستیاب نہیں", "Unknown": "معلوم نہیں", "Free": "مفت",
    "Sort": "ترتیب", "Filters": "فلٹرز", "Brand": "برانڈ", "Store": "اسٹور", "Price": "قیمت",
    "Apply": "لاگو کریں", "results": "نتائج", "List your store": "اپنا اسٹور شامل کریں",
    "About": "ہمارے بارے میں", "Contact": "رابطہ", "Privacy": "پرائیویسی", "Terms": "شرائط",
    "Affiliate disclosure": "ایفیلیئٹ انکشاف", "Sponsored": "اسپانسرڈ", "Stale price": "پرانی قیمت",
    "Price history": "قیمت کی تاریخ", "Offers": "آفرز", "Notify me": "مجھے بتائیں",
    "We are not the seller. Prices and stock can change; always verify at the retailer's checkout.":
        "ہم فروخت کنندہ نہیں ہیں۔ قیمت اور اسٹاک بدل سکتے ہیں؛ ہمیشہ ریٹیلر کے چیک آؤٹ پر تصدیق کریں۔",
}


def t(request: Request, text: str) -> str:
    return UR.get(text, text) if request.session.get("lang") == "ur" else text


def pkr(v) -> str:
    if v is None:
        return "—"
    v = Decimal(v)
    return f"Rs {v:,.0f}"


templates.env.filters["pkr"] = pkr
templates.env.filters["ago"] = humanize_age
templates.env.globals.update(settings=settings, freshness=freshness)


def render(request: Request, name: str, ctx: dict | None = None, status_code: int = 200):
    c = {"request": request, "csrf": csrf_token(request), "user": getattr(request.state, "user", None),
         "_": lambda s: t(request, s), "lang": request.session.get("lang", "en"),
         "flash": request.session.pop("flash", None)}
    c.update(ctx or {})
    return templates.TemplateResponse(request, name, c, status_code=status_code)


def flash(request: Request, msg: str, kind: str = "ok"):
    request.session["flash"] = {"msg": msg, "kind": kind}


def redirect(url: str):
    return RedirectResponse(url, status_code=303)


def current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    uid = request.session.get("uid")
    if not uid or not request.session.get("mfa_ok"):
        return None
    u = db.get(User, uid)
    if not u or not u.active:
        return None
    request.state.user = u
    return u


class LoginRequired(Exception):
    def __init__(self, next_url: str):
        self.next_url = next_url


def require_role(*roles):
    def dep(request: Request, user: User | None = Depends(current_user)) -> User:
        if not user:
            raise LoginRequired(str(request.url.path))
        if user.role not in roles:
            raise HTTPException(403, "You do not have access to this page.")
        return user
    return dep


require_staff = require_role("admin", "editor")
require_admin = require_role("admin")
require_merchant = require_role("merchant")


def chart_svg(points) -> str:
    """Small server-side SVG line chart (no JavaScript needed)."""
    from markupsafe import escape
    if len(points) < 2:
        return ""
    W, H, P = 640, 180, 34
    ys = [float(p.price) for p in points]
    lo, hi = min(ys), max(ys)
    span = (hi - lo) or 1
    def x(i): return P + i * (W - 2 * P) / (len(points) - 1)
    def y(v): return H - P - (v - lo) * (H - 2 * P) / span
    d = " ".join(f"{'M' if i == 0 else 'L'}{x(i):.1f},{y(v):.1f}" for i, v in enumerate(ys))
    return (f'<svg class="chart" viewBox="0 0 {W} {H}" width="100%" role="img" '
            f'aria-label="Price history from {pkr(lo)} to {pkr(hi)}">'
            f'<line x1="{P}" y1="{H-P}" x2="{W-P}" y2="{H-P}" stroke="var(--line)"/>'
            f'<path d="{d}" fill="none" stroke="var(--brand2)" stroke-width="2.5" stroke-linejoin="round"/>'
            f'<circle cx="{x(len(ys)-1):.1f}" cy="{y(ys[-1]):.1f}" r="4" fill="var(--brand2)"/>'
            f'<text x="{P}" y="14">{escape(pkr(hi))}</text><text x="{P}" y="{H-P+16}">{escape(pkr(lo))}</text>'
            f'<text x="{P}" y="{H-4}">{escape(points[0].day)}</text>'
            f'<text x="{W-P}" y="{H-4}" text-anchor="end">{escape(points[-1].day)}</text></svg>')


def jsonld(product, variant, offers) -> str:
    import json
    prices = [float(o.price) for o in offers if o.stock_status != "out_of_stock"] or [float(o.price) for o in offers]
    data = {"@context": "https://schema.org", "@type": "Product", "name": product.title,
            "brand": {"@type": "Brand", "name": product.brand},
            "offers": {"@type": "AggregateOffer", "priceCurrency": "PKR", "lowPrice": min(prices),
                       "highPrice": max(prices), "offerCount": len(offers)}}
    if product.image_url:
        data["image"] = product.image_url
    if product.model_number:
        data["mpn"] = product.model_number
    if variant and variant.gtin:
        data["gtin"] = variant.gtin
    return json.dumps(data).replace("</", "<\\/")


templates.env.globals.update(chart_svg=chart_svg, jsonld=jsonld)


def qs(pairs, drop: tuple | None = None, **set_):
    """Build a query string from (key, value) pairs, optionally dropping one
    (key, value) pair and overriding keys, e.g. qs(base_qs, page=2)."""
    from urllib.parse import urlencode
    out = [(k, v) for k, v in pairs if not (drop and k == drop[0] and v == drop[1]) and k not in set_]
    out += [(k, v) for k, v in set_.items() if v not in (None, "")]
    return "?" + urlencode(out)


from .filters import filter_label as _fl  # noqa: E402
templates.env.globals.update(qs=qs, spec_label=_fl)
