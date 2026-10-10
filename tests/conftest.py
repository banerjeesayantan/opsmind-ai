"""Shared pytest fixtures for the OpsMind test suite.

test_engine gives persistence-layer tests a real, isolated Postgres
database (opsmind_test) rather than the app's main database - every
test function gets a clean schema (drop_all + create_all) so tests never
depend on ordering or leak state between runs, while still exercising the
exact same SQLModel/Postgres code path used in production. This is what
lets IncidentPersistenceService be regression-tested for real instead of
mocked.
"""

import os

import pytest
from sqlalchemy import create_engine as _create_engine
from sqlmodel import SQLModel

TEST_DATABASE_URL = os.getenv(
    "OPSMIND_TEST_DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/opsmind_test",
)


def _build_test_engine():
    """Build a fresh engine for the test database, requiring PostgreSQL.

    Fails clearly if PostgreSQL is unavailable rather than falling back to SQLite,
    ensuring tests run against the true production-like database backend.
    """
    engine = _create_engine(TEST_DATABASE_URL)
    with engine.connect():
        pass
    return engine


@pytest.fixture()
def test_engine():
    """A real database engine with a freshly-created OpsMind schema.

    Function-scoped: every test starts from an empty schema and tears it
    down afterward, so tests are isolated from each other without needing
    to manually clean up rows.
    """
    engine = _build_test_engine()
    setup_succeeded = False

    try:
        # Import models so SQLModel.metadata knows about every table before
        # create_all runs - these modules aren't otherwise imported by a
        # plain "from sqlmodel import SQLModel" call.
        import app.models.action_execution  # noqa: F401
        import app.models.approval  # noqa: F401
        import app.models.diagnosis  # noqa: F401
        import app.models.evidence  # noqa: F401
        import app.models.hypothesis  # noqa: F401
        import app.models.incident  # noqa: F401
        import app.models.incident_event  # noqa: F401
        import app.models.postmortem  # noqa: F401
        import app.models.remediation  # noqa: F401
        import app.models.session  # noqa: F401
        import app.models.user  # noqa: F401
        import app.models.verification  # noqa: F401

        SQLModel.metadata.drop_all(engine)
        SQLModel.metadata.create_all(engine)
        setup_succeeded = True

        yield engine
    finally:
        try:
            if setup_succeeded:
                SQLModel.metadata.drop_all(engine)
        finally:
            engine.dispose()