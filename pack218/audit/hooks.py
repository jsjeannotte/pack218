"""Audit substrate implementation.

`SQLModelWithSave.save()` and `.delete_by_id()` call `record_change()` to write
one `ActionLog` row per persistent mutation, attributing it to the
request-scoped `current_actor` and the operator-supplied `current_reason`.
`ActionLog` itself is the recursion-bypass exemption — recording would be
infinite. See `AGENTS.md` for the universal-write-path convention.
"""

from contextvars import ContextVar
from datetime import datetime, date
from typing import Any, Optional, Tuple

from sqlalchemy import inspect
from sqlmodel import Session


# Request-scoped actor and reason. Set by the request boundary in app.py
# (chrome() or page handlers) and read inside SQLModelWithSave.save() during
# the audit hook. Defaults to None so unit tests and offline scripts work
# without setup.
current_actor: ContextVar[Optional[int]] = ContextVar("pack218_current_actor", default=None)
current_reason: ContextVar[Optional[str]] = ContextVar("pack218_current_reason", default=None)


class AuditError(Exception):
    """Raised when an on-behalf-of write violates the audit/authorization rules.

    Caught by the UI layer (pack218/pages/*) which displays the message via
    ui.notify(color='negative'). Distinct from generic Exception so callers
    can match on it specifically.
    """


def subject_for(instance) -> Tuple[str, Optional[int], Optional[int]]:
    """Return (entity_name, entity_id, subject_user_id) for a persistent instance.

    - User → subject is the user themselves
    - EventRegistration → subject is the registration's owner (user_id)
    - Family → no single subject; the parent panel surfaces these to all
      family members by joining entity_name='Family' AND entity_id with
      the viewer's family_id

    Returns (entity_name, entity_id, None) for any other model class so an
    unknown future entity does not silently misattribute a row to a user
    whose id happens to match the entity_id.
    """
    # Import locally to avoid an import cycle (models.py imports from this
    # module once U3 wires the save hook).
    from pack218.entities.models import User, EventRegistration, Family

    entity_name = type(instance).__name__
    entity_id = getattr(instance, "id", None)

    if isinstance(instance, User):
        return entity_name, entity_id, entity_id
    if isinstance(instance, EventRegistration):
        return entity_name, entity_id, getattr(instance, "user_id", None)
    if isinstance(instance, Family):
        return entity_name, entity_id, None
    return entity_name, entity_id, None


_SCALAR_TYPES = (str, int, float, bool, type(None))


# User fields whose value must never appear in an ActionLog row. The audit log
# records that these fields changed (so a parent can see "your email/password
# was updated by an admin") but the actual values are redacted, because the
# log is long-lived and visible to all admins. bcrypt hashes are credentials;
# email_confirmation_code is a single-use bearer token; email is PII whose
# historical values aren't useful enough to justify retaining.
_REDACTED_USER_FIELDS = frozenset({
    "hashed_password",
    "email_confirmation_code",
    "email",
})

_REDACTED_PLACEHOLDER = "<redacted>"


def _serialize_value(value: Any) -> Any:
    """Coerce a Python value into something JSON-serializable for ActionLog."""
    if isinstance(value, _SCALAR_TYPES):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _redact_if_sensitive(entity_name: str, field: str, value: Any) -> Any:
    if entity_name == "User" and field in _REDACTED_USER_FIELDS:
        return _REDACTED_PLACEHOLDER if value not in (None, "") else value
    return _serialize_value(value)


def _model_snapshot(instance) -> dict:
    """Best-effort dict-of-columns snapshot for delete actions, with sensitive
    User fields redacted."""
    insp = inspect(instance)
    entity_name = type(instance).__name__
    out = {}
    for attr in insp.mapper.column_attrs:
        out[attr.key] = _redact_if_sensitive(
            entity_name, attr.key, getattr(instance, attr.key, None)
        )
    return out


