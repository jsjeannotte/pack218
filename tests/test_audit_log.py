from datetime import datetime

import pytest
from sqlmodel import select

from pack218.audit import (
    AuditError,
    current_actor,
    current_reason,
    diff_for,
    record_change,
    subject_for,
)
from pack218.entities.models import ActionLog, EventRegistration, Family, User


@pytest.fixture
def parent_user(db_session):
    user = User(
        first_name="Sarah",
        last_name="Chen",
        email="sarah@example.com",
        hashed_password=User.hash_password("x"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session):
    user = User(
        first_name="Cubmaster",
        last_name="Dave",
        email="dave@example.com",
        hashed_password=User.hash_password("x"),
        is_admin=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_action_log_persists_with_all_fields(db_session):
    log = ActionLog(
        actor_user_id=1,
        subject_user_id=2,
        entity_name="EventRegistration",
        entity_id=42,
        action="update",
        field_changes={"eat_saturday_breakfast": [True, False]},
        reason="Sarah texted",
    )
    log.save(session=db_session)

    rows = db_session.exec(select(ActionLog)).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.actor_user_id == 1
    assert row.subject_user_id == 2
    assert row.entity_name == "EventRegistration"
    assert row.entity_id == 42
    assert row.action == "update"
    assert row.field_changes == {"eat_saturday_breakfast": [True, False]}
    assert row.reason == "Sarah texted"
    assert isinstance(row.created_at, datetime)


def test_action_log_supports_family_scoped_null_subject(db_session):
    log = ActionLog(
        actor_user_id=1,
        subject_user_id=None,
        entity_name="Family",
        entity_id=7,
        action="update",
        field_changes={"emergency_contact_phone_number_1": ["555-old", "555-new"]},
        reason="Mom updated her number",
    )
    log.save(session=db_session)

    rows = db_session.exec(
        select(ActionLog).where(ActionLog.entity_name == "Family", ActionLog.entity_id == 7)
    ).all()
    assert len(rows) == 1
    assert rows[0].subject_user_id is None


def test_action_log_self_edit_has_null_reason(db_session):
    log = ActionLog(
        actor_user_id=3,
        subject_user_id=3,
        entity_name="User",
        entity_id=3,
        action="update",
        field_changes={"phone_number": ["111", "222"]},
        reason=None,
    )
    log.save(session=db_session)

    rows = db_session.exec(select(ActionLog)).all()
    assert len(rows) == 1
    assert rows[0].reason is None


def test_action_log_empty_diff_still_inserts(db_session):
    log = ActionLog(
        actor_user_id=1,
        subject_user_id=1,
        entity_name="User",
        entity_id=1,
        action="update",
        field_changes={},
    )
    log.save(session=db_session)

    rows = db_session.exec(select(ActionLog)).all()
    assert len(rows) == 1
    assert rows[0].field_changes == {}


def test_action_log_delete_snapshot(db_session):
    log = ActionLog(
        actor_user_id=1,
        subject_user_id=2,
        entity_name="EventRegistration",
        entity_id=99,
        action="delete",
        field_changes={
            "_action": "delete",
            "snapshot": {"eat_saturday_breakfast": True, "stay_friday_night": False},
        },
        reason="Family pulled out",
    )
    log.save(session=db_session)

    rows = db_session.exec(select(ActionLog)).all()
    assert len(rows) == 1
    assert rows[0].action == "delete"
    assert rows[0].field_changes["_action"] == "delete"
    assert rows[0].field_changes["snapshot"]["eat_saturday_breakfast"] is True


def test_action_log_indexed_query_by_subject(db_session):
    """The (subject_user_id, created_at) index supports the parent panel query."""
    db_session.add(ActionLog(
        actor_user_id=1, subject_user_id=2, entity_name="User", entity_id=2,
        action="update", field_changes={"phone_number": ["a", "b"]},
        reason="r1",
    ))
    db_session.add(ActionLog(
        actor_user_id=1, subject_user_id=3, entity_name="User", entity_id=3,
        action="update", field_changes={"phone_number": ["c", "d"]},
        reason="r2",
    ))
    db_session.commit()

    rows_for_2 = db_session.exec(
        select(ActionLog).where(ActionLog.subject_user_id == 2)
    ).all()
    assert len(rows_for_2) == 1
    assert rows_for_2[0].reason == "r1"


# ---------------------------------------------------------------------------
# U2: subject_for, diff_for, record_change, contextvars
# ---------------------------------------------------------------------------


def test_subject_for_user_uses_self_id(parent_user):
    entity_name, entity_id, subject_user_id = subject_for(parent_user)
    assert entity_name == "User"
    assert entity_id == parent_user.id
    assert subject_user_id == parent_user.id


def test_subject_for_event_registration_uses_user_id(db_session, parent_user):
    event = __import__("pack218.entities.models", fromlist=["Event"]).Event(
        date="2026-06-01", location="Camp Emerald", duration_in_days=2,
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    er = EventRegistration(user_id=parent_user.id, event_id=event.id, eat_saturday_breakfast=True)
    db_session.add(er)
    db_session.commit()
    db_session.refresh(er)

    entity_name, entity_id, subject_user_id = subject_for(er)
    assert entity_name == "EventRegistration"
    assert entity_id == er.id
    assert subject_user_id == parent_user.id


def test_subject_for_family_has_null_subject(db_session):
    family = Family(family_name="Chen")
    db_session.add(family)
    db_session.commit()
    db_session.refresh(family)

    entity_name, entity_id, subject_user_id = subject_for(family)
    assert entity_name == "Family"
    assert entity_id == family.id
    assert subject_user_id is None


def test_diff_for_create_returns_per_field_with_null_before(db_session):
    user = User(
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
        hashed_password="x",
    )
    db_session.add(user)
    db_session.flush()

    diff = diff_for(user, "create")
    assert "id" not in diff  # id is the row identity, not a field change
    assert diff["first_name"] == [None, "Ada"]
    assert diff["last_name"] == [None, "Lovelace"]
    # Sensitive User columns are redacted in the audit log.
    assert diff["email"] == [None, "<redacted>"]
    assert diff["hashed_password"] == [None, "<redacted>"]


def test_diff_for_update_captures_only_dirty_fields(db_session, parent_user):
    parent_user.first_name = "Sarah-Updated"
    diff = diff_for(parent_user, "update")
    assert diff["first_name"] == ["Sarah", "Sarah-Updated"]
    # Untouched fields don't appear
    assert "last_name" not in diff
    assert "email" not in diff


def test_diff_for_update_redacts_sensitive_user_fields(db_session, parent_user):
    """Email and password changes are recorded as redacted in the audit log."""
    parent_user.email = "newsarah@example.com"
    parent_user.hashed_password = "new_bcrypt_hash"
    diff = diff_for(parent_user, "update")
    assert diff["email"] == ["<redacted>", "<redacted>"]
    assert diff["hashed_password"] == ["<redacted>", "<redacted>"]


def test_diff_for_update_skips_relationship_attrs(db_session, parent_user):
    """User.family is a relationship — must not appear in field_changes."""
    parent_user.first_name = "Sarah-Edit"
    diff = diff_for(parent_user, "update")
    assert "family" not in diff
    assert "family_members" not in diff


def test_diff_for_delete_returns_snapshot(parent_user):
    diff = diff_for(parent_user, "delete")
    assert diff["_action"] == "delete"
    snapshot = diff["snapshot"]
    assert snapshot["first_name"] == "Sarah"
    # Sensitive User columns are redacted even in delete snapshots.
    assert snapshot["email"] == "<redacted>"
    assert snapshot["hashed_password"] == "<redacted>"


def test_record_change_inserts_with_actor_and_reason(
    db_session, isolated_audit_context, admin_user, parent_user
):
    current_actor.set(admin_user.id)
    current_reason.set("Sarah texted at 7pm")
    parent_user.phone_number = None  # mark something dirty
    parent_user.first_name = "Sarah-2"

    record_change(db_session, parent_user, "update")
    db_session.commit()

    rows = db_session.exec(select(ActionLog).where(ActionLog.entity_name == "User")).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.actor_user_id == admin_user.id
    assert row.subject_user_id == parent_user.id
    assert row.reason == "Sarah texted at 7pm"
    assert row.action == "update"
    assert row.field_changes["first_name"] == ["Sarah", "Sarah-2"]


def test_record_change_skips_action_log_itself(db_session, isolated_audit_context):
    """Recursion guard: saving an ActionLog must not record a meta-audit row."""
    log = ActionLog(
        actor_user_id=1,
        subject_user_id=1,
        entity_name="User",
        entity_id=1,
        action="update",
        field_changes={"phone_number": ["a", "b"]},
    )
    db_session.add(log)
    db_session.flush()

    record_change(db_session, log, "create")
    db_session.commit()

    rows = db_session.exec(select(ActionLog)).all()
    # Only the original log row exists; no meta-audit row was added.
    assert len(rows) == 1


def test_record_change_self_edit_records_null_reason(
    db_session, isolated_audit_context, parent_user
):
    current_actor.set(parent_user.id)
    current_reason.set(None)
    parent_user.first_name = "Sarah-Self"

    record_change(db_session, parent_user, "update")
    db_session.commit()

    rows = db_session.exec(select(ActionLog).where(ActionLog.entity_name == "User")).all()
    assert len(rows) == 1
    assert rows[0].actor_user_id == parent_user.id
    assert rows[0].subject_user_id == parent_user.id
    assert rows[0].reason is None


def test_record_change_no_actor_falls_through_with_null(
    db_session, isolated_audit_context, parent_user
):
    """Offline scripts / system-level writes record actor=NULL; never raises here."""
    current_actor.set(None)
    parent_user.first_name = "System-Edit"

    record_change(db_session, parent_user, "update")
    db_session.commit()

    rows = db_session.exec(select(ActionLog).where(ActionLog.entity_name == "User")).all()
    assert len(rows) == 1
    assert rows[0].actor_user_id is None


def test_contextvars_isolation():
    """Two distinct Context.run() invocations see independent actor values."""
    import contextvars

    def in_ctx_a():
        current_actor.set(1)
        return current_actor.get()

    def in_ctx_b():
        current_actor.set(2)
        return current_actor.get()

    ctx_a = contextvars.copy_context()
    ctx_b = contextvars.copy_context()
    a = ctx_a.run(in_ctx_a)
    b = ctx_b.run(in_ctx_b)
    assert a == 1
    assert b == 2
    # And no leakage into the outer context:
    assert current_actor.get() is None
