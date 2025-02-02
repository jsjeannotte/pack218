"""This is just a simple authentication example.

Please see the `OAuth2 example at FastAPI <https://fastapi.tiangolo.com/tutorial/security/simple-oauth2/>`_  or
use the great `Authlib package <https://docs.authlib.org/en/v0.13/client/starlette.html#using-fastapi>`_ to implement a classing real authentication system.
Here we just demonstrate the NiceGUI integration.
"""
from typing import Optional

from fastapi import Request
from fastapi.responses import RedirectResponse
from niceguicrud import NiceCRUDConfig
from sqlalchemy.exc import NoResultFound
from starlette.middleware.base import BaseHTTPMiddleware

from nicegui import app, ui

from pack218.entities.camping_event import CampingEventCRUD, CampingEvent
from pack218.entities.user import User, UserCRUD
from pack218.db import init_db

# in reality users passwords would obviously need to be hashed
# TODO: Create a signup page
# TODO: Create a DB with the users and their hashed passwords
# TODO: NiceGUI: https://nicegui.io/#examples


unrestricted_page_routes = {'/login', '/register'}


class AuthMiddleware(BaseHTTPMiddleware):
    """This middleware restricts access to all NiceGUI pages.

    It redirects the user to the login page if they are not authenticated.
    """

    async def dispatch(self, request: Request, call_next):
        if not app.storage.user.get('authenticated', False):
            if not request.url.path.startswith('/_nicegui') and request.url.path not in unrestricted_page_routes:
                app.storage.user['referrer_path'] = request.url.path  # remember where the user wanted to go
                return RedirectResponse('/login')
        return await call_next(request)


app.add_middleware(AuthMiddleware)

init_db()

def get_current_user() -> User:
    return User.get_by_id(app.storage.user['username'])


@ui.page('/my-profile')
def profile_page(first_time: Optional[bool] = False) -> None:
    header()

    # Check if this is the first time the user is visiting this page
    if first_time:
        ui.notify('Welcome to your profile page! Please fill in your information.', color='positive')

    def update_profile() -> None:
        ui.notify(f'Profile updated for username {app.storage.user.get("username")}', color='positive')

        # TODO: Update the user in the database
        current_user = get_current_user()
        current_user.email = email.value
        current_user.first_name = first_name.value
        current_user.last_name = last_name.value

        if update_password.value:
            current_user.update_password(current_password.value, new_password.value, new_password_confirm.value)

        # Reload the page
        ui.navigate.to('/my-profile')

    current_user = get_current_user()

    # # Bind the dark_mode value to the app.storage.user object
    # ui.dark_mode().bind_value(app.storage.user, 'dark_mode')
    # # And also bind it to the checkbox to control this
    # ui.checkbox('dark mode').bind_value(app.storage.user, 'dark_mode')

    email = ui.input('Email', value=current_user.email).on('keydown.enter', update_profile)
    first_name = ui.input('First Name', value=current_user.first_name).on('keydown.enter', update_profile)
    last_name = ui.input('First Name', value=current_user.last_name).on('keydown.enter', update_profile)

    update_password = ui.checkbox('Update password')
    current_password = ui.input('Current Password',
                                password=True,
                                password_toggle_button=True).on('keydown.enter', update_profile)
    new_password = ui.input('New Password', password=True, password_toggle_button=True).on(
        'keydown.enter',
        update_profile)
    new_password_confirm = ui.input('Confirm New Password', password=True, password_toggle_button=True).on(
        'keydown.enter',
        update_profile)

    ui.button('Update', on_click=update_profile)

def header():
    def logout() -> None:
        app.storage.user.clear()
        ui.navigate.to('/login')

    def menu() -> None:
        with ui.header().classes(replace='row items-center') as header:
            ui.button(on_click=lambda: left_drawer.toggle(), icon='menu').props('flat color=white')
            # with ui.tabs() as tabs:
            #     ui.tab('A')
            #     ui.tab('B')
            #     ui.tab('My Profile')

        with ui.footer(value=False) as footer:
            ui.label('Footer')

        with ui.left_drawer().classes('bg-blue-100 dark:bg-blue-400') as left_drawer:
            ui.label('My Profile')
            ui.link('Edit my profile', profile_page)
            ui.label('Admin')
            ui.link('Camping Events', admin_camping_event)
            ui.link('Users', admin_users)
            ui.label('Log Out')
            ui.button(on_click=logout, icon='logout').props('outline round')

        with ui.page_sticky(position='bottom-right', x_offset=20, y_offset=20):
            ui.button(on_click=footer.toggle, icon='contact_support').props('fab')

        # with ui.tab_panels(tabs, value='A').classes('w-full'):
        #     with ui.tab_panel('A'):
        #         ui.label('Content of A')
        #     with ui.tab_panel('Admin'):
        #         ui.label('Content of B')
        #     with ui.tab_panel('My Profile'):
        #         profile_page()

    menu()



