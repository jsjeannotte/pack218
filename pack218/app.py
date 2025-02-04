"""This is just a simple authentication example.

Please see the `OAuth2 example at FastAPI <https://fastapi.tiangolo.com/tutorial/security/simple-oauth2/>`_  or
use the great `Authlib package <https://docs.authlib.org/en/v0.13/client/starlette.html#using-fastapi>`_ to implement a classing real authentication system.
Here we just demonstrate the NiceGUI integration.
"""
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Request, FastAPI
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session
from starlette.middleware.base import BaseHTTPMiddleware

from nicegui import ui
import nicegui

from pack218.config import config
from pack218.entities import NiceCRUDWithSQL
from pack218.entities.camping_event import CampingEvent
from pack218.entities.family import Family
from pack218.entities.user import User
from pack218.pages.profile import render_profile_page
from pack218.pages.register import render_page_register
from pack218.pages.ui_components import BUTTON_CLASSES_ACCEPT
from pack218.pages.update_password import render_update_password_page
from pack218.pages.utils import SessionDep, assert_is_admin

from pack218.persistence import create_db_and_tables


logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s')

logger = logging.getLogger(__name__)

# in reality users passwords would obviously need to be hashed
# TODO: Create a signup page
# TODO: Create a DB with the users and their hashed passwords
# TODO: NiceGUI: https://nicegui.io/#examples


unrestricted_page_routes = {'/login', '/register'}


@asynccontextmanager
async def lifespan(app_: FastAPI):
    logger.info("Creating DB and Tables (if they don't exist)...")
    create_db_and_tables()
    logger.info("TODO: Run migrations here")
    # run_migrations()
    yield
    logger.info("Shutting down...")


class AuthMiddleware(BaseHTTPMiddleware):
    """This middleware restricts access to all NiceGUI pages.

    It redirects the user to the login page if they are not authenticated.
    """

    async def dispatch(self, request: Request, call_next):
        if not nicegui.app.storage.user.get('authenticated', False):
            if not request.url.path.startswith('/_nicegui') and request.url.path not in unrestricted_page_routes:
                nicegui.app.storage.user['referrer_path'] = request.url.path  # remember where the user wanted to go
                return RedirectResponse('/login')
        return await call_next(request)


app = FastAPI(lifespan=lifespan)
nicegui.app.add_middleware(AuthMiddleware)


# Pages

def chrome(session: Session):
    def logout() -> None:
        nicegui.app.storage.user.clear()
        ui.navigate.to('/login')

    def menu() -> None:
        with ui.header().classes(replace='row items-center') as header:
            ui.button(on_click=lambda: left_drawer.toggle(), icon='menu').props('flat color=white')
            ui.label("Pack 218: Let's go camping!").classes('text-l font-bold')
            ui.space()
            ui.button(on_click=logout, icon='logout', text='Logout').classes('flat color=white')

        with ui.footer(value=False) as footer:
            ui.label('Reach out to us on email')

        with ui.left_drawer().classes('bg-blue-100 dark:bg-blue-400') as left_drawer:
            ui.label('My Profile')
            ui.link('Edit my profile', profile_page)
            ui.link('Update my password', update_password_page)

            if User.current_user_is_admin(session=session):
                ui.label('Admin')
                ui.link('Camping Events', admin_camping_events)
                ui.link('Users', admin_users)
                ui.link('Families', admin_families)

            ui.label('Log Out')
            ui.button(on_click=logout, icon='logout').props('outline round')

        with ui.page_sticky(position='bottom-right', x_offset=20, y_offset=20):
            ui.button(on_click=footer.toggle, icon='contact_support').props('fab')

    menu()



@ui.page('/')
def main_page(session: SessionDep) -> None:
    def logout() -> None:
        nicegui.app.storage.user.clear()
        ui.navigate.to('/login')

    chrome(session=session)

    with ui.column().classes('absolute-center items-center'):
        ui.label(f'Hello {nicegui.app.storage.user["username"]}!').classes('text-2xl')
        ui.button(on_click=logout, icon='logout').props('outline round')


@ui.page('/login')
def login(session: SessionDep) -> Optional[RedirectResponse]:
    def try_login() -> None:  # local function to avoid passing username and password as arguments
        try:
            user_trying_to_login = User.get_by_username(username.value, session=session)
        except NoResultFound:
            ui.notify('Wrong username or password', color='negative')
            return
        if user_trying_to_login.validate_password(password.value):
            nicegui.app.storage.user.update({'username': username.value, 'authenticated': True})
            ui.navigate.to(nicegui.app.storage.user.get('referrer_path', '/'))  # go back to where the user wanted to go
        else:
            ui.notify('Wrong username or password', color='negative')

    if nicegui.app.storage.user.get('authenticated', False):
        return RedirectResponse('/')
    with ui.card().classes('absolute-center'):
        username = ui.input('Username').on('keydown.enter', try_login)
        password = ui.input('Password', password=True, password_toggle_button=True).on('keydown.enter', try_login)
        ui.button('Log in', on_click=try_login).classes(BUTTON_CLASSES_ACCEPT)
        ui.link('Click here to register', page_register)
    return None


@ui.page('/register')
def page_register(session: SessionDep) -> Optional[RedirectResponse]:
    return render_page_register(session=session)


@ui.page('/my-profile')
def profile_page(session: SessionDep, first_time: Optional[bool] = False) -> None:
    chrome(session=session)
    render_profile_page(session=session, first_time=first_time)


@ui.page('/admin/families')
def admin_families(session: SessionDep) -> None:
    assert_is_admin(session=session)
    chrome(session=session)
    ui.label('This is the admin page to manage families.')
    NiceCRUDWithSQL(basemodeltype=Family, basemodels=list(Family.get_all()), heading="Families")

@ui.page('/admin/camping-events')
def admin_camping_events(session: SessionDep) -> None:
    assert_is_admin(session=session)
    chrome(session=session)
    ui.label('This is the admin page for the camping events.')
    NiceCRUDWithSQL(basemodeltype=CampingEvent, basemodels=list(CampingEvent.get_all()), heading="Camping Events")

@ui.page('/admin/users')
def admin_users(session: SessionDep) -> None:
    assert_is_admin(session=session)
    chrome(session=session)
    ui.label('This is the admin page to manage users.')
    NiceCRUDWithSQL(basemodeltype=User, basemodels=list(User.get_all()), heading="Users")


@ui.page("/update-password")
def update_password_page(session: SessionDep) -> None:
    render_update_password_page(session=session)


ui.run_with(
    app,
    # mount_path='/',  # NOTE this can be omitted if you want the paths passed to @ui.page to be at the root
    storage_secret=config.pack218_storage_key,
    # NOTE setting a secret is optional but allows for persistent storage per user
)

# if __name__ in {"__main__", "__mp_main__"}:
#     # ui.run(storage_secret=os.environ["PACK218_STORAGE_SECRET"])


