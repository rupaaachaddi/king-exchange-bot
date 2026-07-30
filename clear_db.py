import asyncio
import motor.motor_asyncio
from dotenv import load_dotenv
import os

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")

async def clear_all():
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
    db = client["primebot"]

    collections = ["tickets", "counters", "rates", "wallets", "stats", "client_stats", "limits", "tax"]

    print("🗑️  Clearing all collections in 'primebot' database...\n")
    for col_name in collections:
        result = await db[col_name].delete_many({})
        print(f"  ✅ {col_name}: deleted {result.deleted_count} document(s)")

    print("\n✔️  Done! Database is clean.")
    client.close()

asyncio.run(clear_all())
