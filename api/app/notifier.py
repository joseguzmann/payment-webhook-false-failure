"""Sends messages to the customer. The outbox table plays the role of the WhatsApp and email channels."""

from sqlmodel import Session

from .models import OutboxMessage

PAYMENT_OK = "✅ Payment received. Thank you, your order is confirmed."
PAYMENT_FAILED = "❌ We could not process your payment. Please try again."
RECEIPT = "Receipt: your payment was approved."


def send(session: Session, customer: str, text: str, *, source: str,
         channel: str = "whatsapp", trace_id: str | None = None) -> OutboxMessage:
    message = OutboxMessage(customer=customer, channel=channel, text=text, source=source, trace_id=trace_id)
    session.add(message)
    return message
