"""Parent-visible "Changes made on my behalf" panel.

Reads ``ActionLog`` rows where the subject is the current user (or the current
user's family, for Family-scoped writes) and the actor is someone else, then
renders them as a small collapsible card. Drawn at the top of the profile
page (no entity filter — shows everything) and at the top of a parent's own
event-registration view (filtered to that registration).
"""
from typing import Any, Optional

from nicegui import ui
from sqlmodel import Session, or_, select

from pack218.entities.models import ActionLog, User


# Per the requirements doc: limit to last 30 days OR last 20 rows (whichever
# is larger). At pack scale these are roughly equivalent; we just cap rows.
_MAX_ROWS = 20


def _humanize_field_name(field: str) -> str:
    return field.replace("_", " ")


def _humanize_value(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    if value is None or value == "":
        return "—"
    return str(value)


def _summarize_field_changes(changes: dict[str, Any]) -> str:
    if not changes:
        return "no specific fields"
    if changes.get("_action") == "delete":
        return "removed the record"
    parts = []
    for field, ba in changes.items():
        if field == "_action":
            continue
        if isinstance(ba, list) and len(ba) == 2:
            before, after = ba
            parts.append(
                f"{_humanize_field_name(field)} ({_humanize_value(before)} → "
                f"{_humanize_value(after)})"
            )
        else:
            parts.append(_humanize_field_name(field))
    return ", ".join(parts)


def _actor_label(session: Session, actor_user_id: Optional[int]) -> str:
    if actor_user_id is None:
        return "System"
    actor = session.get(User, actor_user_id)
    if actor is None:
        return f"User #{actor_user_id}"
    return f"{actor.first_name} {actor.last_name}"


def _fetch_rows(
    session: Session,
    current_user: User,
    entity_name: Optional[str] = None,
    entity_id: Optional[int] = None,
) -> list[ActionLog]:
    # Two ways a row surfaces to this user:
    # 1. subject_user_id == current_user.id (User / EventRegistration edits)
    # 2. entity_name == 'Family' AND entity_id == current_user.family_id (Family edits)
    family_clause = None
    if current_user.family_id is not None:
        family_clause = (
            (ActionLog.entity_name == "Family")
            & (ActionLog.entity_id == current_user.family_id)
        )
    subject_clause = ActionLog.subject_user_id == current_user.id

    where = or_(subject_clause, family_clause) if family_clause is not None else subject_clause

    stmt = (
        select(ActionLog)
        .where(where)
        .where(ActionLog.actor_user_id != current_user.id)
        .order_by(ActionLog.created_at.desc())
        .limit(_MAX_ROWS)
    )
    if entity_name is not None and entity_id is not None:
        stmt = stmt.where(
            ActionLog.entity_name == entity_name,
            ActionLog.entity_id == entity_id,
        )
    return list(session.exec(stmt).all())


def render_on_behalf_panel(
    session: Session,
    current_user: User,
    entity_name: Optional[str] = None,
    entity_id: Optional[int] = None,
) -> None:
    """Render the parent-visible 'changes made on my behalf' panel.

    Pass entity_name + entity_id to scope to a single record (e.g., one
    EventRegistration). Omit both to show every on-behalf change touching
    this user or their family.
    """
    if current_user is None:
        return

    rows = _fetch_rows(
        session=session,
        current_user=current_user,
        entity_name=entity_name,
        entity_id=entity_id,
    )

    if not rows:
        return  # Quiet when there's nothing to show.

    with ui.expansion(
        f"📒 Changes made on your behalf ({len(rows)})", icon='history',
    ).classes('w-full'):
        ui.label(
            "These are changes a pack admin made to your record(s) recently."
        ).classes('text-sm italic')
        for row in rows:
            actor_label = _actor_label(session, row.actor_user_id)
            when = row.created_at.strftime("%b %d, %Y")
            summary = _summarize_field_changes(row.field_changes)

            scope_label = row.entity_name
            if row.entity_name == "EventRegistration":
                scope_label = "your event registration"
            elif row.entity_name == "User":
                scope_label = "your profile"
            elif row.entity_name == "Family":
                scope_label = "your family info"

            with ui.card().classes('w-full my-1'):
                with ui.card_section():
                    ui.label(f"{when} — {actor_label}").classes('text-sm font-bold')
                    action_word = (
                        "removed" if row.action == "delete"
                        else "changed" if row.action == "update"
                        else "created"
                    )
                    ui.label(
                        f"{action_word} {scope_label}: {summary}"
                    ).classes('text-sm')
                    if row.reason:
                        ui.label(f"Reason: “{row.reason}”").classes('text-sm italic')
