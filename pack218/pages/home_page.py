from nicegui import ui

from pack218.entities.models import EventRegistration, Event, User, Family
from pack218.pages.ui_components import BUTTON_CLASSES_ACCEPT, table_export_buttons
from pack218.pages.utils import SessionDep
from starlette.requests import Request


def render_participants_table(event: Event, request: Request, session: SessionDep):

    registrations = event.get_registrations(session=session)

    # participants = event.get_participants(session=session)
    with ui.expansion(f'Participants ({len(registrations)})', icon='expand_more').classes('w-full bg-grey-2'):
        # Generate the list of participants
        
        is_admin = User.get_current(request=request, session=session).is_admin
        if is_admin:
            cols = ["Family", "Participant", "Cost", "Allergies", "Email", "Phone"]
        else:
            cols = ["Family", "Participant", "Cost"]


        # Participants table
        table_columns = [
            {'name': 'family', 'label': 'Family', 'field': 'family', 'sortable': True},
            {'name': 'participant', 'label': 'Participant', 'field': 'participant', 'sortable': True},
            {'name': 'cost', 'label': 'Cost', 'field': 'cost', 'sortable': True, 'align': 'right'},
        ]
        if is_admin:
            table_columns.extend([
                {'name': 'allergies', 'label': 'Allergies', 'field': 'allergies'},
                {'name': 'email', 'label': 'Email', 'field': 'email'},
                {'name': 'phone', 'label': 'Phone', 'field': 'phone'},
            ])
        table_rows = []
        for r in sorted(registrations, key=lambda r: r.user(session=session).family.family_name):
            u = r.user(session=session)
            family = Family.get_by_id(u.family_id, session=session)
            row = {
                'family': family.family_name if family and family.family_name else "",
                'participant': u.participant_str,
                'cost': r.cost,
            }
            if is_admin:
                row.update({
                    'allergies': u.food_allergies_detail or "",
                    'email': u.contact_name_email or "",
                    'phone': u.phone_number if u.phone_number else "",
                })
            table_rows.append(row)
        table_export_buttons(table_columns, table_rows, filename=f"participants_event_{event.id}")
        ui.table(columns=table_columns, rows=table_rows).props('flat dense separator="horizontal"').classes('w-full')
    
    # Per-family cost summary
    family_costs = {}
    for r in registrations:
        u = r.user(session=session)
        family = Family.get_by_id(u.family_id, session=session)
        current_total = family_costs.get(family.family_name)
        family_costs[family.family_name] = (current_total + r.cost) if current_total is not None else r.cost

    with ui.expansion(f'Costs by family ({len(family_costs)})', icon='expand_more').classes('w-full bg-grey-2'):
        cost_columns = [
            {'name': 'family', 'label': 'Family', 'field': 'family', 'sortable': True},
            {'name': 'total', 'label': 'Total', 'field': 'total', 'sortable': True, 'align': 'right'},
        ]
        cost_rows = [{'family': name, 'total': family_costs[name]} for name in sorted(family_costs.keys())]
        table_export_buttons(cost_columns, cost_rows, filename=f"costs_by_family_event_{event.id}")
        ui.table(columns=cost_columns, rows=cost_rows).props('flat dense separator="horizontal"').classes('w-full')

    # Admin-only: meal totals
    if is_admin:
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
    if is_admin:
        emails_set = set()
        for r in registrations:
            u = r.user(session=session)
            if u.email:
                emails_set.add(str(u.email))
        emails = sorted(emails_set)
        with ui.expansion(f'Emails of participants ({len(emails)})', icon='mail').classes('w-full bg-grey-2'):
            ui.textarea(value=', '.join(emails)).props('readonly').classes('w-full')

    # Admin-only: phone numbers
    if is_admin:
        phone_numbers_set = set()
        for r in registrations:
            u = r.user(session=session)
            if u.phone_number:
                phone_numbers_set.add(str(u.phone_number))
        phone_numbers = sorted(phone_numbers_set)
        with ui.expansion(f'Phone numbers of participants ({len(phone_numbers)})', icon='call').classes('w-full bg-grey-2'):
            ui.textarea(value=', '.join(phone_numbers)).props('readonly').classes('w-full')
    
    # Admin-only: emergency contacts & license plates by family
    if is_admin:
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
                    
def render_home_page(request: Request, session: SessionDep):

    current_user = User.get_current(request=request, session=session)
    upcoming_events = Event.get_upcoming(session=session)
    past_events = Event.get_past(session=session)
    with ui.card().classes('w-full').tight():
        with ui.tabs().classes('w-full bg-secondary text-white shadow-2') as tabs:
            one = ui.tab('Upcoming Camping Trips', icon="event")
            two = ui.tab('Past Camping Trips', icon="history")
        with ui.tab_panels(tabs, value=one).classes('w-full'):
            with ui.tab_panel(one):
                if upcoming_events:
                    for event in upcoming_events:
                        with ui.card().classes('w-full'):
                            ui.label(f"{event.date} for 2 days, at {event.location}").classes('text-lg font-bold')

                            with ui.expansion('More details', icon='expand_more').classes('w-full bg-grey-2'):
                                ui.markdown(event.details).classes('w-full h-[calc(100vh-2rem)]')

                            render_participants_table(event=event, request=request, session=session)

                            # For each users in the family, check if they're registered
                            is_registered = False
                            for u in current_user.get_all_from_family():
                                event_registration = EventRegistration.get_by_user_and_event(user_id=u.id, event_id=event.id, session=session)
                                if event_registration:
                                    is_registered = True
                                    break
                            if is_registered:
                                ui.markdown(f"Your cost: **${event.get_family_cost(session=session, family_id=current_user.family_id)}**")
                                ui.label("🎉 You are registered! Click below to update the details of your registration").classes('text-lg text-italic')
                            registration_page_url = f'/event-registration/{event.id}'
                            ui.button('Update registration' if is_registered else f'Register').on_click(lambda: ui.navigate.to(registration_page_url)).classes(BUTTON_CLASSES_ACCEPT)
                else:
                    ui.label('No upcoming events found. Come back soon!').classes('text-lg font-bold text-red-500')

            with ui.tab_panel(two):
                with ui.row():
                    if past_events:
                        for event in past_events:
                            with ui.card():
                                ui.label(f"{event.date} for 2 days, at {event.location}").classes('text-lg font-bold')
                    else:
                        ui.label('No past events found').classes('text-lg font-bold text-red-500')
