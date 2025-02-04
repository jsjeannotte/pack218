from typing import List, Literal, Annotated, Optional, Type

import bcrypt
from nicegui import nicegui
from pydantic import computed_field, AfterValidator
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, select, Relationship
from typing_extensions import get_args

from pack218.entities import SQLModelWithSave, T
from pack218.persistence.engine import engine
from sqlalchemy import String
from sqlmodel import Field

from pack218.entities.family import Family


class InvalidPasswordException(Exception):
    pass

class InvalidNewPasswordException(Exception):
    pass


Gender = Literal["Not provided", "Prefer not to share", "Male", "Female", "Other"]


def username_is_unique(value: str) -> str:
    try:
        User.get_by_username(value)
        raise ValueError(f'Username {value} is already taken')
    except NoResultFound:
        return value


class User(SQLModelWithSave, table=True):
    class Config:
        title = "User"

    id: int | None = Field(default=None, primary_key=True)
    username: Annotated[str, AfterValidator(username_is_unique)] = Field(default="", title="Username", unique=True)

    first_name: str = Field(default="", title="First Name")
    last_name: str = Field(default="", title="Last Name")
    email: str = Field(default="", title="Email")
    phone_number: str | None = Field(default="", title="Phone Number")
    car_license_plates: str | None = Field(default="", title="Car License Plates(s)")

    # Private fields for Admins
    hashed_password: str = Field(default="", title="Encrypted Password", exclude=True)
    is_admin: bool = Field(False, title="Is Admin")

    # Couldn't get Enum to work, let's keep it simple and use Literal
    #gender: Gender = Field(default_factory=Gender, title="Gender", sa_type=AutoString)
    #gender: Gender = Field(default=Gender.NOT_PROVIDED, sa_column=Column(SQLModelEnum(Gender)))
    gender: Gender = Field(
        default=get_args(Gender)[0], sa_type=String, title="Gender")

    # Add a foreign key to the Family table
    family_id: int | None = Field(default=None, title="Family", foreign_key="family.id")
    family: Family | None = Relationship(back_populates="family_members", sa_relationship_kwargs={"lazy": "selectin"})


    def pre_save_check(self):
        if not self.username:
            raise ValueError("Username is required")

    @computed_field
    @property
    def family_name(self) -> str:
        if self.family_id:
            return self.family.family_name
        else:
            return "Not provided"

    @property
    def family_size(self) -> int:
        family_members = self.get_all_from_family()
        return len(family_members)


    @staticmethod
    def hash_password(password) -> str:
        # Generate a salt
        salt = bcrypt.gensalt()

        # Hash the password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)

        # Convert to a string
        hashed_password_str = hashed_password.decode('utf-8')
        return hashed_password_str

    def set_hashed_password(self, password: str) -> None:
        self.hashed_password = User.hash_password(password)

    def validate_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode('utf-8'), self.hashed_password.encode('utf-8'))

    def update_password(self, current_password: str, new_password: str, new_password_confirmation: str) -> bool:
        if new_password != new_password_confirmation:
            raise InvalidNewPasswordException("New password and confirmation do not match")
        if not self.validate_password(current_password):
            raise InvalidPasswordException("Invalid value for the current password")

        self.set_hashed_password(new_password)

    def get_all_from_family(self) -> List['User']:
        with Session(engine) as session:
            statement = select(User).where(User.family_id == self.family_id)
            results = session.exec(statement)
            return list(results.all())

    @staticmethod
    def get_by_username(username: str, session: Optional[Session] = None) -> 'User':
        def execute_query(s: Session) -> User:
            statement = select(User).where(User.username == username)
            result = s.exec(statement)
            return result.one()

        if session is None:
            with Session(engine) as session:
                return execute_query(session)
        else:
            return execute_query(session)

    @staticmethod
    def get_current(session: Optional[Session] = None) -> 'User':
        return User.get_by_username(nicegui.app.storage.user['username'], session=session)

    @staticmethod
    def current_user_is_admin(session: Optional[Session] = None) -> bool:
        try:
            current_user = User.get_current(session=session)
            return current_user.is_admin
        except NoResultFound:
            return False

    @classmethod
    def delete_by_id(cls: Type[T], id: int, session: Optional[Session] = None):
        # Ensure we're not trying to delete ourselves
        if id == User.get_current(session=session).id:
            raise ValueError("You cannot delete yourself. Ask another Admin to do it.")
        super().delete_by_id(id=id, session=session)
