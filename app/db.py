from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    kw = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kw["connect_args"] = {"check_same_thread": False}
    eng = create_engine(url, **kw)
    if url.startswith("sqlite"):
        @event.listens_for(eng, "connect")
        def _fk(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")
    return eng


engine = make_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def is_postgres() -> bool:
    return engine.dialect.name == "postgresql"


def init_db(eng=None):
    from . import models  # noqa: F401  (register tables)
    eng = eng or engine
    if eng.dialect.name == "postgresql":
        with eng.begin() as c:
            c.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    Base.metadata.create_all(eng)
    if eng.dialect.name == "postgresql":
        with eng.begin() as c:
            c.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_products_search_trgm "
                "ON products USING gin (search_text gin_trgm_ops)")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
