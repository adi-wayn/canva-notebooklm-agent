
import asyncio
import sys
import os
from datetime import datetime

sys.path.append(os.getcwd())

from src.storage.database import database
from src.storage.repository import UserConnectionRepository
from sqlalchemy import text

async def diagnose():
    await database.connect()
    try:
        async with database.session() as session:
            result = await session.execute(text("SELECT user_id, tenant_id, provider, created_at, updated_at FROM user_connections"))
            rows = result.fetchall()
            print("--- User Connections ---")
            for row in rows:
                print(f"User: {row[0]} | Tenant: {row[1]} | Provider: {row[2]} | Updated: {row[4]}")
            
            if not rows:
                print("No connections found.")
                
    finally:
        await database.disconnect()

if __name__ == "__main__":
    asyncio.run(diagnose())
