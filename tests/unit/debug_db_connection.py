#!/usr/bin/env python3
"""Debug asyncpg vs psql connection issue."""

import asyncio
import asyncpg
import subprocess

def test_psql():
    """Test with psql."""
    result = subprocess.run(
        ['docker', 'exec', 'canva-notebooklm-postgres', 'psql', '-U', 'postgres', '-c', 'SELECT version();'],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print("✓ psql works")
        print(f"  Output: {result.stdout.split('(')[0].strip()[:80]}...")
    else:
        print(f"✗ psql failed: {result.stderr}")

async def test_asyncpg():
    """Test with asyncpg."""
    try:
        conn = await asyncpg.connect(
            user='postgres',
            password='postgres_dev_password',
            database='canva_notebooklm_db',
            host='127.0.0.1',
            port=5432,
            timeout=5,
            command_timeout=5
        )
        result = await conn.fetchval('SELECT version();')
        print("✓ asyncpg works")
        print(f"  Result: {str(result)[:80]}...")
        await conn.close()
    except Exception as e:
        print(f"✗ asyncpg failed")
        print(f"  Error: {type(e).__name__}: {e}")
        
        # Try with explicit connection parameters debug
        print(f"\n  Connection details:")
        print(f"    User: postgres")
        print(f"    Host: 127.0.0.1:5432")
        print(f"    Database: canva_notebooklm_db")

if __name__ == '__main__':
    print("Testing database connectivity:\n")
    test_psql()
    print()
    asyncio.run(test_asyncpg())
