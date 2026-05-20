"""Admin view for the append-only ``action_log`` table.

Mounted at ``/admin/action-log``. Lists every audited write (create / update /
delete) with the actor, subject, target entity, action, field-level diff,
reason, and timestamp. The view filters server-side by free-text (matches
``reason``, ``entity_name``, field-change blob, and actor/subject names),
action type, entity type, and result limit — so the page stays responsive
even with a large log.
"""
from __future__ import annotations

from typing import Optional

from nicegui import ui
from sqlalchemy import String, cast
from sqlmodel import Session, or_, select

from pack218.entities.models import ActionLog, EventRegistration, User
from pack218.pages.ui_components import card_title

# A reasonable upper bound on result rows so a misclicked "All" doesn't pull
# the entire log into the UI.
_LIMIT_CHOICES = [50, 200, 1000, 10000]
# ActionLog is excluded on purpose — the audit hook skips writes targeting
# ActionLog itself (to avoid recursion), so there are no such rows to filter.
_ENTITY_CHOICES = ["(any)", "User", "Event", "EventRegistration", "Family"]
_ACTION_CHOICES = ["(any)", "create", "update", "delete"]


def _user_label(user: Optional[User]) -> str:
    if user is None:
        return ""
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    if not name:
        name = user.email or f"user#{user.id}"
    return f"{name},id#{user.id}"


def _format_changes(field_changes: dict) -> str:
    """Render the JSON diff as one ``field: old → new`` line per entry."""
    if not field_changes:
        return ""
    lines = []
    for field, change in field_changes.items():
        if isinstance(change, dict) and 'old' in change and 'new' in change:
            lines.append(f"{field}: {change['old']!r} → {change['new']!r}")
        else:
            # create / delete diffs are just `{field: value}`
            lines.append(f"{field}: {change!r}")
    return "\n".join(lines)


