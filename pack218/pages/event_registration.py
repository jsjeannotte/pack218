import json
import logging
import re
import uuid
from typing import Optional

from nicegui import ui
import nicegui
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session
from starlette.responses import RedirectResponse

from pack218.config import config
from pack218.email import send_message
from pack218.entities.models import EventRegistration, Event, User

from pack218.pages.ui_components import BUTTON_CLASSES_ACCEPT, card_title, card, simple_dialog
from pack218.pages.utils import validate_new_password

logger = logging.getLogger(__name__)

def render_page_event_registration(session: Session, event_id: int):

    current_user = User.get_current(session=session)
    event = Event.get_by_id(event_id, session=session)

    def perform_event_registration():  # local function to avoid passing username and password as arguments
        has_registered_user = False
        with simple_dialog() as dialog, card():
            with ui.card_section():
                ui.label('Thank you for registering for this event.').classes('text-lg font-bold')
            with ui.card_section():
                for user_id, fields in user_to_fields.items():
                    user = User.get_by_id(user_id, session=session)
                    # Check if we should delete the registration (when all fields are False)
                    if not any([field_checkbox.value for field_checkbox in fields.values()]):
                        event_registration = EventRegistration.get_by_user_and_event(user_id=user_id, event_id=event_id, session=session)
                        if event_registration:
                            EventRegistration.delete_by_id(event_registration.id, session=session)
                            ui.label(f"❌ Looks like {user.first_name} is no longer coming. Maybe next time!")
                    else:
                        event_registration = EventRegistration.get_or_create_by_user_and_event(user_id=user_id, event_id=event_id, session=session)
                        for field_name, field_checkbox in fields.items():
                            # First, let's see if we have a registration for this user already
                            setattr(event_registration, field_name, field_checkbox.value)

                        event_registration.save(session=session)
                        ui.label(f"☑️ Registration pending for {user.first_name}.")
                        has_registered_user = True
            if has_registered_user:
                with ui.card_section():
                    ui.label('📧 We will send you a confirmation email shortly.').classes('text-lg text-italic')
            with ui.card_section():
                ui.button('Close').on_click(dialog.close).classes(BUTTON_CLASSES_ACCEPT)

        dialog.open()

    with ui.card().classes('w-full').tight():
        card_title('Event Registration')
        with card():
            with ui.card_section():
                ui.label(f"🏕️ Camping trip: {event.date} for 2 days, at {event.location}").classes('text-lg font-bold')
                with ui.card_section():
                    ui.label('Please fill out the form below to register your family for this event')
                    with ui.row():

                        user_to_fields = {}

                        # For each family member, create a ui.card with a form to register them
                        for u in current_user.get_all_from_family():

                            # Get the current registration
                            current_event_registration = EventRegistration.get_by_user_and_event(user_id=u.id, event_id=event_id, session=session)

                            user_to_fields[u.id] = {}
                            with ui.card().tight():
                                card_title(f"{u.first_name} {u.last_name} ({u.family_member_type})", level=2)
                                with card():
                                    with ui.card_section():
                                        ui.label(f"Will this family member stay overnight?")
                                        user_to_fields[u.id]["stay_friday_night"] = ui.checkbox(
                                            "Stay Friday Night",
                                            value=current_event_registration is not None and current_event_registration.stay_friday_night)
                                        user_to_fields[u.id]["stay_saturday_night"] = ui.checkbox(
                                            "Stay Saturday Night",
                                            value=current_event_registration is not None and current_event_registration.stay_saturday_night)
                                    with ui.card_section():
                                        ui.label(f"Select all the meals that you wish to be included with your experience")
                                        user_to_fields[u.id]["eat_saturday_breakfast"] = ui.checkbox(
                                            "Saturday Breakfast",
                                            value=current_event_registration is not None and current_event_registration.eat_saturday_breakfast)
                                        user_to_fields[u.id]["eat_saturday_lunch"] = ui.checkbox(
                                            "Saturday Lunch",
                                            value=current_event_registration is not None and current_event_registration.eat_saturday_lunch)
                                        user_to_fields[u.id]["eat_saturday_dinner"] = ui.checkbox(
                                            "Saturday Night Dinner",
                                            value=current_event_registration is not None and current_event_registration.eat_saturday_dinner)
                                        user_to_fields[u.id]["eat_sunday_breakfast"] = ui.checkbox(
                                            "Sunday Breakfast",
                                            value=current_event_registration is not None and current_event_registration.eat_sunday_breakfast)

                with ui.card_section():
                    with ui.row():
                        ui.button('Register').on_click(perform_event_registration).classes(BUTTON_CLASSES_ACCEPT)

