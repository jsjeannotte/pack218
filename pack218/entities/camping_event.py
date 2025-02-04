from datetime import datetime

from sqlmodel import Field

from pack218.entities import SQLModelWithSave


class CampingEvent(SQLModelWithSave, table=True, title="Camping Event"):
    id: int | None = Field(default=None, primary_key=True)
    date: str = Field(default="", title="Date")

