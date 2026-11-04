"""Data model, following the blueprint: a canonical Product has Variants;
each Retailer's listing is an Offer on exactly one Variant. Prices are
DECIMAL with an explicit currency, and every price change is kept in
PriceHistory (never overwritten)."""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String,
                        Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sqlalchemy.types import TypeDecorator

from .db import Base


class UTCDateTime(TypeDecorator):
    """Always stores and returns timezone-aware UTC datetimes (SQLite drops tz)."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc) if value is not None else None

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


def now():
    return datetime.now(timezone.utc)


Money = Numeric(12, 2)


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    # spec keys shown as filters on the category page, e.g. ["storage", "ram"]
    filter_specs: Mapped[list] = mapped_column(JSON, default=list)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    slug: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    brand: Mapped[str] = mapped_column(String(120), index=True)
    model_number: Mapped[str | None] = mapped_column(String(120), index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    specs: Mapped[dict] = mapped_column(JSON, default=dict)
    image_url: Mapped[str | None] = mapped_column(String(1000))
    description: Mapped[str | None] = mapped_column(Text)
    search_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)

    category: Mapped[Category | None] = relationship()
    variants: Mapped[list["Variant"]] = relationship(back_populates="product",
                                                     cascade="all, delete-orphan")


class Variant(Base):
    __tablename__ = "variants"
    __table_args__ = (UniqueConstraint("product_id", "variant_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    storage: Mapped[str | None] = mapped_column(String(40))
    ram: Mapped[str | None] = mapped_column(String(40))
    colour: Mapped[str | None] = mapped_column(String(60))
    size: Mapped[str | None] = mapped_column(String(40))
    region: Mapped[str | None] = mapped_column(String(60))  # e.g. PTA approved / non-PTA
    gtin: Mapped[str | None] = mapped_column(String(20), unique=True)
    variant_key: Mapped[str] = mapped_column(String(200), default="")

    product: Mapped[Product] = relationship(back_populates="variants")
    offers: Mapped[list["Offer"]] = relationship(back_populates="variant")

    @property
    def label(self):
        parts = [p for p in (self.storage, self.ram and f"{self.ram} RAM", self.colour,
                             self.size, self.region) if p]
        return " · ".join(parts) or "Standard"


class Retailer(Base):
    __tablename__ = "retailers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(180), unique=True)
    domain: Mapped[str] = mapped_column(String(200))  # allow-listed outbound host
    city: Mapped[str | None] = mapped_column(String(120))
    delivery_regions: Mapped[str | None] = mapped_column(String(300))
    phone: Mapped[str | None] = mapped_column(String(60))
    email: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(300))
    return_policy_url: Mapped[str | None] = mapped_column(String(500))
    warranty_policy_url: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    logo_url: Mapped[str | None] = mapped_column(String(1000))
    # status: pending (applied), active, suspended
    status: Mapped[str] = mapped_column(String(20), default="pending")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_notes: Mapped[str | None] = mapped_column(Text)  # evidence, shown to admins
    feed_method: Mapped[str] = mapped_column(String(20), default="csv")  # csv|feed_url|manual|shopify
    feed_url: Mapped[str | None] = mapped_column(String(1000))
    permission_reference: Mapped[str | None] = mapped_column(String(300))
    affiliate_status: Mapped[str] = mapped_column(String(30), default="none")
    affiliate_param: Mapped[str | None] = mapped_column(String(200))  # e.g. "ref=saleradar"
    plan: Mapped[str] = mapped_column(String(20), default="free")  # free|pro
    last_import_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)

    offers: Mapped[list["Offer"]] = relationship(back_populates="retailer")


class Offer(Base):
    __tablename__ = "offers"
    __table_args__ = (UniqueConstraint("retailer_id", "retailer_sku"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    retailer_id: Mapped[int] = mapped_column(ForeignKey("retailers.id", ondelete="CASCADE"))
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("variants.id", ondelete="SET NULL"))
    retailer_sku: Mapped[str] = mapped_column(String(200))
    retailer_title: Mapped[str] = mapped_column(String(400))  # original, kept for audit
    product_url: Mapped[str] = mapped_column(String(1000))
    price: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3), default="PKR")
    shipping_cost: Mapped[Decimal | None] = mapped_column(Money)  # None = unknown
    stock_status: Mapped[str] = mapped_column(String(20), default="in_stock")
    condition: Mapped[str] = mapped_column(String(20), default="new")
    warranty_type: Mapped[str | None] = mapped_column(String(120))
    image_url: Mapped[str | None] = mapped_column(String(1000))
    checked_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    source: Mapped[str] = mapped_column(String(30), default="manual")
    import_run_id: Mapped[int | None] = mapped_column(ForeignKey("import_runs.id", ondelete="SET NULL"))
    permission_reference: Mapped[str | None] = mapped_column(String(300))
    # matching
    match_status: Mapped[str] = mapped_column(String(20), default="matched")  # matched|review|unmatched
    match_method: Mapped[str | None] = mapped_column(String(40))
    match_confidence: Mapped[float | None] = mapped_column()
    match_evidence: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)

    retailer: Mapped[Retailer] = relationship(back_populates="offers")
    variant: Mapped[Variant | None] = relationship(back_populates="offers")

    @property
    def delivered_price(self):
        return None if self.shipping_cost is None else self.price + self.shipping_cost


class PriceHistory(Base):
    __tablename__ = "price_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), index=True)
    price: Mapped[Decimal] = mapped_column(Money)
    shipping_cost: Mapped[Decimal | None] = mapped_column(Money)
    stock_status: Mapped[str] = mapped_column(String(20))
    captured_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, index=True)


class ImportRun(Base):
    __tablename__ = "import_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    retailer_id: Mapped[int | None] = mapped_column(ForeignKey("retailers.id", ondelete="SET NULL"))
    source: Mapped[str] = mapped_column(String(40))  # csv_upload|feed_url|shopify|admin
    filename: Mapped[str | None] = mapped_column(String(300))
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(20), default="running")
    rows_total: Mapped[int] = mapped_column(Integer, default=0)
    rows_ok: Mapped[int] = mapped_column(Integer, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0)
    rows_review: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    rejects: Mapped[list["ImportReject"]] = relationship(cascade="all, delete-orphan")


class ImportReject(Base):
    __tablename__ = "import_rejects"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id", ondelete="CASCADE"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    reasons: Mapped[str] = mapped_column(Text)
    row: Mapped[dict] = mapped_column(JSON, default=dict)


class MatchCandidate(Base):
    """An offer the matcher was not sure about; waits for human review."""
    __tablename__ = "match_candidates"
    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), index=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("variants.id", ondelete="CASCADE"))
    score: Mapped[float] = mapped_column()
    evidence: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|accepted|rejected

    offer: Mapped[Offer] = relationship()
    variant: Mapped[Variant] = relationship()


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))  # admin|editor|merchant
    retailer_id: Mapped[int | None] = mapped_column(ForeignKey("retailers.id", ondelete="SET NULL"))
    totp_secret: Mapped[str | None] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    retailer: Mapped[Retailer | None] = relationship()


class ClickEvent(Base):
    __tablename__ = "click_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int | None] = mapped_column(ForeignKey("offers.id", ondelete="SET NULL"), index=True)
    retailer_id: Mapped[int | None] = mapped_column(ForeignKey("retailers.id", ondelete="SET NULL"), index=True)
    session_id: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str | None] = mapped_column(String(60))  # product|search|alert|sponsored
    referrer: Mapped[str | None] = mapped_column(String(500))
    campaign: Mapped[str | None] = mapped_column(String(100))
    sponsored: Mapped[bool] = mapped_column(Boolean, default=False)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, index=True)


class SearchLog(Base):
    __tablename__ = "search_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    query: Mapped[str] = mapped_column(String(300))
    results: Mapped[int] = mapped_column(Integer)
    session_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, index=True)


class ProductView(Base):
    __tablename__ = "product_views"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str | None] = mapped_column(String(64))
    from_search: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, index=True)


class AffiliateConversion(Base):
    __tablename__ = "affiliate_conversions"
    id: Mapped[int] = mapped_column(primary_key=True)
    network: Mapped[str] = mapped_column(String(80))
    click_id: Mapped[int | None] = mapped_column(ForeignKey("click_events.id", ondelete="SET NULL"))
    reference: Mapped[str | None] = mapped_column(String(200))
    order_status: Mapped[str] = mapped_column(String(30), default="pending")
    commission: Mapped[Decimal | None] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3), default="PKR")
    validated_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)


class SponsoredCampaign(Base):
    """Paid placement. Shown in a separate, labelled block; never changes
    the organic price ranking."""
    __tablename__ = "sponsored_campaigns"
    id: Mapped[int] = mapped_column(primary_key=True)
    retailer_id: Mapped[int] = mapped_column(ForeignKey("retailers.id", ondelete="CASCADE"))
    offer_id: Mapped[int | None] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(160))
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    ends_at: Mapped[datetime] = mapped_column(UTCDateTime)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    budget_note: Mapped[str | None] = mapped_column(String(300))

    retailer: Mapped[Retailer] = relationship()
    offer: Mapped[Offer | None] = relationship()


class PriceAlert(Base):
    __tablename__ = "price_alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), index=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("variants.id", ondelete="CASCADE"))
    target_price: Mapped[Decimal] = mapped_column(Money)
    token: Mapped[str] = mapped_column(String(64), unique=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)  # double opt-in
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_notified_price: Mapped[Decimal | None] = mapped_column(Money)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)

    variant: Mapped[Variant] = relationship()


class PriceReport(Base):
    __tablename__ = "price_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"))
    reason: Mapped[str] = mapped_column(String(40))  # wrong_price|out_of_stock|wrong_product|other
    note: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)

    offer: Mapped[Offer] = relationship()


class ContactMessage(Base):
    __tablename__ = "contact_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))  # contact|correction|takedown|merchant_application
    name: Mapped[str | None] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)


class EmailOutbox(Base):
    __tablename__ = "email_outbox"
    id: Mapped[int] = mapped_column(primary_key=True)
    to: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(80))
    entity: Mapped[str | None] = mapped_column(String(60))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, index=True)

    user: Mapped[User | None] = relationship()
