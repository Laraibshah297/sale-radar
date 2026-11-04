"""Passwords, TOTP MFA, CSRF, login throttling and the anonymous session id."""
import hmac
import secrets
import time
from collections import defaultdict

import pyotp
from fastapi import HTTPException, Request
from passlib.context import CryptContext

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(p: str) -> str:
    return pwd.hash(p)


def verify_password(p: str, h: str) -> bool:
    try:
        return pwd.verify(p, h)
    except Exception:
        return False


def new_totp_secret() -> str:
    return pyotp.random_base32()


def verify_totp(secret: str, code: str) -> bool:
    return bool(secret) and pyotp.TOTP(secret).verify((code or "").replace(" ", ""), valid_window=1)


def totp_uri(secret: str, email: str, issuer: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


# ---- CSRF: one random token per session, required on every POST form
def csrf_token(request: Request) -> str:
    tok = request.session.get("csrf")
    if not tok:
        tok = secrets.token_urlsafe(32)
        request.session["csrf"] = tok
    return tok


async def require_csrf(request: Request):
    if request.method != "POST":
        return
    form = await request.form()
    sent = str(form.get("csrf") or request.headers.get("x-csrf-token") or "")
    expected = request.session.get("csrf") or ""
    if not sent or not expected or not hmac.compare_digest(sent, expected):
        raise HTTPException(status_code=400, detail="Form expired. Go back, refresh the page and try again.")


# ---- simple in-memory login throttle (per IP + email)
_attempts: dict[str, list[float]] = defaultdict(list)
WINDOW, MAX_ATTEMPTS = 15 * 60, 8


def throttled(key: str) -> bool:
    t = time.time()
    _attempts[key] = [a for a in _attempts[key] if t - a < WINDOW]
    return len(_attempts[key]) >= MAX_ATTEMPTS


def record_failure(key: str):
    _attempts[key].append(time.time())


def reset_failures(key: str):
    _attempts.pop(key, None)


def session_id(request: Request) -> str:
    sid = request.session.get("sid")
    if not sid:
        sid = secrets.token_hex(16)
        request.session["sid"] = sid
    return sid


BOT_MARKERS = ("bot", "crawl", "spider", "slurp", "preview", "curl", "wget", "python-requests", "httpx",
               "headless")


def looks_like_bot(ua: str | None) -> bool:
    ua = (ua or "").lower()
    return not ua or any(m in ua for m in BOT_MARKERS)
