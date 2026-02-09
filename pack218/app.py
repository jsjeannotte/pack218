"""This is just a simple authentication example.

Please see the `OAuth2 example at FastAPI <https://fastapi.tiangolo.com/tutorial/security/simple-oauth2/>`_  or
use the great `Authlib package <https://docs.authlib.org/en/v0.13/client/starlette.html#using-fastapi>`_ to implement a classing real authentication system.
Here we just demonstrate the NiceGUI integration.
"""
from authlib.integrations.starlette_client import OAuth
from fastapi import FastAPI, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from nicegui import ui
from starlette.config import Config
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
import logging
import os
from contextlib import asynccontextmanager

from jose import jwt

from fastapi import Request, FastAPI, Cookie, Depends
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from nicegui import ui, app
import nicegui

from pack218.config import config
from pack218.entities import NiceCRUDWithSQL
from pack218.entities.models import Event, Family, User
from pack218.pages.event_registration import render_page_event_registration
from pack218.pages.home_page import render_home_page
from pack218.pages.profile import render_profile_page
from pack218.pages.ui_components import BUTTON_CLASSES_ACCEPT
from pack218.pages.utils import SessionDep, assert_is_admin

from pack218.persistence import create_db_and_tables

from starlette.config import Config
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.cors import CORSMiddleware
from authlib.integrations.starlette_client import OAuth


logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s')

logger = logging.getLogger(__name__)

unrestricted_page_routes = {'/login'}

# FastAPI App instantiation
@asynccontextmanager
async def lifespan(app_: FastAPI):
    logger.info("Creating DB and Tables (if they don't exist)...")
    create_db_and_tables()
    yield
    if config.pack218_use_sqlite:
        from sqlalchemy import text
        from pack218.persistence.engine import engine
        logger.info("Checkpointing SQLite WAL...")
        with engine.connect() as conn:
            conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
    logger.info("Shutting down...")

fastapi_app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)
fastapi_app.add_middleware(SessionMiddleware, secret_key=config.pack218_storage_key)
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], #replace where needed
    allow_methods=["*"],
    max_age=3600,
)

if not config.local_dev:
    # Google OAuth
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

    # Replace these with your own values from the Google Developer Console
    GOOGLE_CLIENT_ID = config.google_oauth_client_id
    GOOGLE_CLIENT_SECRET = config.google_oauth_client_secret
    GOOGLE_REDIRECT_URI = f"{config.pack218_app_url}/auth"

    oauth_config = Config()
    oauth = OAuth(oauth_config)
    oauth.register(
        name='google',
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        redirect_uri=GOOGLE_REDIRECT_URI,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        authorize_state=config.pack218_storage_key,
        client_kwargs={'scope': 'openid email profile'}
    )

@app.get('/login')
async def login(request: Request):
    if config.local_dev:
        user = User.get_by_id(id=config.local_dev_user_id)
        if user is None:
            return JSONResponse(
                status_code=500,
                content={"error": f"LOCAL_DEV_USER_ID={config.local_dev_user_id} not found in DB"}
            )
        request.session["user"] = {
            "id": str(user.id),
            "email": user.email,
            "verified_email": True,
            "name": f"{user.first_name} {user.last_name}",
            "given_name": user.first_name,
            "family_name": user.last_name,
            "picture": "",
        }
        return RedirectResponse("/my-profile")
    # Normal OAuth flow
    referrer = request.headers.get('referer')
    if referrer:
        request.session['referrer'] = referrer
    return await oauth.google.authorize_redirect(request, GOOGLE_REDIRECT_URI)

