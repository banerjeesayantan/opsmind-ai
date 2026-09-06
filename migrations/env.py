"""Alembic environment script for OpsMind AI.

The database URL is built here from app.core.config.settings (the same
POSTGRES_* environment variables the application itself reads) rather than
being hardcoded in alembic.ini, so migrations connect to whatever
environment they're run in without any credentials in version control.

Target metadata is SQLModel.metadata, populated by importing
app.models.database, which force-imports every table model (see that
module's docstring for why this matters for import-order safety).
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import (
    engine_from_config,
    pool,
)

from app.core.config import settings

# Import the model registry so every table is registered on SQLModel.metadata
# before Alembic looks at target_metadata below.
import app.models.database  # noqa: F401
from sqlmodel import SQLModel

# This is the Alembic Config object, which provides access to values within
# the .ini file in use.
config = context.config

# Interpret the config file for Python logging, unless it's disabled
# (e.g. when Alembic is invoked programmatically rather than from the CLI).
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Build the database URL from application settings rather than alembic.ini,
# so there is exactly one place (app/core/config.py) that owns database
# connection configuration.
DATABASE_URL = (
    "postgresql+psycopg://"
    f"{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
)
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# add your model's MetaData object here for 'autogenerate' support
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine, though an
    Engine is acceptable here as well. By skipping the Engine creation we
    don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the script
    output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a connection
    with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()