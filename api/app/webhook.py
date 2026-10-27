"""PayLink webhook: turns a gateway callback into a payment status and a message to the customer.

Callback body: {"transaction": {"id", "status", "status_detail", "dev_reference"}}, where
dev_reference is our payment id. Status "1" with detail "3" means approved.
"""

from sqlmodel import Session

from . import notifier
from .models import Payment, now

APPROVED = "1"


def handle_callback(session: Session, payload: dict) -> str:
    tx = payload["transaction"]
    payment = session.get(Payment, int(tx["dev_reference"]))
    if payment is None:
        return "unknown_payment"
    if payment.status == "paid":
        return "already_paid"

    if tx["status"] == APPROVED:
        # A later approval wins over an earlier failure: the gateway can change its mind.
        payment.status = "paid"
        notifier.send(session, payment.customer, notifier.PAYMENT_OK, source="webhook")
        notifier.send(session, payment.customer, notifier.RECEIPT, source="webhook", channel="email")
    elif payment.status == "pending":
        payment.status = "failed"
        notifier.send(session, payment.customer, notifier.PAYMENT_FAILED, source="webhook")
    else:
        return "already_failed"

    payment.updated_at = now()
    session.add(payment)
    session.commit()
    return payment.status
