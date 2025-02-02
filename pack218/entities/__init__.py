from sqlmodel import SQLModel, Session

from pack218.db import engine


class SQLModelWithSave(SQLModel):

    def save(self):
        with Session(engine) as session:
            session.add(self)
            session.commit()
            session.refresh(self)