@ui.page('/admin/users')
def admin_users() -> None:
    header()
    crud_config = NiceCRUDConfig(id_field="id", heading="Users", title="User")
    ui.label('This is the admin page to manage users.')
    UserCRUD(basemodeltype=User, basemodels=User.get_all(), config=crud_config)


@ui.page('/admin/camping-events')
def admin_camping_event() -> None:
    header()
    crud_config = NiceCRUDConfig(id_field="id", heading="Camping Events")
    ui.label('This is the admin page for the camping events.')
    CampingEventCRUD(basemodeltype=CampingEvent, basemodels=CampingEvent.get_all(), config=crud_config)


@ui.page('/')
def main_page() -> None:
    def logout() -> None:
        app.storage.user.clear()
        ui.navigate.to('/login')

    header()

    # with ui.column().classes('absolute-center items-center'):
    #     ui.label(f'Hello {app.storage.user["username"]}!').classes('text-2xl')
    #     ui.button(on_click=logout, icon='logout').props('outline round')


@ui.page('/subpage')
def test_page() -> None:
    ui.label('This is a sub page.')
    # NOTE dark mode will be persistent for each user across tabs and server restarts
    ui.dark_mode().bind_value(app.storage.user, 'dark_mode')
    ui.checkbox('dark mode').bind_value(app.storage.user, 'dark_mode')


@ui.page('/login')
def login() -> Optional[RedirectResponse]:
    def try_login() -> None:  # local function to avoid passing username and password as arguments
        try:
            user_trying_to_login = User.get_by_id(username.value)
        except NoResultFound as ex:
            ui.notify('Wrong username or password', color='negative')
            return
        # Todo: Handle wrong user
        if user_trying_to_login.validate_password(password.value):
            app.storage.user.update({'username': username.value, 'authenticated': True})
            ui.navigate.to(app.storage.user.get('referrer_path', '/'))  # go back to where the user wanted to go
        else:
            ui.notify('Wrong username or password', color='negative')

    if app.storage.user.get('authenticated', False):
        return RedirectResponse('/')
    with ui.card().classes('absolute-center'):
        username = ui.input('Username').on('keydown.enter', try_login)
        password = ui.input('Password', password=True, password_toggle_button=True).on('keydown.enter', try_login)
        ui.button('Log in', on_click=try_login)
        ui.link('Click here to register', page_register)
    return None


@ui.page('/register')
def page_register() -> Optional[RedirectResponse]:
    def register() -> Optional[RedirectResponse]:  # local function to avoid passing username and password as arguments
        # TODO: Make sure that this user doesn't already exist
        try:
            User.get_by_id(username.value)
            ui.notify('This username is already taken', color='negative')
            return
        except NoResultFound:
            # Create the user
            if password.value != password_confirm.value:
                ui.notify("The passwords don't match. Please try again", color='negative')
                return
            elif len(password.value) < 8:
                ui.notify("The password is too short (minimum 8 characters)", color='negative')
                return
            else:
                # Create the user
                user = User(id=username.value,
                            first_name='', last_name='', email='',
                            hashed_password=User.hash_password(password.value))
                user.save()
                # Autologin
                app.storage.user.update({'username': username.value, 'authenticated': True})
                # Refresh the page
                ui.navigate.to('/my-profile?first_time=1')

            #
            # if user_trying_to_login.validate_password(password.value):
            #     app.storage.user.update({'username': username.value, 'authenticated': True})
            #     ui.navigate.to(app.storage.user.get('referrer_path', '/'))  # go back to where the user wanted to go
            # else:
            #     ui.notify('Wrong username or password', color='negative')
    # if app.storage.user.get('authenticated', True):
    #     return RedirectResponse('/')
    with ui.card().classes('absolute-center'):
        username = ui.input('Username').on('keydown.enter', register)
        password = ui.input('Password', password=True, password_toggle_button=True).on('keydown.enter', register)
        password_confirm = ui.input('Password (Confirm)', password=True, password_toggle_button=True).on('keydown.enter', register)
        ui.button('Register', on_click=register)
    return None


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(storage_secret='ASDFDSFAWEFSDFGSDFVDFFADSF')