if not config.local_dev:
    @app.get("/auth")
    async def auth(request: Request):
        token = await oauth.google.authorize_access_token(request)
        expires_in = token.get("expires_in")

        user_info_response = await oauth.google.get('https://www.googleapis.com/oauth2/v2/userinfo', token=token)
        user_info = user_info_response.json()
        request.session["user"] = user_info


        """
        Example user info:
        {
        "id":"1***************",
        "email":"user_email@gmail.com",
        "verified_email":true,
        "name":"<full name>",
        "given_name":"<first_name>",
        "family_name":"<last_name>",
        "picture":"https://lh3.googleusercontent.com/a/<...>"
        }
        """

        # TODO: Make sure the Google user has a verified email
        if not user_info.get('verified_email', False):
            # Return a 401 response
            return JSONResponse(status_code=401, content={"error": "Google User email is not verified. Please address this and try again."})

        # Check if the user already exists
        email = user_info.get('email')
        user = User.get_by_email_or_none(email=email)
        if user is None:
            # Create the user
            user = User(first_name=user_info.get('given_name'),
                        last_name=user_info.get('family_name'),
                        username=email,
                        email=email,
                        family_member_type='Parent',
                        hashed_password="GOOGLE_AUTH",
                        can_login=True,
                        email_confirmation_code="N/A")
            user.save()

        return RedirectResponse("/my-profile")

    @app.get("/token")
    async def get_token(token: str = Depends(oauth2_scheme)):
        return jwt.decode(token, GOOGLE_CLIENT_SECRET, algorithms=["HS256"])


@ui.page("/logout")
async def logout(request: Request):
    request.session.clear()
    ui.chat_message(text='Good bye! <a href="/login">Click here to login again</a>', text_html=True,
                    name='',
                    stamp='',
                    avatar='https://robohash.org/ui')
    return None

# Get this file's directory using __file__ and append the images folder
current_file_path = os.path.abspath(__file__)
current_directory = os.path.dirname(current_file_path)
nicegui.app.add_static_files('/images', f'{current_directory}/images')

def assert_logged_in(request: Request):
    user = request.session.get("user")
    should_redirect = user is None and not request.url.path.startswith('/_nicegui') and request.url.path not in unrestricted_page_routes
    logger.warning(f"user: {user}, would redirect: {should_redirect}")
    if should_redirect:
        return RedirectResponse('/login', headers={"Referer": str(request.url)})
    else: 
        return None

# Pages

def chrome(request: Request, session: Session):
    
    redirect = assert_logged_in(request=request)
    if redirect is not None:
        return redirect
    user_full_name = request.session.get('user', {}).get('name', 'N/A')
    
    def logout() -> None:
        ui.navigate.to('/logout')

    def menu() -> None:
        with ui.header().classes(replace='row items-center') as header:
            ui.button(on_click=lambda: left_drawer.toggle(), icon='menu').props('flat color=white')
            ui.label("Pack 218 Camping").classes('text-l font-bold')
            ui.space()
            ui.label(f'Hello {user_full_name}!').classes('mr-4')
            ui.button(on_click=logout, icon='logout', text='Logout').classes('flat color=white')

        with ui.footer(value=False) as footer:
            ui.label('Reach out to us on email')

        with ui.left_drawer().classes('bg-blue-100 dark:bg-blue-400') as left_drawer:
            ui.label('Home')
            ui.link('Camping Trips', main_page)

            ui.label('My Profile')
            ui.link('Manage my profile/family', profile_page)
            # ui.link('Update my password', update_password_page)

            if User.current_user_is_admin(request=request, session=session):
                ui.label('Admin')
                ui.link('Events', admin_events)
                ui.link('Create Event', admin_events_new)
                ui.link('Users', admin_users)
                ui.link('Families', admin_families)

            ui.label('Log Out')
            ui.button(on_click=logout, icon='logout').props('outline round')

        with ui.page_sticky(position='bottom-right', x_offset=20, y_offset=20):
            ui.button(on_click=footer.toggle, icon='contact_support').props('fab')

    # is_confirmed = assert_account_confirmed(session=session)
    # if is_confirmed:
    menu()


