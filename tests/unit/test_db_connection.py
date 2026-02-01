#!/usr/bin/env python3
import asyncio
import asyncpg
import sys

async def test_connection():
    # Test Unix socket
    print("Testing Unix socket connection...")
    try:
        conn = await asyncpg.connect(
            user='canva_user',
            password='canva_password_dev',
            database='canva_notebooklm_db',
            unix_socket_path='/tmp/.s.PGSQL.5432'
        )
        result = await conn.fetchval("SELECT 'Unix socket works!'")
        print(f"✓ Unix socket: {result}")
        await conn.close()
        return True
    except Exception as e:
        print(f"✗ Unix socket failed: {e}")
    
    # Test TCP
    print("\nTesting TCP connection...")
    try:
        conn = await asyncpg.connect(
            user='canva_user',
            password='canva_password_dev',
            database='canva_notebooklm_db',
            host='127.0.0.1',
            port=5432,
            timeout=5
        )
        result = await conn.fetchval("SELECT 'TCP works!'")
        print(f"✓ TCP: {result}")
        await conn.close()
        return True
    except Exception as e:
        print(f"✗ TCP failed: {e}")
    
    # Test Docker internal hostname
    print("\nTesting Docker hostname (canva-notebooklm-postgres)...")
    try:
        conn = await asyncpg.connect(
            user='canva_user',
            password='canva_password_dev',
            database='canva_notebooklm_db',
            host='canva-notebooklm-postgres',
            port=5432,
            timeout=5
        )
        result = await conn.fetchval("SELECT 'Docker hostname works!'")
        print(f"✓ Docker hostname: {result}")
        await conn.close()
        return True
    except Exception as e:
        print(f"✗ Docker hostname failed: {e}")
    
    return False

if __name__ == '__main__':
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)