def diff_for(instance, action: str) -> dict:
    """Compose the field_changes JSON payload for an ActionLog row.

    - create: {field: [None, value]} for every column (sensitive User fields redacted)
    - update: {field: [before, after]} only for dirty COLUMNS (relationships skipped)
    - delete: {"_action": "delete", "snapshot": {column: value, ...}}
    """
    entity_name = type(instance).__name__
    if action == "delete":
        return {"_action": "delete", "snapshot": _model_snapshot(instance)}

    insp = inspect(instance)
    diff: dict = {}

    if action == "create":
        for attr in insp.mapper.column_attrs:
            if attr.key == "id":
                continue  # id is the row identity, not a "field change"
            value = getattr(instance, attr.key, None)
            diff[attr.key] = [None, _redact_if_sensitive(entity_name, attr.key, value)]
        return diff

    # update — iterate only columns (NOT relationships); relationship attrs
    # would surface stringified SQLModel objects in the JSON.
    for attr in insp.mapper.column_attrs:
        history = inspect(instance).attrs[attr.key].history
        if not history.has_changes():
            continue
        before_raw = history.deleted[0] if history.deleted else None
        after_raw = (
            history.added[0]
            if history.added
            else getattr(instance, attr.key, None)
        )
        diff[attr.key] = [
            _redact_if_sensitive(entity_name, attr.key, before_raw),
            _redact_if_sensitive(entity_name, attr.key, after_raw),
        ]
    return diff


# ---------------------------------------------------------------------------
# On-behalf-of enforcement (U3)
# ---------------------------------------------------------------------------


# Fields the user themselves owns — admins cannot change them on a user's
# behalf, even with a reason. This is enforced at the save boundary; the
# UI further surfaces the rejection. See `pack218.audit.is_self_edit` for
# what counts as "the user themselves" (includes same-family members).
BLOCKLISTED_USER_FIELDS = frozenset({
    "email",
    "username",
    "hashed_password",
    "is_admin",
    "can_login",
    "email_confirmed",
    "email_confirmation_code",
})


# A subset of the blocklist that ALSO applies at create time. These are the
# fields whose non-default value would grant elevated capability to the new
# user. The remaining blocklist members (email, username, hashed_password)
# are part of normal user setup and an admin must be able to set them when
# creating an account for someone who hasn't logged in yet (matches the
# PowerSchool admin-creates-parent pattern from the origin doc).
_CREATE_TIME_BLOCKED_FIELDS = frozenset({
    "is_admin",
    "email_confirmed",
})


_USER_SAFE_DEFAULTS_FOR_CREATE = {
    "is_admin": False,
    "email_confirmed": False,
}


def is_self_edit(session: Session, instance, actor_id: int) -> bool:
    """Self-edit semantics for the entities we audit.

    - User: same user OR same family (using the persisted family_id, not the
      possibly-being-changed in-memory value — otherwise an admin could
      reassign a user into their own family and bypass enforcement).
    - EventRegistration: actor IS the registration's owner OR they share a
      family. Direct identity match short-circuits the DB lookup so a stale
      actor_id pointing at a deleted user still classifies a save of one's
      own record as self-edit.
    - Family: actor is a member (actor.family_id == family.id).

    Wrapped in ``no_autoflush`` so the ``session.get()`` lookups don't flush
    the in-flight dirty changes on ``instance`` (which would clear the
    attribute history that ``diff_for`` relies on later in save()).
    """
    from pack218.entities.models import User, EventRegistration, Family

    # Short-circuit direct identity matches BEFORE any DB lookup. This makes
    # a parent editing their own record self-edit even if their User row has
    # been deleted between chrome() setting current_actor and save() reading
    # it — protecting against confusing "Reason is required" errors on a
    # user's own profile when the session is stale.
    if isinstance(instance, User) and instance.id == actor_id:
        return True
    if isinstance(instance, EventRegistration) and instance.user_id == actor_id:
        return True

    with session.no_autoflush:
        actor = session.get(User, actor_id)
        if actor is None:
            return False

        if isinstance(instance, User):
            # Read the PERSISTED family_id, not the (possibly being-changed)
            # in-memory value. An admin reassigning a user into their own
            # family must still be classified as on-behalf so enforcement
            # (blocklist, admin-on-admin) runs.
            insp = inspect(instance)
            fam_history = insp.attrs.family_id.history
            if fam_history.has_changes():
                persisted_family_id = (
                    fam_history.deleted[0] if fam_history.deleted else None
                )
            else:
                persisted_family_id = instance.family_id
            if actor.family_id and persisted_family_id == actor.family_id:
                return True
            return False

        if isinstance(instance, EventRegistration):
            if actor.family_id:
                subject = session.get(User, instance.user_id)
                if subject and subject.family_id == actor.family_id:
                    return True
            return False

        if isinstance(instance, Family):
            return actor.family_id == instance.id

        return False