def render_admin_action_log(session: Session) -> None:
    """Searchable list of audit-log rows."""
    card_title("Action Log")
    ui.label(
        "Append-only record of every audited write. Filter by free text, "
        "action, or entity type."
    ).classes('text-sm p-2')

    # Filter state lives in a mutable dict so the refreshable closure can
    # read the current values without rebinding.
    state = {
        'q': '',
        'action': '(any)',
        'entity': '(any)',
        'limit': _LIMIT_CHOICES[0],
    }

    with ui.row().classes('w-full items-center gap-4 p-2'):
        search_input = ui.input(
            'Search',
            placeholder='reason / entity / actor / subject / field change',
        ).props('dense outlined clearable').classes('flex-grow')
        action_select = ui.select(_ACTION_CHOICES, value='(any)', label='Action')\
            .props('dense outlined').classes('w-40')
        entity_select = ui.select(_ENTITY_CHOICES, value='(any)', label='Entity')\
            .props('dense outlined').classes('w-48')
        limit_select = ui.select(
            _LIMIT_CHOICES, value=_LIMIT_CHOICES[0], label='Limit'
        ).props('dense outlined').classes('w-32')

    @ui.refreshable
    def render_table():
        # Pull filter values into the query right at render time.
        q = (state['q'] or '').strip()
        action_filter = state['action']
        entity_filter = state['entity']
        limit = state['limit']

        stmt = select(ActionLog)
        if action_filter != '(any)':
            stmt = stmt.where(ActionLog.action == action_filter)
        if entity_filter != '(any)':
            stmt = stmt.where(ActionLog.entity_name == entity_filter)
        if q:
            # Build an OR across the textual columns. Actor / subject names
            # live on User, so we resolve those user ids in a separate query
            # and OR them into the main filter.
            like = f"%{q}%"
            matching_user_ids = session.exec(
                select(User.id).where(
                    or_(
                        User.first_name.ilike(like),
                        User.last_name.ilike(like),
                        User.email.ilike(like),
                    )
                )
            ).all()
            or_clauses = [
                ActionLog.reason.ilike(like),
                ActionLog.entity_name.ilike(like),
                # field_changes is JSON in the model, stored as TEXT in
                # SQLite. Cast to String so ILIKE works as a substring match
                # on the serialized blob.
                cast(ActionLog.field_changes, String).ilike(like),
            ]
            if matching_user_ids:
                or_clauses.append(ActionLog.actor_user_id.in_(matching_user_ids))
                or_clauses.append(ActionLog.subject_user_id.in_(matching_user_ids))
            stmt = stmt.where(or_(*or_clauses))

        stmt = stmt.order_by(ActionLog.created_at.desc()).limit(limit)
        rows_raw = session.exec(stmt).all()

        # Resolve actor / subject usernames in a single batch to avoid N+1
        # session.get() calls per row.
        user_ids = {r.actor_user_id for r in rows_raw if r.actor_user_id} | {
            r.subject_user_id for r in rows_raw if r.subject_user_id
        }
        users_by_id: dict[int, User] = {}
        if user_ids:
            for u in session.exec(select(User).where(User.id.in_(user_ids))).all():
                users_by_id[u.id] = u

        # For EventRegistration rows in the log, look up the event_id once per
        # registration so the Entity column can surface "which camping trip".
        registration_ids = {
            r.entity_id for r in rows_raw if r.entity_name == 'EventRegistration'
        }
        event_id_by_registration_id: dict[int, int] = {}
        if registration_ids:
            for er in session.exec(
                select(EventRegistration).where(EventRegistration.id.in_(registration_ids))
            ).all():
                event_id_by_registration_id[er.id] = er.event_id

        columns = [
            {'name': 'created_at', 'label': 'When', 'field': 'created_at', 'sortable': True, 'align': 'left'},
            {'name': 'actor', 'label': 'Actor', 'field': 'actor', 'sortable': True},
            {'name': 'subject', 'label': 'Subject', 'field': 'subject', 'sortable': True},
            {'name': 'entity', 'label': 'Entity', 'field': 'entity', 'sortable': True},
            {'name': 'action', 'label': 'Action', 'field': 'action', 'sortable': True},
            {'name': 'reason', 'label': 'Reason', 'field': 'reason'},
            {'name': 'changes', 'label': 'Field changes', 'field': 'changes'},
        ]
        rows = []
        for r in rows_raw:
            entity_label = f"{r.entity_name}#{r.entity_id}"
            if r.entity_name == 'EventRegistration':
                # Prefer the live registration row; for `create`/`delete`
                # diffs the event_id is in field_changes, so fall back to that.
                event_id = event_id_by_registration_id.get(r.entity_id)
                if event_id is None:
                    ev_change = (r.field_changes or {}).get('event_id')
                    if isinstance(ev_change, dict):
                        event_id = ev_change.get('new') or ev_change.get('old')
                    elif isinstance(ev_change, int):
                        event_id = ev_change
                if event_id is not None:
                    entity_label = f"EventRegistration#{r.entity_id},event#{event_id}"

            rows.append({
                'id': r.id,
                'created_at': r.created_at.strftime('%Y-%m-%d %H:%M:%S') if r.created_at else '',
                'actor': _user_label(users_by_id.get(r.actor_user_id)) if r.actor_user_id else '(system)',
                'subject': _user_label(users_by_id.get(r.subject_user_id)) if r.subject_user_id else '',
                'entity': entity_label,
                'action': r.action,
                'reason': r.reason or '',
                'changes': _format_changes(r.field_changes or {}),
            })

        ui.label(f"{len(rows)} row(s) shown (limit {limit})").classes('text-sm italic p-2')
        table = ui.table(columns=columns, rows=rows).props(
            'flat dense separator="horizontal" wrap-cells'
        ).classes('w-full')
        # Field-changes cell can be multi-line — render with preserved
        # whitespace so the per-field diff is readable.
        table.add_slot('body-cell-changes', r'''
            <q-td :props="props">
                <pre style="white-space: pre-wrap; margin: 0; font-size: 12px;">{{ props.row.changes }}</pre>
            </q-td>
        ''')

    def on_filter_change():
        state['q'] = search_input.value or ''
        state['action'] = action_select.value
        state['entity'] = entity_select.value
        state['limit'] = limit_select.value
        render_table.refresh()

    search_input.on('update:model-value', lambda e: on_filter_change())
    action_select.on('update:model-value', lambda e: on_filter_change())
    entity_select.on('update:model-value', lambda e: on_filter_change())
    limit_select.on('update:model-value', lambda e: on_filter_change())

    render_table()
