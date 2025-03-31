from nicegui import ui

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
            cols = ["Family", "Participant", "Cost", "Allergies", "Email"]
        else:
            cols = ["Family", "Participant", "Cost"]


        def header(text: str):
            return ui.label(text).classes('text-lg font-bold border p-1')

        def cell(text: str):
            return ui.label(text).classes('border p-1')

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

                            ui.markdown(f"Your cost: **${event.get_family_cost(session=session, family_id=current_user.family_id)}**")

                            # For each users in the family, check if they're registered
                            is_registered = False
                            for u in current_user.get_all_from_family():
                                event_registration = EventRegistration.get_by_user_and_event(user_id=u.id, event_id=event.id, session=session)
                                if event_registration:
                                    is_registered = True
                                    break
                            if is_registered:
                                ui.label("🎉 You are registered! Click below to update the details of your registration").classes('text-lg text-italic')
                            ui.button('Update registration' if is_registered else 'Register').on_click(lambda: ui.navigate.to(f'/event-registration/{event.id}')).classes(BUTTON_CLASSES_ACCEPT)
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
