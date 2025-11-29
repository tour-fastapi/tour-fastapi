import sys
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# --- Setup project path so Alembic can import app modules ---
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

# --- Load SQLAlchemy Base and models ---
from app.db.session import Base
from app.db import models  # ensure all models (Agency, Package, etc.) are imported

# --- Alembic Config object ---
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate support.
target_metadata = Base.metadata

# --------------------------------------------------------------
# Modify this if you use dynamic URLs from environment variables
# --------------------------------------------------------------
def get_url():
    return os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:password@localhost/user_auth"
    )

# --------------------------------------------------------------
# Offline mode (generates SQL scripts)
# --------------------------------------------------------------
def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,             # detect type changes
        compare_server_default=True,   # detect default changes
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

# --------------------------------------------------------------
# Online mode (runs migrations directly on DB)
# --------------------------------------------------------------
def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()

# --------------------------------------------------------------
# Entrypoint
# --------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
