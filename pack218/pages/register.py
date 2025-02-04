from typing import Optional

from nicegui import ui
import nicegui
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session
from starlette.responses import RedirectResponse

from pack218.entities.user import User
from pack218.pages.ui_components import BUTTON_CLASSES_ACCEPT
from pack218.pages.utils import validate_new_password


def render_page_register(session: Session):
    def register() -> Optional[RedirectResponse]:  # local function to avoid passing username and password as arguments
        try:
            User.get_by_username(username.value, session=session)
            ui.notify('This username is already taken', color='negative')
            return
        except NoResultFound:

            # Validate the password
            if not validate_new_password(password.value, password_confirm.value):
                return
            else:
                # Create the user
                user = User(username=username.value,
                            first_name='', last_name='', email='',
                            hashed_password=User.hash_password(password.value))
                user.save()

                # Autologin
                nicegui.app.storage.user.update({'username': username.value, 'user_id': user.id, 'authenticated': True})
                # Refresh the page
                ui.navigate.to('/my-profile?first_time=1')

    with ui.card().classes('absolute-center'):
        username = ui.input('Username').on('keydown.enter', register)
        password = ui.input('Password', password=True, password_toggle_button=True).on('keydown.enter', register)
        password_confirm = ui.input('Password (Confirm)', password=True, password_toggle_button=True).on(
            'keydown.enter', register)
        ui.button('Register', on_click=register).classes(BUTTON_CLASSES_ACCEPT)
    return None
