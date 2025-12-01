from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Import your Base (all models must extend this)
from app.db.base import Base  # <-- this MUST exist and import all models

# Import settings to get DATABASE_URL
from app.core.config import settings

# ----------------------------------------------------------------------
# Alembic Config
# ----------------------------------------------------------------------

config = context.config

# Use your actual DATABASE_URL from .env
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging.
fileConfig(config.config_file_name)

# Metadata object for 'autogenerate'
target_metadata = Base.metadata

# ----------------------------------------------------------------------
# Run Migration Offline
# ----------------------------------------------------------------------
def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

# ----------------------------------------------------------------------
# Run Migration Online
# ----------------------------------------------------------------------
def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()

# ----------------------------------------------------------------------
# Execute Proper Mode
# ----------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
