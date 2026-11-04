import os
import tempfile

os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or \
    f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["SECRET_KEY"] = "test"

import pyotp  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine, init_db  # noqa: E402
from app.models import Retailer, User  # noqa: E402
from app.security import hash_password  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    init_db()
    yield


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def client():
    from app.main import create_app
    return TestClient(create_app(init=False))


def csrf_of(client):
    import re
    html = client.get("/login").text
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


@pytest.fixture
def store(db):
    r = Retailer(name="Alpha Mobiles", slug="alpha", domain="alpha.pk", status="active", verified=True,
                 verification_notes="checked", permission_reference="email 2026-11-01")
    b = Retailer(name="Beta Tech", slug="beta", domain="beta.pk", status="active",
                 permission_reference="feed agreement")
    db.add_all([r, b])
    db.commit()
    return r, b


def login(client, db, role="admin", retailer=None):
    secret = pyotp.random_base32()
    u = User(email=f"{role}@t.pk", role=role, password_hash=hash_password("pass-12345678"),
             totp_secret=secret if role != "merchant" else None, retailer_id=retailer.id if retailer else None)
    db.add(u)
    db.commit()
    tok = csrf_of(client)
    client.post("/login", data={"csrf": tok, "email": u.email, "password": "pass-12345678"})
    if role != "merchant":
        tok = csrf_of(client)
        client.post("/login/mfa", data={"csrf": tok, "code": pyotp.TOTP(secret).now()})
    return u
