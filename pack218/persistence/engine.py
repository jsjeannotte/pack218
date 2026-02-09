import os

from sqlalchemy import create_engine, event
from sqlmodel import SQLModel
import logging

from pack218.config import config


logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s')
logger = logging.getLogger(__name__)

def get_sql_alchemy_database_url():
    if config.pack218_use_sqlite:
        return "sqlite:///database.db"
    else:
        connection_str = f"postgresql+psycopg://{config.postgres_user}:{config.postgres_password}@{config.postgres_host}:{config.postgres_port}/pack218"
        logger.info(f"Connecting to {connection_str}")
        return connection_str

engine = create_engine(get_sql_alchemy_database_url())

if config.pack218_use_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_wal_mode(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA wal_autocheckpoint=1000")
        cursor.close()

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = SQLModel.metadata
metadata.naming_convention = NAMING_CONVENTION
