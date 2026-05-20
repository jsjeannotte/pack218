import logging

from nicegui import ui

from pack218.audit import AuditError, current_reason, set_actor_from_request
from pack218.entities.models import Event, EventRegistration, Family, User
from pack218.pages.ui_components import (
    BUTTON_CLASSES_ACCEPT,
    BUTTON_CLASSES_CANCEL,
    simple_dialog,
    table_export_buttons,
)
from pack218.pages.utils import SessionDep
from starlette.requests import Request

logger = logging.getLogger(__name__)


def render_participants_table(event: Event, request: Request, session: SessionDep):

    registrations = event.get_registrations(session=session)
    waitlist_status = EventRegistration.compute_waitlist_status(session=session, event_id=event.id)

    # participants = event.get_participants(session=session)
    with ui.expansion(f'Participants ({len(registrations)})', icon='expand_more').classes('w-full bg-grey-2'):
        # Generate the list of participants

        is_admin = User.acting_is_admin(request=request, session=session)
        if is_admin:
            cols = ["Family", "Participant", "Cost", "Allergies", "Email", "Phone"]
        else:
            cols = ["Family", "Participant", "Cost"]


        # Participants table
        table_columns = [
            {'name': 'family', 'label': 'Family', 'field': 'family', 'sortable': True},
            {'name': 'participant', 'label': 'Participant', 'field': 'participant', 'sortable': True},
            {'name': 'cost', 'label': 'Cost', 'field': 'cost', 'sortable': True, 'align': 'right'},
            {'name': 'registration_ts', 'label': 'Registration Date', 'field': 'registration_ts', 'sortable': True},
            {'name': 'waitlisted', 'label': 'Waitlisted', 'field': 'waitlisted', 'sortable': True},
        ]
        if is_admin:
            table_columns.extend([
                {'name': 'allergies', 'label': 'Allergies', 'field': 'allergies'},
                {'name': 'email', 'label': 'Email', 'field': 'email'},
                {'name': 'phone', 'label': 'Phone', 'field': 'phone'},
                {'name': 'actions', 'label': '', 'field': 'family_id'},
            ])
        table_rows = []
        for r in sorted(registrations, key=lambda r: r.user(session=session).family.family_name):
            u = r.user(session=session)
            family = Family.get_by_id(u.family_id, session=session)
            row = {
                'family': family.family_name if family and family.family_name else "",
                'participant': u.participant_str,
                'cost': r.cost,
                'registration_ts': r.registration_ts.strftime('%Y-%m-%d %H:%M') if r.registration_ts else "",
                'waitlisted': "Yes" if waitlist_status.get(r.id, False) else "",
            }
            if is_admin:
                row.update({
                    'allergies': u.food_allergies_detail or "",
                    'email': u.contact_name_email or "",
                    'phone': u.phone_number if u.phone_number else "",
                    'family_id': family.id if family else None,
                })
            table_rows.append(row)
        table_export_buttons(table_columns, table_rows, filename=f"participants_event_{event.id}")
        table = ui.table(columns=table_columns, rows=table_rows).props('flat dense separator="horizontal"').classes('w-full')
        # The body slot replaces the entire row, so the action cell is inlined.
        # The button emits an 'edit_family' event that we route to the
        # on-behalf-of registration page below.
        table.add_slot('body', r'''
            <q-tr :props="props" :class="props.row.waitlisted === 'Yes' ? 'bg-red-1' : ''">
                <q-td v-for="col in props.cols" :key="col.name" :props="props">
                    <template v-if="col.name === 'actions'">
                        <q-btn v-if="props.row.family_id"
                               dense flat color="primary" icon="edit" label="Edit"
                               @click="() => $parent.$emit('edit_family', props.row.family_id)" />
                    </template>
                    <template v-else>
                        {{ col.value }}
                    </template>
                </q-td>
            </q-tr>
        ''')
        if is_admin:
            table.on(
                'edit_family',
                lambda e, event_id=event.id: ui.navigate.to(
                    f'/event-registration/{event_id}/family/{e.args}'
                ),
            )

    if is_admin:
    # Per-family cost summary
        families_summary = {}
        for r in registrations:
            u = r.user(session=session)
            family = Family.get_by_id(u.family_id, session=session)
            if not family:
                continue
            summary = families_summary.get(family.family_name)
            if summary is None:
                summary = {
                    'total': 0,
                    'emails': set(),
                    'phones': set(),
                }
            summary['total'] += r.cost
            if u.email:
                summary['emails'].add(str(u.email))
            if u.phone_number:
                summary['phones'].add(str(u.phone_number))
            families_summary[family.family_name] = summary

        with ui.expansion(f'Costs by family ({len(families_summary)})', icon='expand_more').classes('w-full bg-grey-2'):
            cost_columns = [
                {'name': 'family', 'label': 'Family', 'field': 'family', 'sortable': True},
                {'name': 'total', 'label': 'Total', 'field': 'total', 'sortable': True, 'align': 'right'},
                {'name': 'emails', 'label': 'Emails', 'field': 'emails'},
                {'name': 'phones', 'label': 'Phones', 'field': 'phones'},
            ]
            cost_rows = []
            for name in sorted(families_summary.keys()):
                summary = families_summary[name]
                row = {
                    'family': name,
                    'total': summary['total'],
                    'emails': ', '.join(sorted(summary['emails'])),
                    'phones': ', '.join(sorted(summary['phones'])),
                }
                cost_rows.append(row)
            table_export_buttons(cost_columns, cost_rows, filename=f"costs_by_family_event_{event.id}")
            ui.table(columns=cost_columns, rows=cost_rows).props('flat dense separator="horizontal"').classes('w-full')

        # Admin-only: meal totals
        meal_rows = [
            ("Saturday breakfast", sum(1 for r in registrations if r.eat_saturday_breakfast)),
            ("Saturday lunch", sum(1 for r in registrations if r.eat_saturday_lunch)),
            ("Saturday dinner", sum(1 for r in registrations if r.eat_saturday_dinner)),
            ("Sunday breakfast", sum(1 for r in registrations if r.eat_sunday_breakfast)),
        ]
        with ui.expansion('Meal totals', icon='restaurant').classes('w-full bg-grey-2'):
            meal_columns = [
                {'name': 'meal', 'label': 'Meal', 'field': 'meal', 'sortable': True},
                {'name': 'total', 'label': 'Total', 'field': 'total', 'sortable': True, 'align': 'right'},
            ]
            meal_rows_data = [{'meal': meal_name, 'total': count} for meal_name, count in meal_rows]
            table_export_buttons(meal_columns, meal_rows_data, filename=f"meal_totals_event_{event.id}")
            ui.table(columns=meal_columns, rows=meal_rows_data).props('flat dense separator="horizontal"').classes('w-full')

        # Admin-only: list of participant emails for easy copy/paste
        emails_set = set()
        for r in registrations:
            u = r.user(session=session)
            if u.email:
                emails_set.add(str(u.email))
        emails = sorted(emails_set)
        with ui.expansion(f'Emails of participants ({len(emails)})', icon='mail').classes('w-full bg-grey-2'):
            ui.textarea(value=', '.join(emails)).props('readonly').classes('w-full')

        # Admin-only: phone numbers
        phone_numbers_set = set()
        for r in registrations:
            u = r.user(session=session)
            if u.phone_number:
                phone_numbers_set.add(str(u.phone_number))
        phone_numbers = sorted(phone_numbers_set)
        with ui.expansion(f'Phone numbers of participants ({len(phone_numbers)})', icon='call').classes('w-full bg-grey-2'):
            ui.textarea(value=', '.join(phone_numbers)).props('readonly').classes('w-full')

        # Admin-only: emergency contacts & license plates by family
        families_by_id = {}
        for r in registrations:
            u = r.user(session=session)
            family = Family.get_by_id(u.family_id, session=session)
            if family:
                families_by_id[family.id] = family
        families = sorted(families_by_id.values(), key=lambda f: f.family_name or "")
        with ui.expansion(f'Emergency contacts & license plates ({len(families)})', icon='contact_emergency').classes('w-full bg-grey-2'):
            table_columns = [
                {'name': 'family', 'label': 'Family', 'field': 'family', 'sortable': True},
                {'name': 'contact1', 'label': 'Contact 1', 'field': 'contact1'},
                {'name': 'phone1', 'label': 'Phone 1', 'field': 'phone1'},
                {'name': 'contact2', 'label': 'Contact 2', 'field': 'contact2'},
                {'name': 'phone2', 'label': 'Phone 2', 'field': 'phone2'},
                {'name': 'license', 'label': 'License plates', 'field': 'license'},
            ]
            table_rows = []
            for family in families:
                contact1 = f"{family.emergency_contact_first_name_1} {family.emergency_contact_last_name_1}".strip()
                contact2 = f"{family.emergency_contact_first_name_2} {family.emergency_contact_last_name_2}".strip()
                table_rows.append({
                    'family': family.family_name,
                    'contact1': contact1,
                    'phone1': family.emergency_contact_phone_number_1 or "",
                    'contact2': contact2,
                    'phone2': family.emergency_contact_phone_number_2 or "",
                    'license': family.car_license_plates or "",
                })
            table_export_buttons(table_columns, table_rows, filename=f"emergency_contacts_event_{event.id}")
            ui.table(columns=table_columns, rows=table_rows).props('flat separator=\"horizontal\"').classes('w-full')


