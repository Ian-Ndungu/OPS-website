import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["UPLOAD_DIR"] = "./test_uploads"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app import models  # noqa: F401
from app.models.core import Role, User
from app.providers import payments
from app.security import hash_password


_HASH = hash_password("password123")


class StubProvider(payments.PaymentProvider):
    """Test double. Never used by application code; it only records requests.
    It does NOT confirm anything: tests must feed callbacks explicitly."""

    def __init__(self):
        self.stk, self.b2c, self.fail_phones = [], [], set()

    def stk_push(self, phone, amount, reference, description):
        self.stk.append((phone, amount))
        n = len(self.stk)
        return payments.StkResult(f"ws_CO_{n:04d}", f"mr_{n}")

    def b2c_payout(self, phone, amount, reference, remarks):
        if phone in self.fail_phones:
            raise payments.ProviderError("rejected")
        self.b2c.append((phone, amount, reference))
        return payments.B2CResult(reference)

    def stk_status(self, checkout_request_id):
        return {}


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, autoflush=True, expire_on_commit=False)()
    yield s
    s.close()


@pytest.fixture()
def db_prod():
    """Session configured exactly like app.db.SessionLocal (autoflush off). Callers commit between
    steps, as the routers do."""
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield s
    s.close()


@pytest.fixture()
def provider():
    p = StubProvider()
    payments.set_provider(p)
    yield p
    payments.set_provider(None)


def make_user(db, email, role=Role.member.value, **kw):
    u = User(email=email, hashed_password=_HASH, gamer_tag=email.split("@")[0],
             role=role, **kw)
    db.add(u)
    db.commit()  # committed so API-level rollbacks don't discard fixtures
    return u


@pytest.fixture()
def admins(db):
    return {"finance1": make_user(db, "fin1@x.com", Role.finance_admin.value),
            "finance2": make_user(db, "fin2@x.com", Role.finance_admin.value),
            "verifier": make_user(db, "ver@x.com", Role.clan_verifier.value),
            "content": make_user(db, "cont@x.com", Role.content_admin.value),
            "results": make_user(db, "res@x.com", Role.results_admin.value)}
