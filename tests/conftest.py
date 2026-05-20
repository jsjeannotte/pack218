# Shared fixtures for the pack218 test suite.
import pytest
from sqlmodel import SQLModel, Session, create_engine

from pack218.audit import current_actor, current_reason

# Importing models registers them with SQLModel.metadata so create_all sees them.
from pack218.entities.models import (  # noqa: F401
    User,
    Family,
    Event,
    EventRegistration,
    ActionLog,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def isolated_audit_context():
    """Reset audit contextvars after each test so they never leak between tests."""
    actor_token = current_actor.set(None)
    reason_token = current_reason.set(None)
    yield
    current_actor.reset(actor_token)
    current_reason.reset(reason_token)
