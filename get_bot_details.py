import asyncio
import json
from app.recall_client import RecallAIClient

async def check():
    client = RecallAIClient()
    try:
        data = await client.list_bots()
        bots = data.get('results', [])
        active_bots = [b for b in bots if b.get('status') not in ['done', 'failed']]
        
        if not active_bots:
            print("No active bots found.")
            return

        for b in active_bots:
            bid = b.get('id')
            # Fetch full details
            details = await client.get_bot(bid)
            config = details.get('transcription', {})
            print(f"Bot {bid} Details:")
            print(f"- Transcription Config: {json.dumps(config, indent=2)}")
            print(f"- Status: {details.get('status')}")
            print(f"- Meeting URL: {details.get('meeting_url')}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check())
