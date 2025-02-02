from sqlalchemy import create_engine
from sqlmodel import SQLModel

engine = create_engine("sqlite:///database.db")

def init_db():
    SQLModel.metadata.create_all(engine)

