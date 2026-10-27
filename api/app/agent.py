"""A stand-in for the sales agent: one customer message in, one reply out, recorded as a trace.

The real agent was an LLM graph traced in Langfuse. This one is deterministic so the demo runs
without API keys, but it keeps the property that mattered in the investigation: every message
the agent sends has a trace, and messages sent by the webhook do not.
"""

import uuid

from sqlmodel import Session

from . import notifier
from .models import OutboxMessage, Payment, Trace

PAY_WORDS = ("pay", "buy", "checkout")


def handle_turn(session: Session, gateway, customer: str, text: str, amount_cents: int = 2500) -> OutboxMessage:
    trace = Trace(id=uuid.uuid4().hex[:12], customer=customer, input=text)
    session.add(trace)
    if any(word in text.lower() for word in PAY_WORDS):
        payment = Payment(customer=customer, amount_cents=amount_cents)
        session.add(payment)
        session.commit()
        session.refresh(payment)
        link = gateway.create_link(reference=str(payment.id), amount_cents=amount_cents)
        payment.link_id, payment.link_url = link["id"], link["url"]
        reply = f"Here is your payment link for ${amount_cents / 100:.2f}: {link['url']}"
    else:
        reply = 'Hi! Write "I want to pay" and I will send you a payment link.'
    trace.output = reply
    message = notifier.send(session, customer, reply, source="agent", trace_id=trace.id)
    session.commit()
    session.refresh(message)
    return message
