from datetime import datetime

from sqlmodel import Field

from pack218.entities import SQLModelWithSave

class EventRegistration(SQLModelWithSave, table=True, title="Event Registration"):

    id: int | None = Field(default=None, primary_key=True)

    # Add a foreign key to the User table
    user_id: int = Field(title="User", foreign_key="user.id")

    # Add a foreign key to the Event table
    event_id: int = Field(title="Event", foreign_key="event.id")

    # Default to now when creating a new EventRegistration
    registration_ts: datetime = Field(default_factory=datetime.now, title="Registration Date")



