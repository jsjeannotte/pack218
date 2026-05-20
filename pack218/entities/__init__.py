from typing import TypeVar, Optional, Type, Sequence

from nicegui import ui
from niceguicrud import NiceCRUD, NiceCRUDConfig
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, Session, select
from pack218.persistence.engine import engine


# Define a generic type variable for the SQLModelWithSave class
T = TypeVar('T', bound='SQLModelWithSave')


class SQLModelWithSave(SQLModel):

    def pre_save(self):
        # Override this method to add custom logic like validation before saving
        pass

    def save(self, session: Optional[Session] = None) -> None:
        # Local imports inside make_the_save avoid an import cycle:
        # pack218.audit.hooks imports models which import this module.
        def make_the_save():
            from pack218.audit import (
                diff_for,
                enforce_on_behalf_rules,
                record_change,
            )
            from pack218.entities.models import ActionLog

            is_action_log = isinstance(self, ActionLog)

            # Audit log rows bypass enforcement and self-recording — without
            # this the audit hook would recurse forever. ActionLog rows must
            # be append-only: existing rows are rejected so the log cannot be
            # rewritten through the same primitive that wrote it.
            if is_action_log:
                if sa_inspect(self).persistent or getattr(self, "id", None) is not None:
                    raise RuntimeError(
                        "ActionLog rows are append-only; "
                        "cannot update an existing audit row"
                    )
                self.pre_save()
                # audit: bypassed because ActionLog rows must not self-audit (recursion guard)
                session.add(self)
                session.commit()
                session.refresh(self)
                return

            # Determine action BEFORE state changes.
            state = sa_inspect(self)
            is_create = state.transient or state.pending
            action = "create" if is_create else "update"

            # 1. Existing validation hook.
            self.pre_save()

            # 2. Capture diff BEFORE enforce. Some enforce paths read related
            #    rows (e.g., the actor's User row) which could otherwise
            #    trigger autoflush and clear the dirty-attribute history.
            field_changes = diff_for(self, action)

            # 3. Enforce on-behalf rules (raises AuditError on violation).
            enforce_on_behalf_rules(session, self, action)

            # 4. Write the row.
            session.add(self)
            session.flush()  # populate id

            # 5. Record the audit row in the same transaction. record_change
            #    accepts the pre-flush diff so dirty-attribute history stays
            #    intact and live + tested code paths converge.
            record_change(session, self, action, field_changes=field_changes)

            session.commit()
            session.refresh(self)

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
    def delete_by_id(cls: Type[T], id: int, session: Optional[Session] = None) -> None:
        def execute_query(s: Session) -> None:
            from pack218.audit import (
                diff_for,
                enforce_on_behalf_rules,
                record_change,
            )
            from pack218.entities.models import ActionLog

            instance = cls.get_by_id(id=id, session=s, raise_if_not_found=True)

            # ActionLog rows are append-only — refuse to delete one through
            # the universal primitive even though we could technically do so.
            if isinstance(instance, ActionLog):
                raise RuntimeError(
                    "ActionLog rows are append-only; delete_by_id is not allowed"
                )

            enforce_on_behalf_rules(s, instance, "delete")
            # Capture the snapshot before deletion clears the row.
            field_changes = diff_for(instance, "delete")
            record_change(s, instance, "delete", field_changes=field_changes)

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