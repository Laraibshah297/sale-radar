"""Settings, read from environment variables (see .env.example)."""
import os


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


class Settings:
    SITE_NAME = os.environ.get("SITE_NAME", "Sale Radar")
    BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
    DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./saleradar.db")
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    DEFAULT_CURRENCY = "PKR"

    # Freshness rules (hours). An offer older than STALE is labelled stale;
    # older than HIDE it is not shown as a live price at all.
    STALE_HOURS = _int("STALE_HOURS", 48)
    HIDE_HOURS = _int("HIDE_HOURS", 24 * 7)
    CATEGORY_STALE_HOURS = {"mobile-phones": 36, "laptops": 72, "accessories": 72}

    # Email (price alerts, confirmations). If SMTP_HOST is empty, emails are
    # stored in the outbox table and shown in the admin panel instead.
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = _int("SMTP_PORT", 587)
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "alerts@example.com")

    CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "hello@example.com")
    COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"


settings = Settings()


def stale_hours_for(category_slug: str | None) -> int:
    return settings.CATEGORY_STALE_HOURS.get(category_slug or "", settings.STALE_HOURS)
