from typing import Optional, get_args

from nicegui import ui
import nicegui

from niceguicrud import NiceCRUDConfig
from pack218.entities import NiceCRUDWithSQL
from pack218.entities.family import Family
from pack218.entities.user import Gender, User
from pack218.pages.ui_components import grid, card_title, card, BUTTON_CLASSES_ACCEPT
from pack218.pages.utils import SessionDep


# def family_info_label(user: User):
#     if user.family:
#         ui.label(f'👨‍👩‍👧‍👦 Family: {user.family.family_name}').classes('text-lg font-bold')
#         ui.label(f'🚙 🛻 Cars: {user.family.car_license_plates}').classes('text-lg')
#         ui.label(f'🚑 Primary Emergency Contact: {user.family.emergency_contact_first_name_1} {user.family.emergency_contact_last_name_1} {user.family.emergency_contact_phone_number_1}').classes('text-lg')
#         if user.family.emergency_contact_first_name_2:
#             ui.label(f'🚑 Secondary Emergency Contact: {user.family.emergency_contact_first_name_2} {user.family.emergency_contact_last_name_2} {user.family.emergency_contact_phone_number_2}').classes('text-lg')
#     else:
#         ui.label("You are not part of a family").classes('text-lg font-bold text-red-500')

def render_profile_page(session: SessionDep):

    current_user = User.get_current(session=session)
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
                dialog.close()
            else:
                ui.notify(f'Family updated for username {nicegui.app.storage.user.get("username")}', color='positive')
                current_user.family_id = family_id.value
                current_user.save(session=session)
                dialog.close()

        # Show a dialog with a drop down to select a family, or a button to create a new family
        with ui.dialog().props('backdrop-filter="blur(8px) brightness(40%)"') as dialog, ui.card():
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
                        family_name_input = ui.input('Last Name',
                                 validation={'Need to provide a valid last name': lambda value: len(value) > 0}
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
    with grid():
        with card():
            card_title("My information")
            with ui.card_section():
                with ui.row():
                    ui.input('First Name',
                             validation={'Need to provide a valid first name': lambda value: len(value) > 0 }
                             ).on('keydown.enter', apply_profile_update).bind_value(current_user,
                                                                                                'first_name')
                    ui.input('Last Name',
                             validation={'Need to provide a valid last name': lambda value: len(value) > 0 }
                             ).on('keydown.enter', apply_profile_update).bind_value(current_user,
                                                                                               'last_name')
                with ui.row():
                    ui.input('📧 Email').on('keydown.enter', apply_profile_update).bind_value(current_user, 'email')
                    ui.input('☎️ Phone number').on('keydown.enter', apply_profile_update).bind_value(current_user, 'phone_number')

                with ui.row():
                    ui.select(list(get_args(Gender)), label='Gender').bind_value(current_user, 'gender').classes('w-full')
            with ui.card_section():
                with ui.row():
                    ui.button('Update my information', on_click=apply_profile_update).classes(BUTTON_CLASSES_ACCEPT)

    def apply_family_update() -> None:
        ui.notify(f'Family updated for username {nicegui.app.storage.user.get("username")}', color='positive')
        family.save(session=session)


    # # Bind the dark_mode value to the nicegui.app.storage.user object
    # ui.dark_mode().bind_value(nicegui.app.storage.user, 'dark_mode')
    # # And also bind it to the checkbox to control this
    # ui.checkbox('dark mode').bind_value(nicegui.app.storage.user, 'dark_mode')

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

        with card().bind_visibility_from(current_user, "has_valid_family"):
            card_title("My Family Members (grown ups and cub scouts)")
            with ui.card_section():
                current_user.get_all_from_family()
                additional_exclude = ['family_id', 'is_admin', 'can_login',
                                      'email', 'phone_number', 'username', 'email_confirmed', 'email_confirmation_code']
                config = NiceCRUDConfig(additional_exclude=additional_exclude,
                                        column_count=1,
                                        heading="All Family Members (including yourself)",
                                        add_button_text="Add new family member",
                                        delete_button_text="Remove family member",
                                        new_item_dialog_heading="Add a new Family Member",
                                        update_item_dialog_heading="Update Family Member")
                NiceCRUDWithSQL(basemodeltype=User, basemodels=current_user.get_all_from_family(),
                                config=config)
