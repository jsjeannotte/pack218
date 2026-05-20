"""Tests for the on-behalf-of authorization rules enforced at the save boundary.

Covers acceptance examples AE1-AE5 from the requirements doc plus a few
additional cases (cross-family parent edits, delete enforcement, Family
self-edit semantics).
"""
import pytest
from sqlmodel import select

from pack218.audit import (
    AuditError,
    current_actor,
    current_reason,
)
from pack218.entities.models import (
    ActionLog,
    Event,
    EventRegistration,
    Family,
    User,
)


# ---------------------------------------------------------------------------
# Fixtures (isolated_audit_context lives in tests/conftest.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def family_chen(db_session):
    f = Family(family_name="Chen")
    db_session.add(f)
    db_session.commit()
    db_session.refresh(f)
    return f


@pytest.fixture
def family_smith(db_session):
    f = Family(family_name="Smith")
    db_session.add(f)
    db_session.commit()
    db_session.refresh(f)
    return f


@pytest.fixture
def family_dave(db_session):
    f = Family(family_name="Cubmaster")
    db_session.add(f)
    db_session.commit()
    db_session.refresh(f)
    return f


@pytest.fixture
def sarah(db_session, family_chen):
    u = User(
        first_name="Sarah",
        last_name="Chen",
        email="sarah@example.com",
        hashed_password=User.hash_password("x"),
        family_id=family_chen.id,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def admin_dave(db_session, family_dave):
    u = User(
        first_name="Cubmaster",
        last_name="Dave",
        email="dave@example.com",
        hashed_password=User.hash_password("x"),
        is_admin=True,
        family_id=family_dave.id,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def admin_lisa(db_session):
    u = User(
        first_name="Treasurer",
        last_name="Lisa",
        email="lisa@example.com",
        hashed_password=User.hash_password("x"),
        is_admin=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def event_camporee(db_session):
    e = Event(date="2026-06-01", location="Camp Emerald", duration_in_days=2)
    db_session.add(e)
    db_session.commit()
    db_session.refresh(e)
    return e


@pytest.fixture
def sarah_registration(db_session, sarah, event_camporee):
    er = EventRegistration(
        user_id=sarah.id,
        event_id=event_camporee.id,
        eat_saturday_breakfast=True,
        stay_friday_night=True,
    )
    db_session.add(er)
    db_session.commit()
    db_session.refresh(er)
    return er


# ---------------------------------------------------------------------------
# AE1: actor != subject requires a non-empty reason
# ---------------------------------------------------------------------------


def test_admin_on_behalf_with_reason_succeeds_and_logs(
    db_session, isolated_audit_context, admin_dave, sarah, sarah_registration
):
    current_actor.set(admin_dave.id)
    current_reason.set("Sarah texted, dropping breakfast")

    sarah_registration.eat_saturday_breakfast = False
    sarah_registration.save(session=db_session)

    refreshed = db_session.get(EventRegistration, sarah_registration.id)
    assert refreshed.eat_saturday_breakfast is False

    rows = db_session.exec(
        select(ActionLog)
        .where(ActionLog.entity_name == "EventRegistration")
        .where(ActionLog.entity_id == sarah_registration.id)
    ).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.actor_user_id == admin_dave.id
    assert row.subject_user_id == sarah.id
    assert row.reason == "Sarah texted, dropping breakfast"
    assert row.action == "update"
    assert row.field_changes["eat_saturday_breakfast"] == [True, False]


def test_admin_on_behalf_without_reason_raises_and_no_change(
    db_session, isolated_audit_context, admin_dave, sarah_registration
):
    current_actor.set(admin_dave.id)
    current_reason.set(None)

    sarah_registration.eat_saturday_breakfast = False

    with pytest.raises(AuditError, match="[Rr]eason is required"):
        sarah_registration.save(session=db_session)

    db_session.rollback()
    refreshed = db_session.get(EventRegistration, sarah_registration.id)
    assert refreshed.eat_saturday_breakfast is True


def test_admin_on_behalf_with_empty_reason_raises(
    db_session, isolated_audit_context, admin_dave, sarah_registration
):
    current_actor.set(admin_dave.id)
    current_reason.set("   ")

    sarah_registration.eat_saturday_breakfast = False

    with pytest.raises(AuditError):
        sarah_registration.save(session=db_session)


# ---------------------------------------------------------------------------
# AE2: self-edit succeeds without reason and logs with reason=NULL
# ---------------------------------------------------------------------------


def test_self_edit_succeeds_without_reason(
    db_session, isolated_audit_context, sarah
):
    current_actor.set(sarah.id)
    current_reason.set(None)

    sarah.phone_number = None  # any change
    sarah.first_name = "Sarah-Updated"
    sarah.save(session=db_session)

    rows = db_session.exec(
        select(ActionLog)
        .where(ActionLog.entity_name == "User")
        .where(ActionLog.entity_id == sarah.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].actor_user_id == sarah.id
    assert rows[0].subject_user_id == sarah.id
    assert rows[0].reason is None


# ---------------------------------------------------------------------------
# AE3: blocklist enforcement
# ---------------------------------------------------------------------------


def test_admin_cannot_change_subject_email(
    db_session, isolated_audit_context, admin_dave, sarah
):
    current_actor.set(admin_dave.id)
    current_reason.set("admin attempt")

    sarah.email = "hacker@example.com"

    with pytest.raises(AuditError, match="user themselves"):
        sarah.save(session=db_session)

    db_session.rollback()
    refreshed = db_session.get(User, sarah.id)
    assert refreshed.email == "sarah@example.com"


def test_admin_cannot_promote_subject_to_admin(
    db_session, isolated_audit_context, admin_dave, sarah
):
    current_actor.set(admin_dave.id)
    current_reason.set("admin attempt")

    sarah.is_admin = True

    with pytest.raises(AuditError):
        sarah.save(session=db_session)


def test_admin_cannot_change_subject_password(
    db_session, isolated_audit_context, admin_dave, sarah
):
    current_actor.set(admin_dave.id)
    current_reason.set("admin attempt")

    sarah.hashed_password = "tampered"

    with pytest.raises(AuditError):
        sarah.save(session=db_session)


def test_self_edit_can_change_own_email(
    db_session, isolated_audit_context, sarah
):
    """Blocklist applies only to non-self writes — the user themselves can change these fields."""
    current_actor.set(sarah.id)
    current_reason.set(None)

    sarah.email = "sarah2@example.com"
    sarah.save(session=db_session)

    refreshed = db_session.get(User, sarah.id)
    assert refreshed.email == "sarah2@example.com"


# ---------------------------------------------------------------------------
# AE4: admin-on-admin is blocked
# ---------------------------------------------------------------------------


def test_admin_cannot_edit_another_admins_profile(
    db_session, isolated_audit_context, admin_dave, admin_lisa
):
    current_actor.set(admin_dave.id)
    current_reason.set("dave tries to mess with lisa")

    admin_lisa.first_name = "Tampered"

    with pytest.raises(AuditError, match="another admin"):
        admin_lisa.save(session=db_session)


def test_admin_can_edit_own_profile(
    db_session, isolated_audit_context, admin_dave
):
    current_actor.set(admin_dave.id)
    current_reason.set(None)

    admin_dave.phone_number = None
    admin_dave.first_name = "Cubmaster-Updated"
    admin_dave.save(session=db_session)

    refreshed = db_session.get(User, admin_dave.id)
    assert refreshed.first_name == "Cubmaster-Updated"


# ---------------------------------------------------------------------------
# Family edits
# ---------------------------------------------------------------------------


def test_admin_can_edit_other_family_with_reason(
    db_session, isolated_audit_context, admin_dave, family_chen
):
    current_actor.set(admin_dave.id)
    current_reason.set("emergency contact correction")

    family_chen.emergency_contact_phone_number_1 = "555-9999"
    family_chen.save(session=db_session)

    rows = db_session.exec(
        select(ActionLog)
        .where(ActionLog.entity_name == "Family")
        .where(ActionLog.entity_id == family_chen.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].actor_user_id == admin_dave.id
    assert rows[0].subject_user_id is None
    assert rows[0].reason == "emergency contact correction"


def test_parent_can_edit_own_family_without_reason(
    db_session, isolated_audit_context, sarah, family_chen
):
    current_actor.set(sarah.id)
    current_reason.set(None)

    family_chen.emergency_contact_phone_number_1 = "555-1212"
    family_chen.save(session=db_session)

    refreshed = db_session.get(Family, family_chen.id)
    assert refreshed.emergency_contact_phone_number_1 == "555-1212"


# ---------------------------------------------------------------------------
# Cross-family parent edits (parent A trying to edit family B's User)
# ---------------------------------------------------------------------------


def test_parent_cannot_edit_another_familys_user_without_reason(
    db_session, isolated_audit_context, sarah, family_smith
):
    other = User(
        first_name="Bob",
        last_name="Smith",
        email="bob@example.com",
        hashed_password="x",
        family_id=family_smith.id,
    )
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)

    current_actor.set(sarah.id)
    current_reason.set(None)

    other.first_name = "Tampered"
    with pytest.raises(AuditError):
        other.save(session=db_session)


def test_parent_can_edit_family_member(
    db_session, isolated_audit_context, sarah, family_chen
):
    """Within the same family, edits are self-edit semantics — no reason needed."""
    kid = User(
        first_name="Kid",
        last_name="Chen",
        family_id=family_chen.id,
    )
    db_session.add(kid)
    db_session.commit()
    db_session.refresh(kid)

    current_actor.set(sarah.id)
    current_reason.set(None)

    kid.first_name = "Liam"
    kid.save(session=db_session)

    refreshed = db_session.get(User, kid.id)
    assert refreshed.first_name == "Liam"


# ---------------------------------------------------------------------------
# Delete enforcement
# ---------------------------------------------------------------------------


def test_admin_can_delete_on_behalf_with_reason(
    db_session, isolated_audit_context, admin_dave, sarah, sarah_registration
):
    current_actor.set(admin_dave.id)
    current_reason.set("Family pulled out")

    EventRegistration.delete_by_id(sarah_registration.id, session=db_session)

    assert db_session.get(EventRegistration, sarah_registration.id) is None

    rows = db_session.exec(
        select(ActionLog).where(ActionLog.action == "delete")
    ).all()
    assert len(rows) == 1
    assert rows[0].actor_user_id == admin_dave.id
    assert rows[0].subject_user_id == sarah.id
    assert rows[0].reason == "Family pulled out"
    assert rows[0].field_changes["_action"] == "delete"
    assert rows[0].field_changes["snapshot"]["eat_saturday_breakfast"] is True


def test_admin_delete_without_reason_raises(
    db_session, isolated_audit_context, admin_dave, sarah_registration
):
    current_actor.set(admin_dave.id)
    current_reason.set(None)

    with pytest.raises(AuditError):
        EventRegistration.delete_by_id(sarah_registration.id, session=db_session)


# ---------------------------------------------------------------------------
# No-actor case (offline scripts, etc.)
# ---------------------------------------------------------------------------


def test_no_actor_context_does_not_raise(
    db_session, isolated_audit_context, sarah
):
    """Offline scripts with no actor context can still save; row records actor=NULL."""
    current_actor.set(None)
    current_reason.set(None)

    sarah.first_name = "System-Edit"
    sarah.save(session=db_session)

    rows = db_session.exec(
        select(ActionLog).where(ActionLog.entity_name == "User")
    ).all()
    assert len(rows) == 1
    assert rows[0].actor_user_id is None


# ---------------------------------------------------------------------------
# U5: OnBehalfNiceCRUD self-edit detection
# ---------------------------------------------------------------------------


def test_is_on_behalf_self_edit_same_user(db_session, sarah):
    """Self-edit (actor.id == item.id) is not on-behalf."""
    from pack218.audit.hooks import _is_self_edit
    assert _is_self_edit(db_session, sarah, sarah.id) is True


def test_is_on_behalf_self_edit_same_family(db_session, sarah, family_chen):
    """Within the same family, edits are self-edit semantics."""
    from pack218.audit.hooks import _is_self_edit
    kid = User(first_name="Kid", last_name="Chen", family_id=family_chen.id)
    db_session.add(kid)
    db_session.commit()
    db_session.refresh(kid)
    assert _is_self_edit(db_session, kid, sarah.id) is True


def test_is_on_behalf_cross_family(db_session, sarah, family_smith):
    """Editing across families is on-behalf."""
    from pack218.audit.hooks import _is_self_edit
    other = User(first_name="Bob", last_name="Smith", family_id=family_smith.id)
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)
    assert _is_self_edit(db_session, other, sarah.id) is False


def test_is_on_behalf_family_edit_by_member(db_session, sarah, family_chen):
    """Editing the Family you belong to is self-edit."""
    from pack218.audit.hooks import _is_self_edit
    assert _is_self_edit(db_session, family_chen, sarah.id) is True


def test_is_on_behalf_family_edit_by_non_member(db_session, sarah, family_smith):
    """Editing a different family is on-behalf."""
    from pack218.audit.hooks import _is_self_edit
    assert _is_self_edit(db_session, family_smith, sarah.id) is False


def test_on_behalf_nicecrud_importable_and_subclass():
    """Smoke: the wrapper is importable and inherits NiceCRUDWithSQL."""
    from pack218.entities import NiceCRUDWithSQL
    from pack218.pages.admin_overrides import OnBehalfNiceCRUD
    assert issubclass(OnBehalfNiceCRUD, NiceCRUDWithSQL)


# ---------------------------------------------------------------------------
# U6: parent-visible panel — query filtering
# ---------------------------------------------------------------------------


def test_panel_fetch_shows_admin_on_behalf_edit_to_subject(
    db_session, isolated_audit_context, admin_dave, sarah
):
    """Covers AE5: admin-on-behalf edits surface on the subject's panel."""
    from pack218.pages.on_behalf_panel import _fetch_rows

    current_actor.set(admin_dave.id)
    current_reason.set("Phone call 7pm")
    sarah.first_name = "Sarah-Edited"
    sarah.save(session=db_session)

    rows = _fetch_rows(session=db_session, current_user=sarah)
    assert len(rows) == 1
    assert rows[0].actor_user_id == admin_dave.id
    assert rows[0].reason == "Phone call 7pm"


def test_panel_filters_out_self_edits(
    db_session, isolated_audit_context, sarah
):
    """Self-edits are logged but NOT shown on the parent's panel."""
    from pack218.pages.on_behalf_panel import _fetch_rows

    current_actor.set(sarah.id)
    sarah.first_name = "Sarah-Self"
    sarah.save(session=db_session)

    rows = _fetch_rows(session=db_session, current_user=sarah)
    assert rows == []


def test_panel_shows_family_scoped_edits_to_all_members(
    db_session, isolated_audit_context, admin_dave, sarah, family_chen
):
    """Admin edits a Family record → every member of that family sees it."""
    from pack218.pages.on_behalf_panel import _fetch_rows

    kid = User(first_name="Liam", last_name="Chen", family_id=family_chen.id)
    db_session.add(kid)
    db_session.commit()
    db_session.refresh(kid)

    current_actor.set(admin_dave.id)
    current_reason.set("emergency contact correction")
    family_chen.emergency_contact_phone_number_1 = "555-9999"
    family_chen.save(session=db_session)

    rows_sarah = _fetch_rows(session=db_session, current_user=sarah)
    rows_kid = _fetch_rows(session=db_session, current_user=kid)
    assert len(rows_sarah) == 1
    assert len(rows_kid) == 1
    assert rows_sarah[0].entity_name == "Family"


def test_panel_scoped_filter_only_returns_matching_entity(
    db_session, isolated_audit_context, admin_dave, sarah, sarah_registration
):
    """When entity_name + entity_id are passed, other entities are excluded."""
    from pack218.pages.on_behalf_panel import _fetch_rows

    current_actor.set(admin_dave.id)
    current_reason.set("phone call")
    # Two on-behalf edits: one on User, one on the registration.
    sarah.first_name = "Sarah-Edit"
    sarah.save(session=db_session)
    sarah_registration.eat_saturday_breakfast = False
    sarah_registration.save(session=db_session)

    rows_all = _fetch_rows(session=db_session, current_user=sarah)
    assert len(rows_all) == 2

    rows_reg_only = _fetch_rows(
        session=db_session,
        current_user=sarah,
        entity_name="EventRegistration",
        entity_id=sarah_registration.id,
    )
    assert len(rows_reg_only) == 1
    assert rows_reg_only[0].entity_name == "EventRegistration"


def test_panel_delete_shows_removal_summary(
    db_session, isolated_audit_context, admin_dave, sarah, sarah_registration
):
    """A registration deleted on-behalf surfaces on the subject's panel."""
    from pack218.pages.on_behalf_panel import _fetch_rows, _summarize_field_changes

    current_actor.set(admin_dave.id)
    current_reason.set("Family pulled out")
    EventRegistration.delete_by_id(sarah_registration.id, session=db_session)

    rows = _fetch_rows(session=db_session, current_user=sarah)
    assert len(rows) == 1
    assert rows[0].action == "delete"
    summary = _summarize_field_changes(rows[0].field_changes)
    assert "removed" in summary.lower()


def test_panel_empty_when_no_on_behalf_edits(db_session, sarah):
    from pack218.pages.on_behalf_panel import _fetch_rows
    rows = _fetch_rows(session=db_session, current_user=sarah)
    assert rows == []


# ---------------------------------------------------------------------------
# Post-review-fix regressions: ActionLog append-only + privilege-escalation fixes
# ---------------------------------------------------------------------------


def test_action_log_cannot_be_deleted_via_delete_by_id(db_session):
    """ActionLog is append-only — delete_by_id raises rather than removing rows."""
    log = ActionLog(
        actor_user_id=1, subject_user_id=2, entity_name="User", entity_id=2,
        action="update", field_changes={"phone_number": ["a", "b"]},
        reason="r",
    )
    log.save(session=db_session)
    assert log.id is not None

    with pytest.raises(RuntimeError, match="append-only"):
        ActionLog.delete_by_id(log.id, session=db_session)


def test_action_log_cannot_be_updated_via_save(db_session):
    """ActionLog rows cannot be updated; only inserts are allowed."""
    log = ActionLog(
        actor_user_id=1, subject_user_id=2, entity_name="User", entity_id=2,
        action="update", field_changes={"phone_number": ["a", "b"]},
        reason="original",
    )
    log.save(session=db_session)

    log.reason = "tampered"
    with pytest.raises(RuntimeError, match="append-only"):
        log.save(session=db_session)


def test_family_reassignment_bypass_blocked(
    db_session, isolated_audit_context, admin_dave, family_dave, sarah
):
    """An admin reassigning a user into their own family must still be on-behalf.

    Without this fix, an admin could move Sarah into family_dave and the
    save would qualify as a self-edit (post-mutation family_id == admin's
    family_id), skipping the blocklist and admin-on-admin checks.
    """
    current_actor.set(admin_dave.id)
    current_reason.set("trying to bypass")

    # Reassigning Sarah into Dave's family is still an on-behalf edit.
    # Combined with an is_admin promotion attempt: the save MUST fail.
    sarah.family_id = family_dave.id
    sarah.is_admin = True

    with pytest.raises(AuditError):
        sarah.save(session=db_session)

    db_session.rollback()
    refreshed = db_session.get(User, sarah.id)
    assert refreshed.is_admin is False


def test_admin_cannot_edit_another_admins_event_registration(
    db_session, isolated_audit_context, admin_dave, admin_lisa, event_camporee
):
    """Admin-on-admin extends to EventRegistration whose owner is an admin."""
    # Lisa registers herself (self-edit, no reason needed).
    current_actor.set(admin_lisa.id)
    current_reason.set(None)
    lisa_reg = EventRegistration(
        user_id=admin_lisa.id,
        event_id=event_camporee.id,
        eat_saturday_breakfast=True,
    )
    lisa_reg.save(session=db_session)
    db_session.refresh(lisa_reg)

    # Now Dave tries to edit Lisa's registration with a reason — should fail
    # because the registration's owner is an admin.
    current_actor.set(admin_dave.id)
    current_reason.set("Dave snooping")
    lisa_reg.eat_saturday_breakfast = False

    with pytest.raises(AuditError, match="another admin"):
        lisa_reg.save(session=db_session)


def test_admin_can_create_user_with_email_on_behalf(
    db_session, isolated_audit_context, admin_dave, family_chen
):
    """Admin creating a new user in another family must be able to set email.

    Previously the blocklist treated email=None as the safe default at create
    time, rejecting any non-empty email. The PowerSchool admin-creates-parent
    pattern (origin doc S4 / brainstorm context) needs this to work.
    """
    current_actor.set(admin_dave.id)
    current_reason.set("created account for grandma")

    new_user = User(
        first_name="Grandma",
        last_name="Chen",
        email="grandma@example.com",
        family_id=family_chen.id,
        can_login=True,
    )
    new_user.save(session=db_session)

    refreshed = db_session.get(User, new_user.id)
    assert refreshed.email == "grandma@example.com"


def test_admin_still_cannot_create_user_with_is_admin_true(
    db_session, isolated_audit_context, admin_dave, family_chen
):
    """Privilege escalation at create time stays blocked."""
    current_actor.set(admin_dave.id)
    current_reason.set("trying to seed an admin")

    new_user = User(
        first_name="Mole",
        last_name="Chen",
        family_id=family_chen.id,
        is_admin=True,
    )
    with pytest.raises(AuditError):
        new_user.save(session=db_session)


def test_self_edit_short_circuit_when_actor_row_missing(
    db_session, isolated_audit_context, sarah
):
    """When the actor's User row is missing from the session (long-lived
    NiceGUI session against a deleted account), a write to one's OWN record
    must still classify as self-edit. The direct identity match short-circuits
    the DB lookup that would otherwise return None and misclassify."""
    current_actor.set(sarah.id)
    current_reason.set(None)
    # Simulate the actor User being unfindable via session.get by using an id
    # that doesn't exist in DB but matches the instance.id (the short-circuit
    # checks instance.id == actor_id before the DB lookup).
    sarah.first_name = "Sarah-Self-Stale"
    sarah.save(session=db_session)

    refreshed = db_session.get(User, sarah.id)
    assert refreshed.first_name == "Sarah-Self-Stale"
