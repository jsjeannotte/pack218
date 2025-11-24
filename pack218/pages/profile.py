import logging
from enum import Enum
from functools import partial
from typing import get_args, Optional

from nicegui import ui
import nicegui
from sqlmodel import Session

from pack218.entities.models import Family, Gender, User, FamilyMemberType
from pack218.pages.ui_components import grid, card_title, card, BUTTON_CLASSES_ACCEPT, simple_dialog, \
    BUTTON_CLASSES_CANCEL
from pack218.pages.utils import SessionDep
from starlette.requests import Request
logger = logging.getLogger(__name__)

class CRUDMode(Enum):
    """CRUD mode for the user form"""
    CREATE = 'create'
    UPDATE = 'update'



def dialog_user_crud(request: Request, session: Session, crud_mode:CRUDMode, user: Optional[User] = None, contact_info_required: bool = False):
    """
    Show a dialog to create or update a user.
    """

    if user is None:
        if crud_mode == CRUDMode.UPDATE:
            raise ValueError("User must be provided in UPDATE mode")
        # Create a new user
        user = User()

    def apply_changes():
        if not user.family_id:
            user.family_id = User.get_current(request=request, session=session).family_id
        user.first_name = first_name.value
        user.last_name = last_name.value
        if contact_info_required:
            default_contact_value = ""
        else:
            default_contact_value = None
        # user.email = email.value or default_contact_value
        # user.email = None
        user.phone_number = phone_number.value or default_contact_value

        user.family_member_type = family_member_type.value

        user.gender = gender.value or None

        user.has_food_allergies = has_food_allergies.value
        user.food_allergies_detail = food_allergies_detail.value
        user.has_food_intolerances = has_food_intolerances.value
        user.food_intolerances = food_intolerances.value

        try:
            user.save()
            dialog.close()
            render_profile_page.refresh()
        except Exception as e:
            logger.exception(e)
            ui.notify(f'Error: {e}', color='negative')



    with simple_dialog() as dialog, ui.card():
        with ui.card_section():
            with ui.row():
                first_name = ui.input('First Name',
                         validation={'Need to provide a valid first name': lambda value: len(value) > 0}
                         )
                last_name = ui.input('Last Name',
                         validation={'Need to provide a valid last name': lambda value: len(value) > 0}
                         )
            with ui.row():
                family_member_type = ui.select(list(get_args(FamilyMemberType)), label='Family Member Type').classes('w-full')
            with ui.row():
                contact_info_suffix = " " if contact_info_required else " (optional)"
                # email = ui.input(f'📧 Email{contact_info_suffix}')
                phone_number = ui.input(f'☎️ Phone number{contact_info_suffix}')
            with ui.row():
                gender = ui.select(list(get_args(Gender)), label='Gender').classes('w-full')
            with ui.row():
                has_food_allergies = ui.checkbox('Has food allergies?').classes('w-full')
                food_allergies_detail = ui.textarea('Allergies Detail 💬').classes('w-full').bind_visibility_from(has_food_allergies, "value")
                with ui.tooltip().classes("text-base"):
                    ui.html(User.model_fields["food_allergies_detail"].description, sanitize=False).classes('text-sm')
            with ui.row():
                has_food_intolerances = ui.checkbox('Has food intolerances?').classes('w-full')
                food_intolerances = ui.textarea('Food Intolerances Detail').classes('w-full').bind_visibility_from(has_food_intolerances, "value")

        with ui.row():
            ui.button('Cancel').on_click(dialog.close).classes(BUTTON_CLASSES_CANCEL)
            if crud_mode == CRUDMode.UPDATE:
                first_name.bind_value(user, 'first_name')
                last_name.bind_value(user, 'last_name')
                # email.bind_value(user, 'email')
                phone_number.bind_value(user, 'phone_number')
                gender.bind_value(user, "gender")
                family_member_type.bind_value(user, "family_member_type")
                has_food_allergies.bind_value(user, "has_food_allergies")
                food_allergies_detail.bind_value(user, "food_allergies_detail")
                has_food_intolerances.bind_value(user, "has_food_intolerances")
                food_intolerances.bind_value(user, "food_intolerances")
                ui.button('Update user information').on_click(apply_changes).classes(BUTTON_CLASSES_ACCEPT)
            else:
                ui.button('Create family member').on_click(apply_changes).classes(BUTTON_CLASSES_ACCEPT)

    dialog.open()

def user_card(request: Request, session: Session, user: User):
    # Add padding
    with ui.card():
        with ui.row():
            ui.label(f"{user.first_name} {user.last_name} ({user.family_member_type})").classes('text-lg font-bold')
        if user.email or user.phone_number:
            with ui.row():
                if user.email:
                    ui.label(f"📧 {user.email}")
                if user.phone_number:
                    ui.label(f"☎️ {user.phone_number}")
        if user.has_food_allergies:
            with ui.row():
                ui.label(f"🚨Allergies:  {user.food_allergies_detail}").classes('text-lg text-red-500')
                with ui.tooltip().classes("text-base"):
                    ui.html(User.model_fields["food_allergies_detail"].description, sanitize=False).classes('text-sm')
        if user.has_food_intolerances:
            with ui.row():
                ui.label(f"🍽️ Intolerances: {user.food_intolerances}").classes('text-lg')
        with ui.row():
            ui.button('Update', on_click=partial(dialog_user_crud, request=request, session=session, crud_mode=CRUDMode.UPDATE, user=user)).classes(BUTTON_CLASSES_ACCEPT)

