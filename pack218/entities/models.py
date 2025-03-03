from datetime import datetime
from typing import Optional, Literal, Annotated, List, Type, Union
import bcrypt
import phonenumbers
from nicegui import nicegui
from sqlalchemy.exc import NoResultFound
from typing_extensions import get_args

from pydantic import BeforeValidator, EmailStr, computed_field
from pydantic_extra_types.phone_numbers import PhoneNumber

from sqlalchemy import String
from sqlmodel import Field, Session, select, Relationship

from pack218.entities import SQLModelWithSave, T
from pack218.persistence import engine

# Use US phone numbers only
PhoneNumber.default_region_code = 'US'



class EventRegistration(SQLModelWithSave, table=True, title="Event Registration"):

    id: int | None = Field(default=None, primary_key=True)

    # Add a foreign key to the User table
    user_id: int = Field(title="User", foreign_key="user.id")

    # Add a foreign key to the Event table
    event_id: int = Field(title="Event", foreign_key="event.id")

    # Default to now when creating a new EventRegistration
    registration_ts: datetime = Field(default_factory=datetime.now, title="Registration Date")

    stay_friday_night: bool = Field(default=False, title="Will sleepover on Friday Night")
    stay_saturday_night: bool = Field(default=False, title="Will sleepover on Saturday Night")

    eat_saturday_breakfast: bool = Field(default=False, title="Will enjoy Saturday's breakfast")
    eat_saturday_lunch: bool = Field(default=False, title="Will enjoy Saturday's lunch")
    eat_saturday_dinner: bool = Field(default=False, title="Will enjoy Saturday's dinner")
    eat_sunday_breakfast: bool = Field(default=False, title="Will enjoy Sunday's breakfast")

    has_paid: bool = Field(default=False, title="Has paid for the event")

    @property
    def user(self) -> 'User':
        return User.get_by_id(id=self.user_id, session=self.session)

    @staticmethod
    def select_by_event(session: Session, event_id: int) -> List['EventRegistration']:
        statement = select(EventRegistration).where(
            EventRegistration.event_id == event_id)
        results = session.exec(statement)
        return list(results.all())

    @staticmethod
    def get_by_user_and_event(session: Session, user_id: int, event_id: int) -> Optional['EventRegistration']:
        statement = select(EventRegistration).where(EventRegistration.user_id == user_id).where(EventRegistration.event_id == event_id)
        results = session.exec(statement)
        return results.one_or_none()

    @staticmethod
    def get_or_create_by_user_and_event(session: Session, user_id: int, event_id: int) -> 'EventRegistration':
        event_registration = EventRegistration.get_by_user_and_event(session=session, user_id=user_id, event_id=event_id)
        if event_registration is None:
            event_registration = EventRegistration(user_id=user_id, event_id=event_id)
            event_registration.save()
        return event_registration


EventType = Literal["Camping", "Other"]


def is_date(value: str) -> str:
    # See if this is a valid date of format YYYY-MM-DD
    try:
        datetime.strptime(value, '%Y-%m-%d')
    except ValueError:
        raise ValueError(f'{value} is not a valid date (Expecting format YYYY-MM-DD)')
    return value


Date = Annotated[str, BeforeValidator(lambda v: v + 1)]


class Event(SQLModelWithSave, table=True, title="Event"):
    id: int | None = Field(default=None, primary_key=True)
    event_type: EventType | None = Field(default=None, sa_type=String, title="Event Type")
    date: Date = Field(title="Date")
    location: str = Field(default="", title="Location")
    details: str = Field(default="", title="Details", description="textarea:Details about the event")
    duration_in_days: int = Field(default=2, title="Duration", description="Duration of the event (in days)")

    # TODO: Fix the issue with relationship so we can improve performance
    #  and remove our custom implementation: get_participants
    # participants: list[User] = Relationship(back_populates="events", link_model=EventRegistration)

    def get_participants(self, session: Session) -> List['User']:
        # TODO: Rewrite into a single query with joins

        # Using SQLModel, perform a select of all users in the user table that are registered for this event through the EventRegistration table
        statement = select(User).join(EventRegistration).where(EventRegistration.event_id == self.id)
        results = session.exec(statement)
        return list(results.all())
        # return [er.user for er in EventRegistration.select_by_event(session=session, event_id=self.id)]

    @property
    def date_as_datetime(self) -> datetime:
        return datetime.strptime(self.date, '%Y-%m-%d')

    @property
    def is_upcoming(self) -> bool:
        return self.date_as_datetime > datetime.now()

    @staticmethod
    def get_upcoming(session: Session) -> List['Event']:
        return [e for e in Event.get_all(session=session) if e.is_upcoming]

    @staticmethod
    def get_past(session: Session) -> List['Event']:
        return [e for e in Event.get_all(session=session) if not e.is_upcoming]


