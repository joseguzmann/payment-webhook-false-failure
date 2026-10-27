from conftest import callback, emails, whatsapp


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


def test_in_review_then_approved_customer_only_sees_success(client, session, payment):
    """The callbacks seen in production: in review (0/36), then the approval about 49 s later."""
    callback(client, payment, "0", "36")
    callback(client, payment, "1", "3")

    session.refresh(payment)
    assert payment.status == "paid"
    assert whatsapp(session) == ["✅ Payment received. Thank you, your order is confirmed."]


def test_in_review_callback_changes_nothing(client, session, payment):
    assert callback(client, payment, "0", "36").json() == {"result": "in_review"}

    session.refresh(payment)
    assert payment.status == "pending"
    assert whatsapp(session) == []


def test_malformed_callback_is_logged_with_its_body(client, caplog):
    response = client.post("/webhooks/paylink", json={"tx": {"status": "1"}})

    assert response.status_code == 400
    assert "malformed callback" in caplog.text and "'tx'" in caplog.text


def test_expired_link_is_not_a_failure(client, session, payment):
    """Found through the new logs: an unpaid link that expired arrived as 5/14."""
    callback(client, payment, "5", "14")

    session.refresh(payment)
    assert payment.status == "expired"
    assert whatsapp(session) == []


def test_declined_payment_still_tells_the_customer(client, session, payment):
    callback(client, payment, "failure", "9")

    session.refresh(payment)
    assert payment.status == "failed"
    assert whatsapp(session) == ["❌ We could not process your payment. Please try again."]


def test_unknown_code_is_ignored_and_logged_raw(client, session, payment, caplog):
    """The accepted cost: an unknown code changes nothing, even if it was a real decline."""
    assert callback(client, payment, "7", "99").json() == {"result": "ignored"}

    session.refresh(payment)
    assert payment.status == "pending"
    assert whatsapp(session) == []
    assert "unhandled status" in caplog.text and "'status': '7'" in caplog.text


def test_expired_payment_is_not_reopened_by_a_late_decline(client, session, payment):
    callback(client, payment, "5", "14")
    callback(client, payment, "failure", "9")

    session.refresh(payment)
    assert payment.status == "expired"
    assert whatsapp(session) == []