def _family_is_registered_for(event: Event, current_user: User, session: SessionDep) -> bool:
    for u in current_user.get_all_from_family():
        if EventRegistration.get_by_user_and_event(user_id=u.id, event_id=event.id, session=session):
            return True
    return False


def render_camping_trip_detail(event: Event, request: Request, session: SessionDep):
    """Render the full detail widget for a single camping trip."""
    current_user = User.get_current(request=request, session=session)
    acting_admin = User.acting_is_admin(request=request, session=session)

    with ui.row().classes('w-full items-center'):
        ui.button(icon='arrow_back', on_click=lambda: ui.navigate.to('/')).props('flat').tooltip('Back to camping trips')
        ui.label('Camping Trip List').classes('text-lg font-bold')
        ui.space()
        if acting_admin:
            edit_url = f'/admin/events/{event.id}/edit'
            ui.button(
                'Edit', icon='edit',
                on_click=lambda url=edit_url: ui.navigate.to(url),
            ).props('outline color=primary').tooltip('Edit this camping trip')
            if event.is_upcoming and not event.cancelled:
                ui.button(
                    'Cancel Trip', icon='cancel',
                    on_click=lambda ev=event: _open_cancel_trip_dialog(
                        event=ev, request=request, session=session,
                    ),
                ).props('outline color=red').tooltip('Cancel this trip and drop all registrations')

    with ui.card().classes('w-full'):
        capacity_info = f" (capacity: {event.capacity})" if event.capacity else ""
        ui.label(
            f"{event.date} for {event.duration_in_days} days, "
            f"at {event.location}{capacity_info}"
        ).classes('text-lg font-bold')

        if event.cancelled:
            ui.label('🚫 This trip has been cancelled.').classes(
                'text-lg font-bold text-red-600'
            )

        if (event.details or '').strip():
            ui.markdown(event.details, sanitize=False).classes('w-full')

        render_participants_table(event=event, request=request, session=session)

        is_registered = _family_is_registered_for(event=event, current_user=current_user, session=session)
        if is_registered:
            ui.markdown(
                f"Your cost: **${event.get_family_cost(session=session, family_id=current_user.family_id)}**"
            )

        if event.is_upcoming and not event.cancelled:
            if is_registered:
                ui.label(
                    "🎉 You are registered! Click below to update the details of your registration"
                ).classes('text-lg text-italic')
            registration_page_url = f'/event-registration/{event.id}'
            ui.button(
                'Update registration' if is_registered else 'Register'
            ).on_click(
                lambda url=registration_page_url: ui.navigate.to(url)
            ).classes(BUTTON_CLASSES_ACCEPT)


