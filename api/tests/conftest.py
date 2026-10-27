import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.db import get_session
from app.main import app, get_gateway
from app.models import OutboxMessage, Payment


class FakeGateway:
    def create_link(self, reference: str, amount_cents: int) -> dict:
        return {"id": f"link-{reference}", "url": f"https://pay.example/{reference}"}


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_gateway] = FakeGateway
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def payment(session):
    """A payment whose link was already sent to the customer."""
    p = Payment(customer="ana", amount_cents=2500)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def callback(client, payment, status, detail):
    """Replays one gateway callback, exactly as the gateway sends it."""
    body = {"transaction": {"id": "tx", "status": status, "status_detail": detail, "dev_reference": str(payment.id)}}
    return client.post("/webhooks/paylink", json=body)


def whatsapp(session, customer="ana") -> list[str]:
    query = select(OutboxMessage).where(OutboxMessage.customer == customer, OutboxMessage.channel == "whatsapp")
    return [m.text for m in session.exec(query.order_by(OutboxMessage.id))]


def emails(session, customer="ana") -> list[str]:
    query = select(OutboxMessage).where(OutboxMessage.customer == customer, OutboxMessage.channel == "email")
    return [m.text for m in session.exec(query)]
