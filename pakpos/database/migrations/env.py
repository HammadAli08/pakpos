"""
Alembic migration environment for PakPOS.
Uses DB_URL and Base.metadata from pakpos.database.engine.
"""
from __future__ import annotations

import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from pakpos.config.settings import DB_URL
from pakpos.database.engine import Base
from pakpos.database.models import (
    category, product, customer, supplier,
    sale, purchase, payment, expense,
    stock_movement, user, audit, setting,
)

config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)

# Respect passed-in URL if specified (e.g. during pytest)
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", DB_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
