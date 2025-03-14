from nicegui import ui
from sqlmodel import Session

from pack218.entities.models import InvalidPasswordException, InvalidNewPasswordException, User
from pack218.pages.ui_components import card_title, BUTTON_CLASSES_CANCEL, BUTTON_CLASSES_ACCEPT
from pack218.pages.utils import validate_new_password


def render_update_password_page(request: Request, session: Session):
    def apply_update_password() -> None:
        current_user = User.get_current(request=request, session=session)
        if not validate_new_password(new_password.value, new_password_confirm.value):
            return
        try:
            current_user.update_password(current_password.value, new_password.value, new_password_confirm.value)
        except InvalidPasswordException:
            ui.notify('Invalid value for the current password', color='negative')
            return
        except InvalidNewPasswordException:
            ui.notify("The passwords don't match. Please try again", color='negative')
            return

        current_user.save(session=session)

        # Clear the fields
        current_password.value = ''
        new_password.value = ''
        new_password_confirm.value = ''

        ui.notify('Password updated ... you will be redirected to the main page in a few seconds.', color='positive')
        ui.navigate.to('/')

    # with ui.card().tight().classes('absolute-center items-center col-2 '):
    # with ui.dialog().props('full-width'), ui.card():
    with ui.card().tight().classes('absolute-center'):
        card_title('Update password')
        with ui.card_section():
            current_password = ui.input('Current Password', password=True, password_toggle_button=True).on(
                'keydown.enter', apply_update_password)
            new_password = ui.input('New Password', password=True, password_toggle_button=True).on('keydown.enter',
                                                                                                   apply_update_password)
            new_password_confirm = ui.input('Confirm New Password', password=True, password_toggle_button=True).on(
                'keydown.enter', apply_update_password)
        with ui.card_section():
            with ui.row():
                ui.button('Cancel', on_click=lambda: ui.navigate.to("/")).classes(BUTTON_CLASSES_CANCEL)
                ui.button('Update', on_click=apply_update_password).classes(BUTTON_CLASSES_ACCEPT)
