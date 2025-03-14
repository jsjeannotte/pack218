from nicegui import ui

from pack218.entities.models import EventRegistration, Event, User
from pack218.pages.ui_components import BUTTON_CLASSES_ACCEPT
from pack218.pages.utils import SessionDep
from starlette.requests import Request

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

                            participants = event.get_participants(session=session)
                            with ui.expansion(f'Participants ({len(participants)})', icon='expand_more').classes('w-full bg-grey-2'):
                                # Generate the list of participants
                                participants_md = ""
                                for u in participants:
                                    participants_md += " * " + f"{u.first_name} {u.last_name} ({u.family_member_type})\n"
                                ui.markdown(participants_md)

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
