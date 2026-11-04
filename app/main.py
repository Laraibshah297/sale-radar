import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException as FHTTPException
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .db import init_db
from .web import LoginRequired, redirect, render

log = logging.getLogger("saleradar")


def create_app(init: bool = True) -> FastAPI:
    if settings.SECRET_KEY == "dev-only-change-me" and settings.BASE_URL.startswith("https"):
        raise RuntimeError("Set a real SECRET_KEY in production")
    if init:
        init_db()
    app = FastAPI(title=settings.SITE_NAME, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY, session_cookie="sr_session",
                       max_age=60 * 60 * 24 * 30, same_site="lax", https_only=settings.COOKIE_SECURE)
    app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

    from . import routes_admin, routes_auth, routes_merchant, routes_public
    app.include_router(routes_public.router)
    app.include_router(routes_auth.router)
    app.include_router(routes_admin.router)
    app.include_router(routes_merchant.router)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if request.url.path.startswith(("/admin", "/merchant", "/login")):
            resp.headers["Cache-Control"] = "no-store"
            resp.headers["X-Robots-Tag"] = "noindex"
        return resp

    @app.exception_handler(LoginRequired)
    async def _login(request: Request, exc: LoginRequired):
        return redirect(f"/login?next={exc.next_url}")

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: FHTTPException):
        titles = {404: "Page not found", 403: "Not allowed", 400: "Something is wrong with that request"}
        return render(request, "pages/message.html",
                      {"title": titles.get(exc.status_code, "Error"),
                       "body": exc.detail if exc.status_code != 404 else
                       "We couldn't find that page. Try searching instead."},
                      status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _err(request: Request, exc: Exception):
        log.exception("unhandled error on %s", request.url.path)
        return render(request, "pages/message.html", {
            "title": "Something went wrong", "body": "Please try again in a moment."}, status_code=500)

    return app


app = create_app()
