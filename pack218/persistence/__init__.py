from sqlmodel import Session, SQLModel

from pack218.persistence.engine import engine

# https://arunanshub.hashnode.dev/using-sqlmodel-with-alembic
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

def create_db_and_tables():
    metadata = SQLModel.metadata
    metadata.naming_convention = NAMING_CONVENTION
    metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session