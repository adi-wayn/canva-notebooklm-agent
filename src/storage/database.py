"""
Async database engine and session management.

Uses SQLAlchemy 2.0+ async API:
- AsyncEngine for non-blocking connections
- AsyncSession for transaction management
- Context managers for automatic cleanup
- Connection pooling with configurable pool_size

See ADR-009 (PostgreSQL + JSONB) for design rationale.

Usage:
    from src.storage.database import get_session
    
    async with get_session() as session:
        result = await session.execute(select(Workflow).where(...))
        workflows = result.scalars().all()
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.storage.models import Base


class Database:
    """Database connection manager."""

    def __init__(self):
        """Initialize database with settings."""
        self.engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[sessionmaker] = None

    async def connect(self) -> None:
        """
        Initialize database engine and session factory.

        Must be called on application startup.
        Connects to the configured database (PostgreSQL required for prod).
        """
        import logging
        logger = logging.getLogger(__name__)

        try:
            connect_args = {}
            engine_kwargs = {
                "echo": settings.database.echo,
                "pool_pre_ping": settings.database.pool_pre_ping,
                "pool_recycle": 3600,
            }

            if "sqlite" in settings.database.url:
                from sqlalchemy.pool import StaticPool
                engine_kwargs["poolclass"] = StaticPool
                engine_kwargs["connect_args"] = {"check_same_thread": False}
            else:
                engine_kwargs["pool_size"] = settings.database.pool_size
                engine_kwargs["max_overflow"] = 10

            engine = create_async_engine(
                settings.database.url,
                **engine_kwargs
            )
            # Probe connection early to surface auth/availability issues
            async with engine.connect() as conn:
                await conn.close()
            self.engine = engine
            logger.info(f"✓ Connected to database: {settings.database.url}")
        except Exception as e:
            logger.error(f"✗ Failed to connect to database: {e}")
            logger.error(f"  Database URL: {settings.database.url}")
            logger.error("  Postgres is required for production; SQLite is for testing only.")
            raise

        self._session_factory = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    async def disconnect(self) -> None:
        """
        Close database connections.

        Must be called on application shutdown.
        """
        if self.engine:
            await self.engine.dispose()

    async def create_tables(self) -> None:
        """
        Create all tables from models.

        WARNING: This does not run migrations. Use Alembic for production.
        This is only for development/testing when no migrations exist.
        """
        if not self.engine:
            raise RuntimeError("Database not connected. Call connect() first.")

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_tables(self) -> None:
        """
        Drop all tables.

        WARNING: This is destructive. Dev/test only.
        """
        if not self.engine:
            raise RuntimeError("Database not connected. Call connect() first.")

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get an async session context manager.

        Usage:
            async with database.session() as session:
                # Perform queries
                await session.execute(...)
                # Auto-commit on success, auto-rollback on exception

        Yields:
            AsyncSession: Database session
        """
        # Lazy-connect fallback for test environments where app startup isn't invoked
        if not self._session_factory:
            await self.connect()
            try:
                # Dev/test safety: ensure tables exist if migrations weren't applied
                await self.create_tables()
            except Exception:
                # Ignore if tables already exist or migrations manage schema
                pass

        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Global database instance
database = Database()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency injection for FastAPI.

    Usage in route handlers:
        @app.get("/workflows")
        async def list_workflows(session: AsyncSession = Depends(get_session)):
            ...

    Yields:
        AsyncSession: Database session (auto-committed/rolled-back)
    """
    async with database.session() as session:
        yield session
