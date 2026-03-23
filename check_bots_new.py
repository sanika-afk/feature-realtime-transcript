import asyncio
import json
from app.recall_client import RecallAIClient

async def check():
    client = RecallAIClient()
    try:
        data = await client.list_bots()
        bots = data.get('results', [])
        print(f"Total Bots: {len(bots)}")
        for b in bots:
            bid = b.get('id')
            status = b.get('status')
            config = b.get('recording_config', {})
            endpoints = config.get('realtime_endpoints', [])
            
            ws_endpoints = [e for e in endpoints if e.get('type') == 'websocket']
            has_ws = len(ws_endpoints) > 0
            url = ws_endpoints[0].get('url') if has_ws else "N/A"
            
            print(f"- Bot {bid}: Status={status}, HasWS={has_ws}, URL={url}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check())
