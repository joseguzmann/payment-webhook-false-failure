"""PayLink webhook: turns a gateway callback into a payment status and a message to the customer.

Callback body: {"transaction": {"id", "status", "status_detail", "dev_reference"}}, where
dev_reference is our payment id.

The gateway documents success, failure and pending, but in production it sends numeric codes,
and we never got the full table. So the handler acts only on codes it knows. Anything else is
logged raw and ignored: a missing failure message makes the customer ask, a false one makes
them think they lost money.
"""

import logging

from sqlmodel import Session

from . import notifier
from .models import Payment, now

log = logging.getLogger("paylink.webhook")

APPROVED = "1"
DECLINED = "failure"
EXPIRED = "5"
# Sent while the gateway's anti-fraud check runs. The final answer comes in a later callback.
IN_REVIEW = ("0", "36")


def handle_callback(session: Session, payload: dict) -> str:
    tx = payload["transaction"]
    status, detail = tx["status"], tx["status_detail"]
    payment = session.get(Payment, int(tx["dev_reference"]))
    if payment is None:
        log.warning("callback for unknown payment raw=%s", payload)
        return "unknown_payment"
    if payment.status == "paid":
        log.info("callback after paid, ignored payment=%s raw=%s", payment.id, payload)
        return "already_paid"
    if (status, detail) == IN_REVIEW:
        log.info("in review, waiting for the final callback payment=%s", payment.id)
        return "in_review"

    if status == APPROVED:
        # A later approval wins over an earlier failure: the gateway can change its mind.
        payment.status = "paid"
        notifier.send(session, payment.customer, notifier.PAYMENT_OK, source="webhook")
        notifier.send(session, payment.customer, notifier.RECEIPT, source="webhook", channel="email")
    elif payment.status != "pending":
        log.info("callback after %s, ignored payment=%s raw=%s", payment.status, payment.id, payload)
        return f"already_{payment.status}"
    elif status == DECLINED:
        payment.status = "failed"
        notifier.send(session, payment.customer, notifier.PAYMENT_FAILED, source="webhook")
    elif status == EXPIRED:
        # The customer never paid. Closing the payment is enough; nothing to tell them.
        payment.status = "expired"
    else:
        log.warning("unhandled status, ignored payment=%s raw=%s", payment.id, payload)
        return "ignored"

    payment.updated_at = now()
    session.add(payment)
    session.commit()
    log.info("payment %s -> %s status=%s detail=%s", payment.id, payment.status, status, detail)
    return payment.status
