"""Shared pytest fixtures for the OpsMind test suite.

test_engine gives persistence-layer tests a real, isolated Postgres
database (opsmind_test) rather than the app's main database - every
test function gets a clean schema (drop_all + create_all) so tests never
depend on ordering or leak state between runs, while still exercising the
exact same SQLModel/Postgres code path used in production. This is what
lets IncidentPersistenceService be regression-tested for real instead of
mocked.

Falls back to a temp file-backed SQLite database automatically if
OPSMIND_TEST_DATABASE_URL / the local Postgres test database isn't
reachable, so the suite still runs somewhere without Postgres installed -
but the intended, primary path is real Postgres.
"""

import os
import tempfile

import pytest
from sqlalchemy import create_engine as _create_engine, event
from sqlmodel import SQLModel

TEST_DATABASE_URL = os.getenv(
    "OPSMIND_TEST_DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/opsmind_test",
)


def _build_test_engine():
    """Build a fresh engine for the test database, falling back to SQLite.

    The SQLite fallback uses a temp *file* database rather than
    ":memory:". FastAPI's TestClient runs the ASGI app via an anyio
    worker-thread portal, not the pytest test thread, so any request
    handled through TestClient opens its DB connection from a different
    thread than the one that created the schema. An in-memory SQLite
    database ties its data to a single connection/pool, so sharing it
    correctly across threads depends on pool internals
    (poolclass=StaticPool) that turned out to behave inconsistently
    across platforms/SQLAlchemy versions in practice (confirmed: raises
    "no such table: ..." on some Windows setups even with StaticPool
    configured, while working fine on Linux). A real file on disk sidesteps
    that whole class of problem - it's the same database file regardless
    of which thread or connection opens it, exactly like talking to a
    real database server, with no pooling tricks required.
    """
    try:
        engine = _create_engine(TEST_DATABASE_URL)
        with engine.connect():
            pass
        return engine
    except Exception:
        db_fd, db_path = tempfile.mkstemp(suffix=".sqlite3", prefix="opsmind_test_")
        os.close(db_fd)
        engine = _create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )

        # SQLite does not enforce foreign key constraints by default,
        # unlike Postgres - without this, a bad foreign key (e.g. a
        # Remediation pointed at a nonexistent diagnosis_id) would
        # silently succeed on this fallback while genuinely raising an
        # IntegrityError against the real Postgres path, making any test
        # of that behavior backend-dependent/flaky.
        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine


def _sqlite_file_path(engine) -> str | None:
    """The on-disk path of a file-backed SQLite engine, or None otherwise."""
    if engine.dialect.name != "sqlite":
        return None
    database = engine.url.database
    if not database or database == ":memory:":
        return None
    return database


@pytest.fixture()
def test_engine():
    """A real database engine with a freshly-created OpsMind schema.

    Function-scoped: every test starts from an empty schema and tears it
    down afterward, so tests are isolated from each other without needing
    to manually clean up rows. If the fallback SQLite file was used, its
    temp file is also removed on teardown.
    """
    engine = _build_test_engine()

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

    yield engine

    SQLModel.metadata.drop_all(engine)
    engine.dispose()

    sqlite_path = _sqlite_file_path(engine)
    if sqlite_path:
        try:
            os.remove(sqlite_path)
        except OSError:
            pass