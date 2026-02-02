
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from src.storage.database import database
from src.storage.repository import UserConnectionRepository

async def main():
    await database.connect()
    try:
        user_id = "test-user"
        tenant_id = "demo-tenant"
        
        async with database.session() as session:
            repo = UserConnectionRepository(session, user_id=user_id, tenant_id=tenant_id)
            connection = await repo.get_connection("canva")
            
            if not connection:
                print(f"No connection found for {user_id}")
                return
                
            print(f"Current expires_at: {connection.token_expires_at}")
            
            new_expiry = datetime.now(timezone.utc) + timedelta(days=1)
            
            # Using repository update method if available, or direct override if repo assumes valid refresh
            # Repo.update_tokens expects access_token and refresh_token too.
            # We'll keep existing ones.
            
            await repo.update_tokens(
                provider="canva",
                access_token=connection.access_token,
                refresh_token=connection.refresh_token,
                token_expires_at=new_expiry
            )
            
            print(f"Updated expires_at to: {new_expiry}")
            
    finally:
        await database.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
