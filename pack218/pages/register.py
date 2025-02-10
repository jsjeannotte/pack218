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
from pack218.entities.user import User
from pack218.pages.ui_components import BUTTON_CLASSES_ACCEPT
from pack218.pages.utils import validate_new_password

logger = logging.getLogger(__name__)

def render_page_register(session: Session):

    def register():  # local function to avoid passing username and password as arguments
        try:
            User.get_by_username(username.value, session=session)
            ui.notify('This username is already taken', color='negative')
            # return None
        except NoResultFound:
            # Validate the password
            if validate_new_password(password.value, password_confirm.value):

                # Generate uuid and use it as the confirmation code to send in the confirmation email
                confirmation_code = uuid.uuid4().hex

                # Create the user
                user = User(username=username.value,
                            email=email.value,
                            hashed_password=User.hash_password(password.value),
                            can_login=True,
                            email_confirmation_code=confirmation_code)

                try:
                    user.save()
                except Exception as e:
                    logger.exception(e)
                    ui.notify(f'Error: {e}', color='negative')
                else:

                    # Send the confirmation email
                    send_message(to=str(user.email), subject='Account Registration Confirmation',
                                 is_html=True,
                                 message_text=f'Please click on the following link to confirm your registration: '
                                      f'{config.pack218_app_url}/email-confirmation/{confirmation_code}')

                    # Autologin and store the user in the session with the expected confirmation code
                    nicegui.app.storage.user.update({'username': username.value, 'user_id': user.id, 'authenticated': True})

                    # Show a message to tell the user to check their email and look for a message with the subject we just sent
                    with ui.dialog().props('backdrop-filter="blur(8px) brightness(40%)"') as dialog, ui.card():
                        ui.image('/images/camping-thank-you.jpeg')
                        ui.label('Please check your email to confirm your registration').classes('text-xl')

                    while_they_wait = "/need-email-confirmation"
                    dialog.on('hide', lambda: ui.navigate.to(while_they_wait))
                    dialog.on('escape-key', lambda: ui.navigate.to(while_they_wait))
                    dialog.open()

    with ui.card().classes('absolute-center'):

        # def check_email(e):
        #     if not e or not re.match(r"[^@]+@[^@]+\.[^@]+", e):
        #         return 'Need to provide a valid email'
        #     return None

        username = ui.input('Username').on('keydown.enter', register)
        email = ui.input('Email Address',
                         # validation=check_email
                         ).on('keydown.enter', register)
        password = ui.input('Password', password=True, password_toggle_button=True).on('keydown.enter', register)
        password_confirm = ui.input('Password (Confirm)', password=True, password_toggle_button=True).on(
            'keydown.enter', register)
        ui.button('Register', on_click=register).classes(BUTTON_CLASSES_ACCEPT)
