from sqlmodel import select

from pack218.audit import current_actor, current_reason
from pack218.entities.models import (
    ActionLog,
    Event,
    EventRegistration,
    Family,
    FamilyEventPayment,
    User,
)


def _save(session, instance):
    session.add(instance)
    session.commit()
    session.refresh(instance)
    return instance


def test_event_payment_summary_uses_family_registration_costs(db_session):
    family_one = _save(db_session, Family(family_name="One"))
    family_two = _save(db_session, Family(family_name="Two"))
    user_one = _save(
        db_session,
        User(first_name="A", last_name="One", family_id=family_one.id),
    )
    user_two = _save(
        db_session,
        User(first_name="B", last_name="Two", family_id=family_two.id),
    )
    event = _save(db_session, Event(location="Camp"))
    _save(
        db_session,
        EventRegistration(
            user_id=user_one.id,
            event_id=event.id,
            eat_saturday_breakfast=True,
            eat_saturday_lunch=True,
        ),
    )
    _save(
        db_session,
        EventRegistration(
            user_id=user_two.id,
            event_id=event.id,
            eat_saturday_dinner=True,
        ),
    )
    _save(
        db_session,
        FamilyEventPayment(
            event_id=event.id, family_id=family_one.id, is_paid=True
        ),
    )

    summary = event.get_payment_summary(session=db_session)

    assert summary["families"] == 2
    assert summary["families_paid"] == 1
    assert summary["expected"] == 15
    assert summary["paid"] == 10
    assert summary["remaining"] == 5


def test_paid_and_unpaid_transitions_are_audited(
    db_session, isolated_audit_context
):
    admin_family = _save(db_session, Family(family_name="Admin"))
    paying_family = _save(db_session, Family(family_name="Paying"))
    admin = _save(
        db_session,
        User(
            first_name="Ada",
            last_name="Admin",
            family_id=admin_family.id,
            is_admin=True,
        ),
    )
    event = _save(db_session, Event(location="Camp"))

    actor_token = current_actor.set(admin.id)
    reason_token = current_reason.set("Check received")
    try:
        payment = FamilyEventPayment(
            event_id=event.id, family_id=paying_family.id, is_paid=True
        )
        payment.save(session=db_session)
        current_reason.set("Corrected accidental payment entry")
        payment.is_paid = False
        payment.save(session=db_session)
    finally:
        current_reason.reset(reason_token)
        current_actor.reset(actor_token)

    rows = list(
        db_session.exec(
            select(ActionLog)
            .where(ActionLog.entity_name == "FamilyEventPayment")
            .order_by(ActionLog.id)
        ).all()
    )
    assert len(rows) == 2
    assert rows[0].field_changes["is_paid"] == [None, True]
    assert rows[0].reason == "Check received"
    assert rows[1].field_changes["is_paid"] == [True, False]
    assert rows[1].field_changes["event_id"] == [event.id, event.id]
    assert rows[1].field_changes["family_id"] == [paying_family.id, paying_family.id]
    assert rows[1].field_changes["family_name"] == ["Paying", "Paying"]
    assert rows[1].reason == "Corrected accidental payment entry"
