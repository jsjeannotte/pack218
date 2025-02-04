from sqlalchemy import create_engine
from sqlmodel import SQLModel

from pack218.config import config

# SQL_ALCHEMY_DATABASE_URL = "sqlite:///database.db"
SQL_ALCHEMY_DATABASE_URL = f"postgresql+psycopg://{config.postgres_user}:{config.postgres_password}@localhost:5332/pack218"


engine = create_engine(SQL_ALCHEMY_DATABASE_URL)

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = SQLModel.metadata
metadata.naming_convention = NAMING_CONVENTION