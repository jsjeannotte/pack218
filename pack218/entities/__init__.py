from typing import TypeVar, Optional, Type, Sequence

from nicegui import ui
from pack218.nicecrud import NiceCRUD, NiceCRUDConfig
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, Session, select
from pack218.persistence.engine import engine


# Define a generic type variable for the SQLModelWithSave class
T = TypeVar('T', bound='SQLModelWithSave')


class SQLModelWithSave(SQLModel):

    def pre_save(self):
        # Override this method to add custom logic like validation before saving
        pass

    def save(self, session: Session = None):
        def make_the_save():
            session.add(self)
            session.commit()
            session.refresh(self)

        # Validation
        self.pre_save()

        if session is None:
            with Session(engine) as session:
                make_the_save()
        else:
            make_the_save()

    @classmethod
    def get_by_id(cls: Type[T], id: int, session: Optional[Session] = None, raise_if_not_found: Optional[bool] = False) -> Optional[T]:
        def execute_query(s: Session) -> Optional[T]:
            statement = select(cls).where(cls.id == id)
            result = s.exec(statement)
            if raise_if_not_found:
                return result.one()
            else:
                return result.one_or_none()

        if session is None:
            with Session(engine) as session:
                return execute_query(session)
        else:
            return execute_query(session)

    @classmethod
    def get_all(cls: Type[T], session: Optional[Session] = None) -> Sequence[T]:
        def execute_query(s: Session) -> Sequence[T]:
            statement = select(cls)
            results = s.exec(statement)
            return results.all()

        if session is None:
            with Session(engine) as session:
                return execute_query(session)
        else:
            return execute_query(session)


    @classmethod
    def delete_by_id(cls: Type[T], id: int, session: Optional[Session] = None):
        def execute_query(s: Session) -> Optional[T]:
            instance = cls.get_by_id(id=id, session=s, raise_if_not_found=True)
            s.delete(instance)
            s.commit()
        if session is None:
            with Session(engine) as session:
                return execute_query(session)
        else:
            return execute_query(session)


class NiceCRUDWithSQL(NiceCRUD):

    def __init__(
            self,
            basemodeltype: Optional[Type[T]] = None,
            basemodels: list[T] = [],
            id_field: Optional[str] = None,
            config: NiceCRUDConfig | dict = None,
            **kwargs,  # Config parameters can be given by keyword arguments as well
    ):
        config = config or NiceCRUDConfig()
        if isinstance(config, dict):
            config = NiceCRUDConfig(**config, **kwargs)
        config.update(kwargs)

        # Since we have a convention of using `id` for the Primary key of all tables, we can set it as the default value
        if not id_field:
            config.id_field = 'id'

        # Add `id` to the additional exclude list
        config.additional_exclude.append('id')
        super().__init__(basemodeltype=basemodeltype, basemodels=basemodels, id_field=id_field, config=config)

    async def update(self, item: Type[T]):
        item.pre_save()
        item.save()
        await super().update(item)

    async def create(self, item: Type[T]):
        item.pre_save()
        try:
            item.save()
        except IntegrityError as e:
            # Get the error message and display it to the user (from the exception orig object)
            try:
                origin = e.orig.args[0]
            except Exception:
                origin = str(e)
            ui.notify(f"Integrity error: {origin}", color='negative')
            return
        await super().create(item)

    async def delete(self, id: int):
        self.basemodeltype.delete_by_id(id)
        await super().delete(id)