@ui.refreshable
def family_members(request: Request, session: SessionDep):
    current_user = User.get_current(request=request, session=session)
    with card().bind_visibility_from(current_user, "has_valid_family"):
        card_title("My Family Members (grown ups and cub scouts)")
        ui.button('Create/Add New', on_click=partial(dialog_user_crud, request=request, session=session, crud_mode=CRUDMode.CREATE,
                                                     user=None)).classes(BUTTON_CLASSES_ACCEPT)
        current_user.get_all_from_family()
        for user in current_user.get_all_from_family():
            with ui.card():
                user_card(request=request, session=session, user=user)


@ui.refreshable
def render_profile_page(request: Request, session: SessionDep):

    current_user = User.get_current(request=request, session=session)
    if current_user.family:
        family = current_user.family
    else:
        family = None

    def family_validation(e):
        if isinstance(e, int) or isinstance(e, str):
            current_value = e
        else:
            current_value = e.value
        if current_value == 0:
            return 'Need to provide a valid family'
        return None

    if not current_user.family:
        def apply_family_update() -> None:
            if family_id.value == 0:
                return ui.notify('Please select a family', color='negative')
            elif family_id.value == 'NEW_FAMILY':
                new_family = Family(family_name=family_name_input.value)
                new_family.save(session=session)
                current_user.family_id = new_family.id
                current_user.save(session=session)
                render_profile_page.refresh()
            else:
                current_user.family_id = family_id.value
                current_user.save(session=session)
                render_profile_page.refresh()

        # Show a dialog with a drop down to select a family, or a button to create a new family
        with simple_dialog() as dialog, ui.card():
            with card():
                card_title("Select your family or register a new one")
                with ui.card_section():
                    with ui.row():
                        options = {0: "⚠️ Select an existing family"}
                        options.update({f.id: f.family_name for f in list(Family.get_all())})
                        options["NEW_FAMILY"] = "🆕 Register a new family"
                        family_id = ui.select(options,
                                  label='Your Family',
                                  with_input=True,
                                  # on_change=lambda e: result_select_family.set_text(f'you selected: {e.value}'),
                                  validation=family_validation,
                                  value=0)

                with ui.card_section().bind_visibility_from(family_id, "value", value="NEW_FAMILY"):
                    with ui.row():
                        family_name_input = ui.input('Family Name',
                                 validation={'Need to provide a valid family name': lambda value: len(value) > 0}
                                 )
            with ui.row():
                ui.button('Close', on_click=dialog.close)
                ui.button('Update', on_click=apply_family_update).classes(BUTTON_CLASSES_ACCEPT)
        dialog.open()

    def apply_profile_update() -> None:
        ui.notify(f'Profile updated for username {nicegui.app.storage.user.get("username")}', color='positive')
        current_user.save(session=session)

    # # Bind the dark_mode value to the nicegui.app.storage.user object
    # ui.dark_mode().bind_value(nicegui.app.storage.user, 'dark_mode')
    # # And also bind it to the checkbox to control this
    # ui.checkbox('dark mode').bind_value(nicegui.app.storage.user, 'dark_mode')

    # with grid():
    #     with card():
    #         card_title("My information")
    #         user_card(current_user)

    def apply_family_update() -> None:
        ui.notify(f'Family updated for username {nicegui.app.storage.user.get("username")}', color='positive')
        family.save(session=session)

    with grid():
        with card():
            card_title("My Family Information")
            if family:
                with ui.card_section():
                    with ui.row():
                        ui.label("🚙 🛻 Please provide all your vehicles/cars licence plate numbers for the camping registrations").classes('text-lg')
                    with ui.row():
                        ui.input('Car(s) license plate numbers').on('keydown.enter', apply_family_update).bind_value(family,'car_license_plates').classes('w-full')
                with ui.card_section():
                    with ui.row():
                        ui.label("🚑 Primary Emergency Contact Information").classes('text-lg font-bold')
                    with ui.row():
                        ui.input('First Name').on('keydown.enter', apply_family_update).bind_value(family,
                                                                                                   'emergency_contact_first_name_1')
                        ui.input('Last Name').on('keydown.enter', apply_family_update).bind_value(family,
                                                                                                  'emergency_contact_last_name_1')
                        ui.input('Phone number').on('keydown.enter', apply_family_update).bind_value(family,'emergency_contact_phone_number_1')
                with ui.card_section():

                    with ui.row():
                        ui.label("🚑 Secondary Emergency Contact Information (optional)").classes('text-lg')
                    with ui.row():
                        ui.input('First Name').on('keydown.enter', apply_family_update).bind_value(family,
                                                                                                   'emergency_contact_first_name_2')
                        ui.input('Last Name').on('keydown.enter', apply_family_update).bind_value(family,
                                                                                                  'emergency_contact_last_name_2')
                        ui.input('Phone number').on('keydown.enter', apply_family_update).bind_value(family,
                                                                                                        'emergency_contact_phone_number_2')
                with ui.card_section():
                    with ui.row():
                        ui.button('Update my family information', on_click=apply_family_update).classes(BUTTON_CLASSES_ACCEPT)
            else:
                with ui.card_section():
                    with ui.row():
                        ui.markdown("You are not part of a family. [Please update your profile](/my-profile).").classes('text-lg font-bold text-red-500')

        family_members(request=request, session=session)
