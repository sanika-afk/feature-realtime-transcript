import asyncio
import json
from app.recall_client import RecallAIClient

async def check():
    client = RecallAIClient()
    try:
        data = await client.list_bots()
        bots = data.get('results', [])
        print(f"Total Active Bots: {len(bots)}")
        for b in bots:
            bid = b.get('id')
            status = b.get('status')
            config = b.get('recording_config', {})
            
            # Check transcript status if available
            transcript_config = config.get('transcript', {})
            provider = transcript_config.get('provider', {})
            
            print(f"- Bot {bid}: Status={status}")
            print(f"  Provider: {list(provider.keys())}")
            
            # If the bot is active, try to get more details
            if status in ['joining_call', 'in_call']:
                bot_details = await client.get_bot(bid)
                transcription_status = bot_details.get('transcription_status')
                print(f"  Transcription Status: {transcription_status}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check())
