from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# ---- App imports: URL + models metadata ----
from app.core.config import settings
from app.models.base import Base

# IMPORTANT: import modules that DEFINE tables (side effects register them)
import app.models.author  # registers Author
import app.models.book  # registers Book
import app.models.order  # registers Order, OrderItem, IdempotencyKey

# Alembic Config
config = context.config

# Logging from alembic.ini (if present)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Force URL from app settings (overrides alembic.ini)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Autogenerate will read from this
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = settings.DATABASE_URL  # ensure runtime URL even offline
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
    # engine_from_config will read the URL we set above
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
