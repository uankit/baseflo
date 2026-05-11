"""Alembic env — async engine + autogenerate-friendly metadata.

Reads the database URL from `BASEFLO_DATABASE_URL`. Tests override via env.
Strips the `+asyncpg` driver suffix when running offline (`alembic upgrade --sql`)
since psycopg2 isn't a dependency.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_config
from app.db.base import Base

# Importing the models package registers every model on Base.metadata.
from app.db import models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _resolve_url() -> str:
    return get_config().database_url


def _set_sqlalchemy_url() -> None:
    config.set_main_option("sqlalchemy.url", _resolve_url())


def run_migrations_offline() -> None:
    _set_sqlalchemy_url()
    url = config.get_main_option("sqlalchemy.url") or ""
    # Offline mode emits raw SQL; psycopg/asyncpg distinction is irrelevant.
    context.configure(
        url=url.replace("+asyncpg", ""),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    # Alembic's default `alembic_version.version_num` column is varchar(32),
    # which is too narrow for our descriptive revision IDs (e.g.
    # "0006_refinements_exports_shares_feedback" is 40 chars). Pre-create the
    # table with a wider column; alembic skips its own create when the table
    # already exists.
    connection.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS alembic_version ("
        "version_num VARCHAR(96) NOT NULL, "
        "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
    )
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online_async() -> None:
    _set_sqlalchemy_url()
    section = config.get_section(config.config_ini_section, {})
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )
    async with connectable.begin() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_migrations_online_async())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