@ui.page('/')
def main_page(request: Request, session: SessionDep) -> None:
    redirect = redirect = chrome(request=request, session=session)
    if redirect is not None:
        return redirect
    render_home_page(request=request, session=session)

@ui.page('/my-profile')
def profile_page(request: Request, session: SessionDep) -> None:
    redirect = chrome(request=request, session=session)
    if redirect is not None:
        return redirect
    render_profile_page(request=request, session=session)

@ui.page('/event-registration/{event_id}')
def event_registration_page(request: Request, session: SessionDep, event_id: int) -> None:
    redirect = chrome(request=request, session=session)
    if redirect is not None:
        return redirect
    render_page_event_registration(request=request, session=session, event_id=event_id)

@ui.page('/admin/families')
def admin_families(request: Request, session: SessionDep) -> None:
    assert_is_admin(request=request, session=session)
    redirect = chrome(request=request, session=session)
    if redirect is not None:
        return redirect
    ui.label('This is the admin page to manage families.')
    NiceCRUDWithSQL(basemodeltype=Family, basemodels=list(Family.get_all()), heading="Families")

@ui.page('/admin/events')
def admin_events(request: Request, session: SessionDep) -> None:
    assert_is_admin(request=request, session=session)
    redirect = chrome(request=request, session=session)
    if redirect is not None:
        return redirect
    ui.label('This is the admin page for the events.')
    NiceCRUDWithSQL(basemodeltype=Event, basemodels=list(Event.get_all()), heading="Events")

@ui.page('/admin/events/new')
def admin_events_new(request: Request, session: SessionDep) -> None:
    assert_is_admin(request=request, session=session)
    redirect = chrome(request=request, session=session)
    if redirect is not None:
        return redirect

    ui.label('Create a new Camping Event').classes('text-lg font-bold mb-2')
    with ui.card().classes('w-full p-4').tight():
        with ui.grid(columns=3).classes('w-full gap-4 items-start'):
            date_input = ui.input('Date (YYYY-MM-DD)').props('type=date dense outlined').classes('w-full')
            location_input = ui.input('Location').props('dense outlined').classes('w-full')
            duration_input = ui.input('Duration in days', value='2').props('type=number dense outlined').classes('w-full')
        details_input = ui.textarea('Details (markdown supported)').props('outlined').classes('w-full h-40 mt-2')

        def create_event():
            date_value = (date_input.value or '').strip()
            location_value = (location_input.value or '').strip()
            duration_value = duration_input.value or '2'
            details_value = details_input.value or ''

            if not date_value or not location_value:
                ui.notify('Please provide date and location', type='warning')
                return
            try:
                duration_days = int(duration_value)
            except Exception:
                duration_days = 2

            event = Event(
                event_type='Camping',
                date=date_value,
                location=location_value,
                details=details_value,
                duration_in_days=int(duration_days),
            )
            event.save()
            ui.notify('Event created')
            ui.navigate.to('/admin/events')

        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button('Cancel', on_click=lambda: ui.navigate.to('/admin/events')).props('outline')
            ui.button('Create Event', icon='add').on_click(create_event).classes(BUTTON_CLASSES_ACCEPT)

@ui.page('/admin/users')
def admin_users(request: Request, session: SessionDep) -> None:
    assert_is_admin (request=request, session=session)
    redirect = chrome(request=request, session=session)
    if redirect is not None:
        return redirect
    ui.label('This is the admin page to manage users.')
    NiceCRUDWithSQL(basemodeltype=User, basemodels=list(User.get_all()), heading="Users")

ui.run_with(
    fastapi_app,
    mount_path='/',  # NOTE this can be omitted if you want the paths passed to @ui.page to be at the root
    storage_secret=config.pack218_storage_key,
    # NOTE setting a secret is optional but allows for persistent storage per user
    favicon="🏕️",
    title="Pack 218",
)

# if __name__ in {"__main__", "__mp_main__"}:
#     # ui.run(storage_secret=os.environ["PACK218_STORAGE_SECRET"])
