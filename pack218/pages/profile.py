from typing import Optional, get_args

from nicegui import ui
import nicegui

from pack218.entities.family import Family
from pack218.entities.user import Gender, User
from pack218.pages.ui_components import grid, card_title, card, BUTTON_CLASSES_ACCEPT
from pack218.pages.utils import SessionDep


def render_profile_page(session: SessionDep, first_time: Optional[bool] = False):

    current_user = User.get_current(session=session)

    # Check if this is the first time the user is visiting this page
    if first_time:
        ui.notify('Welcome to your profile page! Please fill in your information.', color='positive')

    def apply_profile_update() -> None:
        ui.notify(f'Profile updated for username {nicegui.app.storage.user.get("username")}', color='positive')
        current_user.save(session=session)

    # # Bind the dark_mode value to the nicegui.app.storage.user object
    # ui.dark_mode().bind_value(nicegui.app.storage.user, 'dark_mode')
    # # And also bind it to the checkbox to control this
    # ui.checkbox('dark mode').bind_value(nicegui.app.storage.user, 'dark_mode')
    with grid():
        with card():
            card_title("Main profile")
            with ui.card_section():
                with ui.row():
                    ui.input('First Name').on('keydown.enter', apply_profile_update).bind_value(current_user,
                                                                                                'first_name')
                    ui.input('Last Name').on('keydown.enter', apply_profile_update).bind_value(current_user,
                                                                                               'last_name')
                with ui.row():
                    ui.input('📧 Email').on('keydown.enter', apply_profile_update).bind_value(current_user, 'email')
                    ui.input('☎️ Phone number').on('keydown.enter', apply_profile_update).bind_value(current_user, 'phone_number')

                with ui.row():
                    ui.select(list(get_args(Gender)), label='Gender').bind_value(current_user, 'gender').classes('w-full')

                with ui.row():
                    ui.select({f.id: f.family_name for f in list(Family.get_all())}, label='Your Family').bind_value(
                        current_user, 'family_id').classes('w-full')


        if current_user.family:
            ui.label(
                f"You are part of the {current_user.family.family_name} family (total of {current_user.family_size} members)")
        else:
            ui.label("You are not part of a family. Please update your profile.")

        ui.button('Update', on_click=apply_profile_update).classes(BUTTON_CLASSES_ACCEPT)
