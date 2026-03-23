import asyncio
import aiohttp
import sys

async def check_endpoints():
    base_url = "http://127.0.0.1:8000"
    print(f"Checking API at {base_url}...")

    async with aiohttp.ClientSession() as session:
        # 1. Check Health
        try:
            async with session.get(f"{base_url}/health") as resp:
                print(f"Health Check: {resp.status}")
                if resp.status == 200:
                    print(await resp.json())
        except Exception as e:
            print(f"Health Check Failed: {e}")

        # 2. Check Transcript History
        try:
            async with session.get(f"{base_url}/api/live/transcript-history") as resp:
                print(f"Transcript History: {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    print(f"History Entries: {len(data.get('entries', []))}")
                    print(f"Total: {data.get('total')}")
        except Exception as e:
            print(f"History Check Failed: {e}")

        # 3. Check WebSocket Analysis
        ws_url = "ws://127.0.0.1:8000/api/live/ws/analysis"
        try:
            async with session.ws_connect(ws_url) as ws:
                print("WebSocket Analysis: Connected")
                
                # Wait for history_init event
                msg = await ws.receive()
                if msg.type == aiohttp.WSMsgType.TEXT:
                    print(f"WebSocket Message: {msg.data[:100]}...")
                
                # Simulate sending a client message (e.g. heartbeat or config) if needed
                # await ws.send_str('{"event": "ping"}')

                await ws.close()
                print("WebSocket Analysis: Closed")
        except Exception as e:
            print(f"WebSocket Check Failed: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check_endpoints())
