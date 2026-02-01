import asyncio
import sys
import os

# Add src to path
sys.path.append(os.getcwd())

from src.storage.database import database
from src.storage.repository import UserConnectionRepository
from datetime import datetime, timedelta, timezone

async def seed_token():
    print("Seeding mock token for test-user...")
    await database.connect()
    try:
        async with database.session() as session:
            repo = UserConnectionRepository(session, user_id="test-user", tenant_id="test-tenant")
            # Check if connection exists
            connection = await repo.get_connection("canva")
            expires_at = datetime.now(timezone.utc) + timedelta(days=365)
            if connection:
                print("Updating existing connection...")
                await repo.update_tokens(
                    provider="canva",
                    access_token="mock_access_token",
                    refresh_token="mock_refresh_token",
                    token_expires_at=expires_at
                )
            else:
                print("Creating new connection...")
                await repo.save_connection(
                    provider="canva",
                    access_token="mock_access_token",
                    refresh_token="mock_refresh_token",
                    token_expires_at=expires_at,
                    account_email="mock@test.com",
                    account_name="Mock User"
                )
            # Check if notebooklm connection exists
            connection = await repo.get_connection("notebooklm")
            if connection:
                print("Updating existing notebooklm connection...")
                await repo.update_tokens(
                    provider="notebooklm",
                    access_token="mock_nb_key",
                    refresh_token=None,
                    token_expires_at=expires_at
                )
            else:
                print("Creating new notebooklm connection...")
                await repo.save_connection(
                    provider="notebooklm",
                    access_token="mock_nb_key",
                    refresh_token=None,
                    token_expires_at=expires_at,
                    account_email="mock@test.com",
                    account_name="Mock User"
                )
            
            print("✅ Mock tokens seeded.")
    except Exception as e:
        print(f"❌ Failed to seed token: {e}")
    finally:
        await database.disconnect()

if __name__ == "__main__":
    asyncio.run(seed_token())
