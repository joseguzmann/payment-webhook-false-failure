from conftest import callback


def test_approved_callback_marks_payment_paid(client, session, payment):
    callback(client, payment, "1", "3")
    session.refresh(payment)
    assert payment.status == "paid"


def test_non_approved_callback_marks_payment_failed(client, session, payment):
    callback(client, payment, "failure", "9")
    session.refresh(payment)
    assert payment.status == "failed"
