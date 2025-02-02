from typing import List, Literal

import bcrypt
from niceguicrud import NiceCRUD
from sqlmodel import Session, select
from pack218.entities import SQLModelWithSave
from pack218.db import engine
from sqlalchemy import String
from sqlmodel import Field


class InvalidPasswordException(Exception):
    pass

class InvalidNewPasswordException(Exception):
    pass


class User(SQLModelWithSave, table=True):
    class Config:
        title = "User"

    id: str = Field(default="", title="Username", primary_key=True)
    first_name: str = Field(default="", title="First Name")
    last_name: str = Field(default="", title="Last Name")
    email: str = Field(default="", title="Email")

    # Private fields for Admins
    hashed_password: str = Field(default="", title="Encrypted Password", exclude=True)
    is_admin: bool = Field(False, title="Is Admin")

    # Couldn't get Enum to work, let's keep it simple and use Literal
    #gender: Gender = Field(default_factory=Gender, title="Gender", sa_type=AutoString)
    #gender: Gender = Field(default=Gender.NOT_PROVIDED, sa_column=Column(SQLModelEnum(Gender)))
    gender: Literal["Not provided", "Prefer not to share", "Male", "Female", "Other"] = Field(
        default="Not provided", sa_type=String, title="Gender")

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

    @staticmethod
    def get_all() -> List['User']:
        with Session(engine) as session:
            statement = select(User)
            results = session.exec(statement)
            return list(results.all())


    @staticmethod
    def get_by_id(id: str) -> 'User':
        with Session(engine) as session:
            statement = select(User).where(User.id == id)
            result = session.exec(statement)
            return result.one()

    @staticmethod
    def delete_by_id(id: str):
        with Session(engine) as session:
            camping_event = User.get_by_id(id=id)
            session.delete(camping_event)
            session.commit()



class UserCRUD(NiceCRUD):
    async def update(self, user: User):
        user.save()
        await super().update(user)

    async def create(self, user: User):
        user.save()
        await super().create(user)

    async def delete(self, id: str):
        User.delete_by_id(id)
        await super().delete(id)
