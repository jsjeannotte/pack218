from typing import List

from niceguicrud import NiceCRUD
from sqlmodel import SQLModel, Field, Session, select

from pack218.db import engine


class CampingEvent(SQLModel, table=True, title="Camping Event"):
    id: str = Field(default="", primary_key=True)
    date: str = Field(default="", primary_key=True)

    def save(self):
        try:
            with Session(engine) as session:
                session.add(self)
                session.commit()
                session.refresh(self)
        except Exception as ex:
            raise ex

    @staticmethod
    def get_all() -> List['CampingEvent']:
        with Session(engine) as session:
            statement = select(CampingEvent)
            results = session.exec(statement)
            return list(results.all())


    @staticmethod
    def get_by_id(id: str) -> 'CampingEvent':
        with Session(engine) as session:
            statement = select(CampingEvent).where(CampingEvent.id == id)
            result = session.exec(statement)
            return result.one()

    @staticmethod
    def delete_by_id(id: str):
        with Session(engine) as session:
            camping_event = CampingEvent.get_by_id(id=id)
            session.delete(camping_event)
            session.commit()



class CampingEventCRUD(NiceCRUD):
    async def update(self, camping_event: CampingEvent):
        camping_event.save()
        await super().update(camping_event)

    async def create(self, camping_event: CampingEvent):
        camping_event.save()
        await super().create(camping_event)

    async def delete(self, id: str):
        CampingEvent.delete_by_id(id)
        await super().delete(id)