def _open_cancel_trip_dialog(event: Event, request: Request, session: SessionDep) -> None:
    """Confirm-and-cancel modal. Marks the event ``cancelled = True`` so the
    trip is no longer registrable, but keeps every existing
    ``EventRegistration`` intact — that history is what tells us who *would*
    have come.

    Server-side admin guard mirrors the button-visibility check; the audit
    hook records the reason against the Event update.
    """
    if not User.current_user_is_admin(request=request, session=session):
        ui.notify('Only admins can cancel a trip', color='negative')
        return

    with simple_dialog() as dialog, ui.card():
        with ui.card_section():
            ui.label(
                f"Cancel camping trip on {event.date} at {event.location}?"
            ).classes('text-lg font-bold')
            ui.label(
                "The trip moves to the Cancelled tab and can no longer be "
                "registered to. Existing registrations are preserved for "
                "historical reference."
            ).classes('text-sm')
        reason_input = ui.textarea(
            'Reason (required)',
            placeholder="e.g., 'Site closed due to wildfire risk'",
        ).classes('w-full').props('outlined autofocus')

        def confirm():
            # Re-bind the actor for this event-handler task — ContextVars
            # set in chrome() don't survive across async boundaries.
            set_actor_from_request(request=request, session=session)

            reason = (reason_input.value or '').strip()
            if not reason:
                ui.notify('Reason is required', color='negative')
                return

            event.cancelled = True
            token = current_reason.set(reason)
            try:
                event.save(session=session)
            except AuditError as e:
                ui.notify(str(e), color='negative')
                session.rollback()
                session.expire(event)
                return
            except Exception as e:  # pragma: no cover - defensive
                logger.exception(e)
                ui.notify(f"Failed to cancel trip: {e}", color='negative')
                session.rollback()
                session.expire(event)
                return
            finally:
                current_reason.reset(token)

            ui.notify('Trip cancelled.', color='positive')
            dialog.close()
            ui.navigate.to('/')

        with ui.row().classes('justify-end gap-2'):
            ui.button('Keep Trip', on_click=dialog.close).classes(BUTTON_CLASSES_CANCEL)
            ui.button('Cancel Trip', icon='cancel', on_click=confirm).classes(BUTTON_CLASSES_ACCEPT)

    dialog.open()


