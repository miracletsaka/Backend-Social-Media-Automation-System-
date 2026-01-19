import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import create_engine, pool
from alembic import context

# ✅ Loads backend/.env (make sure you run alembic from backend folder)
load_dotenv()

# this is the Alembic Config object, which provides access to the values within the .ini file
config = context.config

# ✅ ALWAYS override alembic.ini with DATABASE_URL from .env (works for offline + online)
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL is not set. Check backend/.env")

config.set_main_option("sqlalchemy.url", database_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---- MODELS / METADATA ----
from app.database import Base
from app.models import *  # noqa: F401,F403

# If you explicitly import models to ensure Alembic sees them, keep these:
from app.models.topic import Topic  # noqa: F401
from app.models.content_item import ContentItem  # noqa: F401
from app.models.approval import Approval  # noqa: F401
from app.models.job import Job  # noqa: F401

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")  # ✅ now comes from .env
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url"),  # ✅ now comes from .env
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
