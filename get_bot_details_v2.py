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
            
            print(f"\n=== Bot {bid} Details ===")
            print(f"Status: {details.get('status')}")
            print(f"Meeting URL: {details.get('meeting_url')}")
            
            # Transcription Config check
            transcription = details.get('transcription')
            print(f"Top-level 'transcription': {json.dumps(transcription, indent=2)}")
            
            # Recording Config check
            recording_config = details.get('recording_config', {})
            transcript_config = recording_config.get('transcript')
            print(f"recording_config['transcript']: {json.dumps(transcript_config, indent=2)}")
            
            # Endpoints check
            endpoints = recording_config.get('realtime_endpoints', [])
            for i, ep in enumerate(endpoints):
                print(f"Endpoint {i} ({ep.get('type')}): events={ep.get('events')}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check())
