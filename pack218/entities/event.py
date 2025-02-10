from datetime import datetime
from typing import Literal

from sqlalchemy import String
from sqlmodel import Field, Relationship

from pack218.entities import SQLModelWithSave
from pack218.entities.event_registration import EventRegistration
from pack218.entities.user import User

EventType = Literal["Camping", "Other"]

class Event(SQLModelWithSave, table=True, title="Event"):
    id: int | None = Field(default=None, primary_key=True)
    event_type: EventType | None = Field(default=None, sa_type=String, title="Event Type")
    date: str = Field(default="", title="Date")

    # participants: list[User] = Relationship(back_populates="events", link_model=EventRegistration)

