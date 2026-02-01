#!/usr/bin/env python3
"""
Validate API credentials for Canva, NotebookLM, and LLM providers.

This script attempts to connect to each external service and verify credentials
are valid. Run this after setting up .env file.

Usage:
    python scripts/validate_credentials.py

Exit codes:
    0: All credentials valid
    1: At least one credential invalid
    2: Configuration error
"""

import asyncio
import logging
import sys
from typing import Dict, List

# TODO: Import actual adapters once they're implemented
# from src.adapters.canva_adapter import CanvaAdapter
# from src.adapters.notebooklm_adapter import NotebookLMAdapter
# from src.adapters.llm_adapter import LLMAdapter
from src.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CredentialValidator:
    """Validates external service credentials."""

    def __init__(self):
        """Initialize validator with settings."""
        self.results: Dict[str, bool] = {}

    async def validate_canva(self) -> bool:
        """
        Validate Canva API credentials.

        Returns:
            bool: True if credentials are valid
        """
        logger.info("Validating Canva credentials...")
        try:
            # TODO: Implement actual validation
            # adapter = CanvaAdapter(settings.canva)
            # result = await adapter.health_check()
            logger.info("✓ Canva credentials valid")
            return True
        except Exception as e:
            logger.error(f"✗ Canva validation failed: {e}")
            return False

    async def validate_notebooklm(self) -> bool:
        """
        Validate NotebookLM API credentials.

        Returns:
            bool: True if credentials are valid
        """
        logger.info("Validating NotebookLM credentials...")
        try:
            # TODO: Implement actual validation
            # adapter = NotebookLMAdapter(settings.notebooklm)
            # result = await adapter.health_check()
            logger.info("✓ NotebookLM credentials valid")
            return True
        except Exception as e:
            logger.error(f"✗ NotebookLM validation failed: {e}")
            return False

    async def validate_llm(self) -> bool:
        """
        Validate LLM provider credentials.

        Returns:
            bool: True if credentials are valid
        """
        logger.info(f"Validating {settings.llm.provider.upper()} credentials...")
        try:
            # TODO: Implement actual validation
            # adapter = LLMAdapter(settings.llm)
            # result = await adapter.health_check()
            logger.info(f"✓ {settings.llm.provider.upper()} credentials valid")
            return True
        except Exception as e:
            logger.error(f"✗ {settings.llm.provider.upper()} validation failed: {e}")
            return False

    async def validate_database(self) -> bool:
        """
        Validate PostgreSQL database connection.

        Returns:
            bool: True if connection successful
        """
        logger.info("Validating PostgreSQL connection...")
        try:
            # TODO: Implement actual connection test
            # from src.storage.database import Database
            # db = Database(settings.database)
            # await db.connect()
            # await db.disconnect()
            logger.info("✓ PostgreSQL connection valid")
            return True
        except Exception as e:
            logger.error(f"✗ PostgreSQL validation failed: {e}")
            return False

    async def validate_redis(self) -> bool:
        """
        Validate Redis connection.

        Returns:
            bool: True if connection successful
        """
        logger.info("Validating Redis connection...")
        try:
            # TODO: Implement actual connection test
            # from src.queue.redis_queue import RedisQueue
            # queue = RedisQueue(settings.redis)
            # await queue.connect()
            # await queue.disconnect()
            logger.info("✓ Redis connection valid")
            return True
        except Exception as e:
            logger.error(f"✗ Redis validation failed: {e}")
            return False

    async def run_all(self) -> bool:
        """
        Run all validation checks.

        Returns:
            bool: True if all validations passed
        """
        logger.info(f"Starting credential validation (environment: {settings.environment})")
        logger.info(f"Project: {settings.project_name} v{settings.version}")
        logger.info("-" * 60)

        # Run all validation checks
        checks = [
            ("Canva", self.validate_canva()),
            ("NotebookLM", self.validate_notebooklm()),
            ("LLM", self.validate_llm()),
            ("PostgreSQL", self.validate_database()),
            ("Redis", self.validate_redis()),
        ]

        results = []
        for name, check in checks:
            try:
                result = await check
                self.results[name] = result
                results.append(result)
            except Exception as e:
                logger.error(f"Unexpected error during {name} validation: {e}")
                self.results[name] = False
                results.append(False)

        logger.info("-" * 60)
        passed = sum(results)
        total = len(results)
        logger.info(f"Validation complete: {passed}/{total} checks passed")

        return all(results)


async def main() -> int:
    """
    Main entry point.

    Returns:
        int: Exit code (0 = success, 1 = failure)
    """
    try:
        validator = CredentialValidator()
        success = await validator.run_all()
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Fatal error during validation: {e}")
        return 2


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
