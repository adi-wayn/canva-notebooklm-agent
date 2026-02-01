#!/usr/bin/env python3
"""
Test database fallback - verify SQLite fallback works when PostgreSQL is unavailable.
Run from the project root: python3 test_db_fallback.py
"""

import asyncio
import sys
import os

# Ensure we can import from src
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.storage.database import database
from src.config import settings

async def test_database_connection():
    """Test the database connection with fallback."""
    print("Testing Database Connection with Fallback\n")
    print(f"Configured PostgreSQL URL: {settings.database.url}")
    print(f"Fallback will use: sqlite+aiosqlite:////tmp/canva_dev.db\n")
    
    try:
        print("Attempting to connect to database...")
        await database.connect()
        print("\n✓ Database connection successful!")
        
        # Try a simple query via raw SQL
        async with database.session() as session:
            from sqlalchemy import text
            result = await session.execute(text("SELECT 1"))
            value = result.scalars().first()
            print(f"✓ Query test passed: {value}")
        
        await database.disconnect()
        print("\n✓ Database connection and queries working!")
        return True
        
    except Exception as e:
        print(f"\n✗ Database connection failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_database_connection())
    sys.exit(0 if success else 1)
