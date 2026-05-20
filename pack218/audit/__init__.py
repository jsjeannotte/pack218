"""Audit substrate for pack218.

Hooked into ``SQLModelWithSave.save()`` and ``SQLModelWithSave.delete_by_id()``
so every write produces one ``ActionLog`` row. Actor and reason are carried
via request-scoped ``contextvars`` set by the request boundary in
``pack218/app.py``; reads inside the save hook do not require any signature
changes to existing call sites.

Self-edits (``actor == subject``) get ``reason = NULL`` and are logged but
filtered out by the parent-visible panel. Non-self edits without a reason
raise ``AuditError`` — enforcement lives in U3 (`pack218.audit.rules`).
"""

from pack218.audit.hooks import (  # noqa: F401
    AuditError,
    BLOCKLISTED_USER_FIELDS,
    current_actor,
    current_reason,
    diff_for,
    enforce_on_behalf_rules,
    is_self_edit,
    record_change,
    subject_for,
)


def set_actor_from_request(request, session=None) -> None:
    """Re-bind ``current_actor`` for the current task.

    NiceGUI event handlers (``on_click`` etc.) execute in a different async
    task from the original GET request, so the ContextVar that ``chrome()``
    sets during page render does not propagate. Write handlers must call
    this helper before invoking ``.save()`` / ``.delete_by_id()`` so the
    audit row gets ``actor_user_id`` populated correctly.
    """
    from pack218.entities.models import User
    user = User.get_current(request=request, session=session)
    current_actor.set(user.id if user is not None else None)
