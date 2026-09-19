"""Regression tests for the test-database wiring in tests/conftest.py.

Guards against a specific class of bug: FastAPI's TestClient runs the
ASGI app via an anyio worker-thread portal (see starlette.testclient),
not the pytest test thread. An in-memory SQLite database
(sqlite://, ":memory:") ties its data to a single
connection/pool - sharing it correctly across threads then depends on
pool internals (poolclass=StaticPool) that, in practice, turned out to
behave inconsistently across platforms: confirmed working on Linux but
raising "sqlite3.OperationalError: no such table: ..." on some Windows
setups even with StaticPool configured. tests/conftest.py's SQLite
fallback therefore uses a temp *file* database instead - the same
database file regardless of which thread or connection opens it, with no
pooling tricks required, exactly like talking to a real database server.

tests/test_api_incidents.py already exercises this in practice (every
test there writes via one HTTP request and reads back via another), but
these tests isolate the exact mechanism directly so a regression here
fails fast and close to the cause, without needing a full API round trip
to diagnose, and without depending on a platform-specific quirk to
reproduce.

Run with: pytest tests/test_engine_fixture.py -v
"""

import os
import threading

from sqlmodel import Session, SQLModel, select

import app.models.database  # noqa: F401 - registers every table so create_all's schema has no dangling FKs
from app.models.incident import Incident
from tests.conftest import _build_test_engine, _sqlite_file_path


def test_sqlite_fallback_uses_a_file_not_in_memory():
    """The fallback must be a real file on disk, not an in-memory database.

    A direct assertion on the engine/url shape, rather than only testing
    the cross-thread behavior below, so a future edit that reintroduces
    ":memory:" (even if it happens to not break in a particular test
    run/platform) is caught immediately.
    """
    engine = _build_test_engine()
    try:
        if engine.dialect.name != "sqlite":
            return  # real Postgres test DB is reachable in this environment; nothing to check here
        path = _sqlite_file_path(engine)
        assert path is not None, "expected a file-backed SQLite database, not :memory:"
        assert os.path.exists(path)
    finally:
        engine.dispose()
        path = _sqlite_file_path(engine)
        if path:
            try:
                os.remove(path)
            except OSError:
                pass


def _create_then_query_from_another_thread(engine) -> dict:
    """Reproduces exactly what TestClient's portal thread does to the test engine:
    schema + a row created on the calling (pytest) thread, then queried
    from a different thread.

    Creates the full schema (not just the Incident table) because the
    SQLite fallback enables PRAGMA foreign_keys=ON to match Postgres's
    behavior (see tests/conftest.py) - Incident.created_by references
    the user table, so creating only Incident's table would make even a
    NULL-valued foreign key column fail to validate against a
    nonexistent referenced table. This also better matches how the real
    test_engine fixture always creates the schema.
    """
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(Incident(title="created on the main thread"))
        session.commit()

    results: dict = {}

    def _query_from_another_thread():
        try:
            with Session(engine) as session:
                results["incidents"] = list(session.exec(select(Incident)).all())
        except Exception as exc:  # pragma: no cover - failure path under test
            results["error"] = exc

    worker = threading.Thread(target=_query_from_another_thread)
    worker.start()
    worker.join(timeout=5)
    return results


def test_table_created_on_one_thread_is_visible_from_another_thread():
    """Same reproduction against a hand-built file-backed SQLite engine,
    independent of _build_test_engine(), so this test doesn't depend on
    Postgres being unreachable to exercise the mechanism.
    """
    import tempfile

    from sqlalchemy import create_engine

    db_fd, db_path = tempfile.mkstemp(suffix=".sqlite3", prefix="opsmind_test_engine_fixture_")
    os.close(db_fd)
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    try:
        results = _create_then_query_from_another_thread(engine)
        assert "error" not in results, f"Cross-thread query failed: {results.get('error')}"
        assert len(results["incidents"]) == 1
        assert results["incidents"][0].title == "created on the main thread"
    finally:
        SQLModel.metadata.drop_all(engine)
        engine.dispose()
        os.remove(db_path)


def test_build_test_engine_schema_is_visible_across_threads(monkeypatch):
    """The actual _build_test_engine() used by the test_engine fixture,
    exercised the same way: force the SQLite fallback path (as if Postgres/
    opsmind_test were unreachable) and confirm a table created on the main
    thread is queryable from another thread.
    """
    from tests import conftest as conftest_module

    monkeypatch.setattr(
        conftest_module, "TEST_DATABASE_URL", "postgresql+psycopg2://nouser:nopass@localhost:1/doesnotexist"
    )
    engine = _build_test_engine()
    assert engine.dialect.name == "sqlite", "expected the Postgres connection to fail and fall back to SQLite"

    try:
        results = _create_then_query_from_another_thread(engine)
        assert "error" not in results, f"Cross-thread query failed: {results.get('error')}"
        assert len(results["incidents"]) == 1
    finally:
        SQLModel.metadata.drop_all(engine)
        engine.dispose()
        path = _sqlite_file_path(engine)
        if path:
            os.remove(path)

            