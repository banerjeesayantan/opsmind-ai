
"""Regression tests for the PostgreSQL-only test engine."""

import os
import tempfile
import threading

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, SQLModel, select

import app.models.database  # noqa: F401
from app.models.incident import Incident
from tests import conftest


def _create_then_query_from_another_thread(engine) -> dict:
    """Create a row on one thread and read it from another thread."""
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(Incident(title="created on the main thread"))
        session.commit()

    results = {}

    def _query():
        try:
            with Session(engine) as session:
                results["incidents"] = list(session.exec(select(Incident)).all())
        except Exception as exc:
            results["error"] = exc

    worker = threading.Thread(target=_query)
    worker.start()
    worker.join(timeout=5)

    assert not worker.is_alive(), "Worker thread did not finish"
    return results


def test_sqlite_file_database_is_visible_across_threads():
    """Preserve the independent SQLite file cross-thread regression test."""
    db_fd, db_path = tempfile.mkstemp(
        suffix=".sqlite3",
        prefix="opsmind_test_engine_fixture_",
    )
    os.close(db_fd)
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    try:
        results = _create_then_query_from_another_thread(engine)
        assert "error" not in results, str(results.get("error"))
        assert len(results["incidents"]) == 1
        assert results["incidents"][0].title == "created on the main thread"
    finally:
        SQLModel.metadata.drop_all(engine)
        engine.dispose()
        if os.path.exists(db_path):
            os.remove(db_path)


def test_build_test_engine_connects_to_postgresql():
    """The configured test engine must use the dedicated PostgreSQL DB."""
    engine = conftest._build_test_engine()

    try:
        assert engine.dialect.name == "postgresql"

        with engine.connect() as connection:
            database, user = connection.exec_driver_sql(
                "SELECT current_database(), current_user"
            ).one()

        assert database == "opsmind_test"
        assert user == "postgres"
    finally:
        engine.dispose()


def test_build_test_engine_does_not_fall_back_to_sqlite(monkeypatch):
    """A failed PostgreSQL connection must raise instead of using SQLite."""
    monkeypatch.setattr(
        conftest,
        "TEST_DATABASE_URL",
        "postgresql+psycopg2://nouser:nopass@127.0.0.1:1/doesnotexist",
    )

    with pytest.raises(OperationalError):
        conftest._build_test_engine()
id="opsmindfixture"
