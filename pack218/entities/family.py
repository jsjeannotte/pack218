from sqlmodel import Relationship
from pack218.entities import SQLModelWithSave
from sqlmodel import Field


class Family(SQLModelWithSave, table=True):
    class Config:
        title = "Family"

    id: int | None = Field(default=None, primary_key=True)
    family_name: str = Field(default="", title="Family Name")
    emergency_contact_first_name: str = Field(default="", title="Emergency Contact First Name")
    emergency_contact_last_name: str = Field(default="", title="Emergency Contact Last Name")
    emergency_contact_phone_number: str = Field(default="", title="Emergency Contact Phone Number")
    family_members: list["User"] = Relationship(back_populates="family", sa_relationship_kwargs={"lazy": "selectin"})
    # family_manager_user_id: str | None = Field(default=None, title="Family Manager User ID", foreign_key="user.id")

