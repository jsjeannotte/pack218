from typing import Annotated

from fastapi import HTTPException, Depends
from nicegui import ui
import nicegui
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session

from pack218.entities.models import User
from pack218.persistence import get_session
from starlette.requests import Request


def validate_new_password(new_password: str, new_password_confirm: str) -> bool:
    if new_password != new_password_confirm:
        ui.notify("The passwords don't match. Please try again", color='negative')
        return False
    if len(new_password) < 8:
        ui.notify("The password is too short (minimum 8 characters)", color='negative')
        return False
    return True


def assert_is_admin(request: Request, session: Session) -> None:
    if not User.current_user_is_admin(request=request, session=session):
        ui.notify('You are not authorized to access this page', color='negative')
        raise HTTPException(status_code=403, detail="You are not authorized to access this page")


SessionDep = Annotated[Session, Depends(get_session)]
