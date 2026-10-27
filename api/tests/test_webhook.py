from conftest import callback, emails


def test_approved_callback_marks_payment_paid(client, session, payment):
    callback(client, payment, "1", "3")
    session.refresh(payment)
    assert payment.status == "paid"


def test_non_approved_callback_marks_payment_failed(client, session, payment):
    callback(client, payment, "failure", "9")
    session.refresh(payment)
    assert payment.status == "failed"


def test_approval_after_failure_marks_paid_and_sends_receipt(client, session, payment):
    payment.status = "failed"
    session.add(payment)
    session.commit()

    callback(client, payment, "1", "3")

    session.refresh(payment)
    assert payment.status == "paid"
    assert emails(session) == ["Receipt: your payment was approved."]
