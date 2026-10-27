from sqlmodel import select

from app.models import OutboxMessage, Payment, Trace


def test_payment_request_creates_link_and_trace(client, session):
    reply = client.post("/chat", json={"customer": "ana", "text": "I want to pay"}).json()

    payment = session.exec(select(Payment)).one()
    assert payment.status == "pending"
    assert payment.link_url in reply["text"]
    assert session.get(Trace, reply["trace_id"]) is not None


def test_agent_messages_always_carry_a_trace(client, session):
    client.post("/chat", json={"customer": "ana", "text": "hello"})
    client.post("/chat", json={"customer": "ana", "text": "checkout please"})

    messages = session.exec(select(OutboxMessage)).all()
    assert all(m.source == "agent" and m.trace_id for m in messages)