class Family(SQLModelWithSave, table=True):
    class Config:
        title = "Family"

    id: int | None = Field(default=None, primary_key=True)
    family_name: str = Field(default="", title="Family Name")
    emergency_contact_first_name_1: str = Field(default="", title="Emergency Contact First Name")
    emergency_contact_last_name_1: str = Field(default="", title="Emergency Contact Last Name")
    emergency_contact_phone_number_1: str = Field(default="", title="Emergency Contact Phone Number")
    emergency_contact_first_name_2: str = Field(default="", title="Secondary Emergency Contact First Name")
    emergency_contact_last_name_2: str = Field(default="", title="Secondary Emergency Contact Last Name")
    emergency_contact_phone_number_2: str = Field(default="", title="Secondary Emergency Contact Phone Number")

    car_license_plates: str | None = Field(default="", title="Car License Plates(s)")


    family_members: list["User"] = Relationship(back_populates="family", sa_relationship_kwargs={"lazy": "selectin"})
    # family_manager_user_id: str | None = Field(default=None, title="Family Manager User ID", foreign_key="user.id")


class InvalidPasswordException(Exception):
    pass


class InvalidNewPasswordException(Exception):
    pass


Gender = Literal["Not provided", "Prefer not to share", "Male", "Female", "Other"]
FamilyMemberType = Literal[
    "",
    "Adult Leader",
    "Cub Scout [Lion]",
    "Cub Scout [Tiger]",
    "Cub Scout [Wolf]",
    "Cub Scout [Bear]",
    "Cub Scout [Webelos]",
    "Cub Scout [Arrow of Light]",
    "Parent",
    "Guardian",
    "Sibling",
    "Other"]


class User(SQLModelWithSave, table=True):
    class Config:
        title = "User"

    id: int | None = Field(default=None, primary_key=True)
    username: str | None = Field(default=None, title="Username", description="The username is optional for family members (like cub scouts and partners) "
                                                                             "But if they want to login, they'll need to supply one for them.")

    # Private fields for Admins
    hashed_password: str = Field(default="", title="Encrypted Password", exclude=True)
    is_admin: bool = Field(False, title="Is Admin")

    # Profile
    first_name: str = Field(title="First Name")
    last_name: str = Field(title="Last Name")
    family_member_type: FamilyMemberType = Field(
        default=get_args(FamilyMemberType)[0], sa_type=String, title="Family Member Type")
    gender: Gender = Field(
        default=get_args(Gender)[0], sa_type=String, title="Gender")

    # Contact
    email: EmailStr | None = Field(default=None, title="Email")
    phone_number: PhoneNumber | None = Field(default=None, title="Phone Number")

    # Food related
    has_food_allergies: bool = Field(default=False, title="Has Food Allergies")
    food_allergies_detail: str = Field(default="",
                                       title="Food Allergies Details",
                                       description="🚨Please list all food allergies where a risk of anaphylaxis shock exists. "
                                                   "<br /><b>Note that you are responsible for bringing an EpiPen for "
                                                   "cases of emergencies.</b>")

    has_food_intolerances: bool = Field(default=False, title="Has Food Intolerances")
    food_intolerances: str = Field(default="", title="Food Intolerances")

    # Login/Registration related fields
    can_login: bool = Field(default=False,
                            title="Is a login user",
                            description="This user can log into the system (if not, 'username' is optional and this is mostly a family member / cub scout)")

    email_confirmed: bool = Field(default=False,
                                  title="User has confirmed their email")
    email_confirmation_code: str | None = Field(default=None, title="Email Confirmation Code")


    # Add a foreign key to the Family table
    family_id: int | None = Field(default=None, title="Family", foreign_key="family.id")
    family: Family | None = Relationship(back_populates="family_members", sa_relationship_kwargs={"lazy": "selectin"})

    # Events
    # events: list["Event"] = Relationship(back_populates="participants", link_model=EventRegistration)

    @property
    def has_valid_family(self) -> bool:
        return self.family_id is not None and self.family != 0

    def pre_save(self):
        if self.can_login:
            if not self.username:
                raise ValueError("Username is required for users that can login into the system.")
            if not self.email:
                raise ValueError("Email is required for users that can login into the system.")
        else:
            self.username = None
            if not self.family_id:
                # Let's default to getting the same family as the current user,
                # since this is probably the most likely use case
                self.family_id = User.get_current().family_id
        self.model_validate(self)

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
