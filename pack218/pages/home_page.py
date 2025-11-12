from nicegui import ui
import csv
import io

from pack218.entities.models import EventRegistration, Event, User, Family
from pack218.pages.ui_components import BUTTON_CLASSES_ACCEPT
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


        def header(text: str):
            return ui.label(text).classes('text-lg font-bold border p-1')

        def cell(text: object):
            return ui.label(str(text)).classes('border p-1')

        with ui.grid(columns=len(cols)).classes('gap-0'):
            for col in cols:
                header(col)
            
            for r in sorted(registrations, key=lambda r: r.user(session=session).family.family_name):
                u = r.user(session=session)
                family = Family.get_by_id(u.family_id, session=session)
                cell(family.family_name)
                cell(u.participant_str)
                cell(r.cost)
                if is_admin:
                    cell(u.food_allergies_detail)
                    cell(u.contact_name_email)
                    cell(u.phone_number if u.phone_number else "")
    
    # Per-family cost summary
    family_costs = {}
    for r in registrations:
        u = r.user(session=session)
        family = Family.get_by_id(u.family_id, session=session)
        current_total = family_costs.get(family.family_name)
        family_costs[family.family_name] = (current_total + r.cost) if current_total is not None else r.cost

    def download_family_costs():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["Family", "Total"])
        for family_name in sorted(family_costs.keys()):
            writer.writerow([family_name, family_costs[family_name]])
        ui.download(buffer.getvalue().encode("utf-8"), f"costs_by_family_event_{event.id}.csv")
    
    with ui.expansion(f'Costs by family ({len(family_costs)})', icon='expand_more').classes('w-full bg-grey-2'):
        if is_admin:
            ui.button('Download CSV', icon='file_download').on_click(download_family_costs)
        with ui.grid(columns=2).classes('gap-0'):
            header("Family")
            header("Total")
            for family_name in sorted(family_costs.keys()):
                cell(family_name)
                cell(family_costs[family_name])

    # Admin-only: meal totals
    if is_admin:
        meal_rows = [
            ("Saturday breakfast", sum(1 for r in registrations if r.eat_saturday_breakfast)),
            ("Saturday lunch", sum(1 for r in registrations if r.eat_saturday_lunch)),
            ("Saturday dinner", sum(1 for r in registrations if r.eat_saturday_dinner)),
            ("Sunday breakfast", sum(1 for r in registrations if r.eat_sunday_breakfast)),
        ]
        with ui.expansion('Meal totals', icon='restaurant').classes('w-full bg-grey-2'):
            with ui.grid(columns=2).classes('gap-0'):
                header("Meal")
                header("Total")
                for meal_name, count in meal_rows:
                    cell(meal_name)
                    cell(count)

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