# Back-compat alias for the private name used internally. New callers should
# import `is_self_edit` from `pack218.audit`. The underscore form is preserved
# so existing tests that imported it still pass.
_is_self_edit = is_self_edit


def _blocked_user_fields_in_change(instance, action: str) -> frozenset:
    """Return the set of blocklisted User fields this write would change."""
    from pack218.entities.models import User

    if not isinstance(instance, User):
        return frozenset()

    if action == "update":
        insp = inspect(instance)
        violations = set()
        for field in BLOCKLISTED_USER_FIELDS:
            attr = insp.attrs.get(field)
            if attr is not None and attr.history.has_changes():
                violations.add(field)
        return frozenset(violations)

    if action == "create":
        # On create, only the privilege-granting subset is blocked — admin
        # must be able to set email/username/hashed_password when bootstrapping
        # an account for a parent who hasn't logged in yet (the PowerSchool
        # admin-creates-parent pattern from the origin doc).
        violations = set()
        for field in _CREATE_TIME_BLOCKED_FIELDS:
            default = _USER_SAFE_DEFAULTS_FOR_CREATE.get(field)
            value = getattr(instance, field, default)
            if value != default:
                violations.add(field)
        return frozenset(violations)

    # action == "delete" — blocklist doesn't apply; the action itself is auditable
    return frozenset()


def _is_admin_target(session: Session, instance) -> bool:
    """True if the write targets an admin's record (User or their EventRegistration)."""
    from pack218.entities.models import User, EventRegistration

    if isinstance(instance, User):
        return bool(getattr(instance, "is_admin", False))
    if isinstance(instance, EventRegistration):
        with session.no_autoflush:
            subject = session.get(User, instance.user_id)
            return bool(subject and subject.is_admin)
    return False


def enforce_on_behalf_rules(session: Session, instance, action: str) -> None:
    """Raise AuditError if this write violates the on-behalf-of rules.

    Called from SQLModelWithSave.save() and .delete_by_id() between pre_save
    and flush. Reads current_actor / current_reason from contextvars.

    When current_actor is None (offline scripts, tests without setup), no
    rules are enforced; record_change will log the row with actor_user_id=NULL.
    """
    from pack218.entities.models import Event

    actor_id = current_actor.get()
    if actor_id is None:
        return

    # Event is shared trip metadata, not a personal record — the on-behalf-of
    # rules (reason required, blocklist, admin-on-admin) don't apply. The
    # write is still recorded in action_log so we keep the audit trail.
    if isinstance(instance, Event):
        return

    if is_self_edit(session, instance, actor_id):
        return

    # ON-BEHALF-OF write

    reason = (current_reason.get() or "").strip()
    if not reason:
        raise AuditError("Reason is required when editing another user's record")

    blocked = _blocked_user_fields_in_change(instance, action)
    if blocked:
        raise AuditError(
            "These fields can only be changed by the user themselves: "
            + ", ".join(sorted(blocked))
        )

    # Admin-on-admin: applies to User AND EventRegistration whose owner is an
    # admin. Family is excluded — multi-admin households are a real shape, and
    # the admin-on-admin policy is about acting on someone's personal record,
    # not their shared family info.
    if _is_admin_target(session, instance):
        raise AuditError("On-behalf-of edits cannot target another admin's record")


def record_change(
    session: Session,
    instance,
    action: str,
    field_changes: Optional[dict] = None,
) -> None:
    """Insert one ActionLog row for the given write.

    Does NOT flush or commit — the caller (SQLModelWithSave.save / .delete_by_id)
    owns the surrounding transaction. ActionLog instances themselves are
    skipped to prevent infinite recursion.

    ``field_changes`` may be passed pre-computed (the save() hook does this
    because it needs the diff BEFORE flush, while attribute history is still
    intact). When omitted, the diff is computed here.
    """
    from pack218.entities.models import ActionLog

    if isinstance(instance, ActionLog):
        return

    if field_changes is None:
        field_changes = diff_for(instance, action)

    entity_name, entity_id, subject_user_id = subject_for(instance)

    log = ActionLog(
        actor_user_id=current_actor.get(),
        subject_user_id=subject_user_id,
        entity_name=entity_name,
        entity_id=entity_id,
        action=action,
        field_changes=field_changes,
        reason=current_reason.get(),
    )
    session.add(log)
