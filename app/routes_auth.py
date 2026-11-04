import base64
import io

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import AuditLog, User, now
from .security import (new_totp_secret, record_failure, require_csrf, reset_failures, throttled,
                       totp_uri, verify_password, verify_totp)
from .web import flash, redirect, render

router = APIRouter()


def _home_for(u: User) -> str:
    return "/merchant" if u.role == "merchant" else "/admin"


@router.get("/login")
def login_page(request: Request, next: str = ""):
    return render(request, "auth/login.html", {"next": next})


@router.post("/login", dependencies=[Depends(require_csrf)])
def login(request: Request, email: str = Form(...), password: str = Form(...), next: str = Form(""),
          db: Session = Depends(get_db)):
    email = email.strip().lower()
    key = f"{request.client.host if request.client else '-'}:{email}"
    if throttled(key):
        flash(request, "Too many attempts. Please wait 15 minutes.", "err")
        return redirect("/login")
    u = db.scalar(select(User).where(User.email == email))
    if not u or not u.active or not verify_password(password, u.password_hash):
        record_failure(key)
        flash(request, "Wrong email or password.", "err")
        return redirect("/login")
    reset_failures(key)
    request.session.clear()
    request.session["uid"] = u.id
    request.session["mfa_ok"] = False
    request.session["next"] = next if next.startswith("/") and not next.startswith("//") else ""
    if u.totp_secret:
        return redirect("/login/mfa")
    if u.role in ("admin", "editor"):  # staff must set up MFA
        return redirect("/login/mfa-setup")
    return _finish(request, db, u)


def _finish(request, db, u):
    request.session["mfa_ok"] = True
    u.last_login_at = now()
    db.add(AuditLog(user_id=u.id, action="login"))
    db.commit()
    return redirect(request.session.pop("next", "") or _home_for(u))


def _pending_user(request, db) -> User | None:
    uid = request.session.get("uid")
    return db.get(User, uid) if uid else None


@router.get("/login/mfa")
def mfa_page(request: Request):
    return render(request, "auth/mfa.html")


@router.post("/login/mfa", dependencies=[Depends(require_csrf)])
def mfa(request: Request, code: str = Form(...), db: Session = Depends(get_db)):
    u = _pending_user(request, db)
    if not u or not u.totp_secret:
        return redirect("/login")
    key = f"mfa:{u.id}"
    if throttled(key) or not verify_totp(u.totp_secret, code):
        record_failure(key)
        flash(request, "That code is not correct.", "err")
        return redirect("/login/mfa")
    reset_failures(key)
    return _finish(request, db, u)


@router.get("/login/mfa-setup")
def mfa_setup_page(request: Request, db: Session = Depends(get_db)):
    u = _pending_user(request, db)
    if not u:
        return redirect("/login")
    secret = request.session.get("new_totp") or new_totp_secret()
    request.session["new_totp"] = secret
    uri = totp_uri(secret, u.email, settings.SITE_NAME)
    qr = None
    try:
        import qrcode  # optional
        buf = io.BytesIO()
        qrcode.make(uri).save(buf, format="PNG")
        qr = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        pass
    return render(request, "auth/mfa_setup.html", {"secret": secret, "uri": uri, "qr": qr})


@router.post("/login/mfa-setup", dependencies=[Depends(require_csrf)])
def mfa_setup(request: Request, code: str = Form(...), db: Session = Depends(get_db)):
    u = _pending_user(request, db)
    secret = request.session.get("new_totp")
    if not u or not secret:
        return redirect("/login")
    if not verify_totp(secret, code):
        flash(request, "That code is not correct. Check your phone's time and try again.", "err")
        return redirect("/login/mfa-setup")
    u.totp_secret = secret
    request.session.pop("new_totp", None)
    db.add(AuditLog(user_id=u.id, action="mfa_enabled"))
    return _finish(request, db, u)


@router.post("/logout", dependencies=[Depends(require_csrf)])
def logout(request: Request):
    request.session.clear()
    return redirect("/")