def _render_trip_list_item(event: Event, current_user: User, session: SessionDep, acting_admin: bool, request: Request) -> None:
    """One clickable row in the camping-trips list."""
    url = f'/camping-trip/{event.id}'
    capacity_info = f" (capacity: {event.capacity})" if event.capacity else ""
    is_registered = _family_is_registered_for(event=event, current_user=current_user, session=session)

    with ui.card().classes('w-full cursor-pointer hover:bg-grey-2').on(
        'click', lambda url=url: ui.navigate.to(url)
    ):
        with ui.row().classes('w-full items-center no-wrap'):
            ui.icon(
                'block' if event.cancelled else ('event' if event.is_upcoming else 'history')
            ).classes('text-2xl')
            with ui.column().classes('grow gap-0'):
                ui.label(
                    f"{event.date} for {event.duration_in_days} days, "
                    f"at {event.location}{capacity_info}"
                ).classes('text-lg font-bold')
                if event.cancelled:
                    ui.label('🚫 Cancelled').classes('text-sm text-italic text-red-600')
                elif is_registered:
                    ui.label('🎉 You are registered').classes('text-sm text-italic')
            if acting_admin:
                edit_url = f'/admin/events/{event.id}/edit'
                edit_btn = ui.button(
                    'Edit', icon='edit',
                    on_click=lambda url=edit_url: ui.navigate.to(url),
                ).props('flat color=primary').tooltip('Edit this camping trip')
                # Prevent the card's row-level click handler from also firing
                # and navigating into the trip detail page.
                edit_btn.on('click.stop', lambda: None)

                # Cancel Trip is only meaningful on still-active upcoming trips.
                if event.is_upcoming and not event.cancelled:
                    cancel_btn = ui.button(
                        'Cancel Trip', icon='cancel',
                        on_click=lambda ev=event: _open_cancel_trip_dialog(
                            event=ev, request=request, session=session,
                        ),
                    ).props('flat color=red').tooltip('Cancel this trip and drop all registrations')
                    cancel_btn.on('click.stop', lambda: None)
            ui.icon('chevron_right').classes('text-2xl')


def render_home_page(request: Request, session: SessionDep):

    current_user = User.get_current(request=request, session=session)
    acting_admin = User.acting_is_admin(request=request, session=session)
    upcoming_events = Event.get_upcoming(session=session)
    past_events = sorted(Event.get_past(session=session), key=lambda e: e.date, reverse=True)
    cancelled_events = Event.get_cancelled(session=session)

    if acting_admin:
        with ui.row().classes('w-full justify-end mb-2'):
            ui.button(
                'Create new',
                icon='add',
                on_click=lambda: ui.navigate.to('/admin/events/new'),
            ).classes(BUTTON_CLASSES_ACCEPT)

    with ui.card().classes('w-full').tight():
        with ui.tabs().classes('w-full bg-secondary text-white shadow-2') as tabs:
            one = ui.tab('Upcoming Camping Trips', icon="event")
            two = ui.tab('Past Camping Trips', icon="history")
            three = ui.tab('Cancelled', icon="block")
        with ui.tab_panels(tabs, value=one).classes('w-full'):
            with ui.tab_panel(one):
                if upcoming_events:
                    for event in upcoming_events:
                        _render_trip_list_item(event=event, current_user=current_user, session=session, acting_admin=acting_admin, request=request)
                else:
                    ui.label('No upcoming events found. Come back soon!').classes('text-lg font-bold text-red-500')

            with ui.tab_panel(two):
                if past_events:
                    for event in past_events:
                        _render_trip_list_item(event=event, current_user=current_user, session=session, acting_admin=acting_admin, request=request)
                else:
                    ui.label('No past events found').classes('text-lg font-bold text-red-500')

            with ui.tab_panel(three):
                if cancelled_events:
                    for event in cancelled_events:
                        _render_trip_list_item(event=event, current_user=current_user, session=session, acting_admin=acting_admin, request=request)
                else:
                    ui.label('No cancelled trips').classes('text-lg font-bold text-grey-500')
