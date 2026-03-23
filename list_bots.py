import asyncio
from app.recall_client import RecallAIClient

async def main():
    client = RecallAIClient()
    resp = await client.list_bots()
    bots = resp.get('results', [])
    print(f"Total bots returned: {len(bots)}")
    for b in bots:
        print(f"Bot ID: {b['id']} | Status: {b['status']} | Created: {b['created_at']}")
        if b['status'] not in ['done', 'fatal']:
             print(f"  --> ACTIVE: {b['id']}")

if __name__ == "__main__":
    asyncio.run(main())
