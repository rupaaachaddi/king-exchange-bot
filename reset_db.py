import asyncio
import os
from dotenv import load_dotenv
import motor.motor_asyncio

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")

async def reset_db():
    print("Connecting to MongoDB...")
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
    db = client["primebot"]
    
    print("Dropping 'counters' collection (resets ticket numbers to 1)...")
    await db["counters"].drop()
    
    print("Dropping 'stats' collection (clears daily/weekly/monthly/lifetime stats)...")
    await db["stats"].drop()
    
    print("Dropping 'client_stats' collection (clears client deal history)...")
    await db["client_stats"].drop()
    
    # Optionally drop tickets to clear out old orphaned ticket data
    print("Dropping 'tickets' collection (clears open ticket DB records)...")
    await db["tickets"].drop()
    
    print("Reset complete!")

if __name__ == "__main__":
    asyncio.run(reset_db())
