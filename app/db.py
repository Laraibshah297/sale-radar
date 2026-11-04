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
    _add_missing_columns(eng)
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


# Columns added after the first release. create_all() doesn't alter existing
# tables, so add them here (safe to run every start).
_NEW_COLUMNS = [("categories", "group", "VARCHAR(60) DEFAULT 'Other'")]


def _add_missing_columns(eng):
    from sqlalchemy import inspect
    insp = inspect(eng)
    with eng.begin() as c:
        for table, col, ddl in _NEW_COLUMNS:
            if col not in {x["name"] for x in insp.get_columns(table)}:
                c.exec_driver_sql(f'ALTER TABLE {table} ADD COLUMN "{col}" {ddl}')
