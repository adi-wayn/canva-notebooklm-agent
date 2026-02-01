"""Alembic migrations environment."""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# This is the Alembic Config object, which provides the values of the
# [alembic] section of the alembic.ini file as Python attributes for use
# in various create_*() statements throughout this script.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
from src.storage.models import Base

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a SQLALCHEMY_DATABASE_URL
    set in os.environ by default for
    'offline' mode.
    """
    from src.config import settings

    configuration = config.get_section(config.config_ini_section)
    
    # Convert async URL to sync URL for Alembic (remove +asyncpg driver)
    db_url = settings.database.url
    if "postgresql+asyncpg://" in db_url:
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    
    configuration["sqlalchemy.url"] = db_url

    with context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    ):

        with context.begin_transaction():
            context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    import asyncio

    from src.config import settings

    configuration = config.get_section(config.config_ini_section)
    
    # Convert async URL to sync URL for Alembic (remove +asyncpg driver)
    db_url = settings.database.url
    if "postgresql+asyncpg://" in db_url:
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    
    configuration["sqlalchemy.url"] = db_url

    connectable = engine_from_config(
        configuration,
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


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
