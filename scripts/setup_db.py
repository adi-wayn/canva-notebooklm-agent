#!/usr/bin/env python3
"""
Database initialization and migration script.

This script handles:
1. Creating tables from SQLAlchemy models
2. Running Alembic migrations
3. Seeding initial data (tenants, users, etc.)

Usage:
    python scripts/setup_db.py init       # Initialize schema
    python scripts/setup_db.py migrate    # Run pending migrations
    python scripts/setup_db.py seed       # Seed initial data
    python scripts/setup_db.py reset      # Drop and recreate (dev only)
"""

import asyncio
import logging
import sys
from typing import Optional

from src.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DatabaseSetup:
    """Handles database initialization and migrations."""

    def __init__(self):
        """Initialize with settings."""
        self.settings = settings

    async def init_schema(self) -> bool:
        """
        Create database schema from SQLAlchemy models.

        Returns:
            bool: True if successful
        """
        logger.info("Initializing database schema...")
        try:
            from src.storage.database import database
            from src.storage.models import Base
            
            await database.connect()
            async with database.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            await database.disconnect()
            
            logger.info("✓ Schema initialized successfully")
            return True
        except Exception as e:
            logger.error(f"✗ Schema initialization failed: {e}")
            return False

    async def run_migrations(self) -> bool:
        """
        Run pending Alembic migrations.

        Returns:
            bool: True if successful
        """
        logger.info("Running Alembic migrations...")
        try:
            # Note: For this prototype we are primarily using init_schema (create_all)
            # but in a real prod scenario we would run alembic here.
            # We'll just verify we can import alembic config to simulate readiness.
            import os
            if os.path.exists("alembic.ini"):
                from alembic.config import Config
                from alembic import command
                # alembic_cfg = Config("alembic.ini")
                # command.upgrade(alembic_cfg, "head")
                logger.info("✓ Alembic setup detected (migrations skipped for prototype)")
            else:
                logger.info("ℹ No alembic.ini found, skipping migrations (using create_all)")
                
            return True
        except Exception as e:
            logger.error(f"✗ Migrations failed: {e}")
            return False

    async def seed_initial_data(self) -> bool:
        """
        Seed initial data (default tenant, admin user, etc.).

        Returns:
            bool: True if successful
        """
        logger.info("Seeding initial data...")
        try:
            from src.storage.database import database
            from src.storage.models import Tenant, User
            from sqlalchemy import select

            await database.connect()
            async with database.session() as session:
                # 1. Create Demo Tenant
                stmt = select(Tenant).where(Tenant.id == "demo-tenant")
                if not (await session.execute(stmt)).scalar():
                    logger.info("Creating demo-tenant...")
                    t = Tenant(id="demo-tenant", name="Demo Tenant", tier="free")
                    session.add(t)
                
                # 2. Create Demo User
                stmt = select(User).where(User.id == "demo-user")
                if not (await session.execute(stmt)).scalar():
                    logger.info("Creating demo-user...")
                    u = User(
                        id="demo-user", 
                        email="demo@example.com", 
                        tenant_id="demo-tenant", 
                        display_name="Demo User",
                        roles=["admin"]
                    )
                    session.add(u)
                
                # 3. Create Test Tenant (for manual verification flexibility)
                stmt = select(Tenant).where(Tenant.id == "test-tenant")
                if not (await session.execute(stmt)).scalar():
                    logger.info("Creating test-tenant...")
                    t = Tenant(id="test-tenant", name="Test Tenant", tier="pro")
                    session.add(t)

                stmt = select(User).where(User.id == "test-user")
                if not (await session.execute(stmt)).scalar():
                    logger.info("Creating test-user...")
                    u = User(
                        id="test-user", 
                        email="test@example.com", 
                        tenant_id="test-tenant", 
                        display_name="Test User",
                        roles=["user"]
                    )
                    session.add(u)

                await session.commit()
            
            await database.disconnect()
            logger.info("✓ Initial data seeded successfully")
            return True
        except Exception as e:
            logger.error(f"✗ Seeding failed: {e}")
            return False

    async def reset_database(self) -> bool:
        """
        Drop all tables and recreate schema.

        WARNING: This deletes all data. Only for development!

        Returns:
            bool: True if successful
        """
        if not self.settings.is_development:
            logger.error("✗ Cannot reset database outside of development environment")
            return False

        logger.warning("⚠️  RESETTING DATABASE - ALL DATA WILL BE DELETED")
        try:
            from src.storage.database import database
            from src.storage.models import Base

            await database.connect()
            async with database.engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)
            await database.disconnect()
            
            logger.info("✓ Database reset completed")
            return True
        except Exception as e:
            logger.error(f"✗ Database reset failed: {e}")
            return False

    async def check_connection(self) -> bool:
        """
        Test database connection.

        Returns:
            bool: True if connection successful
        """
        logger.info("Checking database connection...")
        try:
            from src.storage.database import database
            from sqlalchemy import text

            await database.connect()
            async with database.session() as session:
                result = await session.execute(text("SELECT 1"))
                if result.scalar() == 1:
                    logger.info("✓ Database connection successful")
                else:
                    logger.error("✗ Database connection test returned unexpected result")
                    return False
            await database.disconnect()
            return True
        except Exception as e:
            logger.error(f"✗ Database connection failed: {e}")
            return False


async def main(command: Optional[str] = None) -> int:
    """
    Main entry point.

    Args:
        command: Command to run (init, migrate, seed, reset, check)

    Returns:
        int: Exit code (0 = success, 1 = failure)
    """
    if command is None:
        if len(sys.argv) > 1:
            command = sys.argv[1]
        else:
            command = "check"

    logger.info(f"Database setup (environment: {settings.environment})")
    logger.info(f"Database: {settings.database.host}:{settings.database.port}/{settings.database.database}")
    logger.info("-" * 60)

    setup = DatabaseSetup()

    try:
        if command == "init":
            success = await setup.init_schema()
        elif command == "migrate":
            success = await setup.run_migrations()
        elif command == "seed":
            success = await setup.seed_initial_data()
        elif command == "reset":
            success = await setup.reset_database()
        elif command == "check":
            success = await setup.check_connection()
        else:
            logger.error(f"Unknown command: {command}")
            logger.info("Available commands: init, migrate, seed, reset, check")
            return 1

        logger.info("-" * 60)
        return 0 if success else 1

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
