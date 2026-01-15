"""
Simple test script to create a bot and monitor its status.
Usage: python test_bot.py <meeting_url>
"""
import sys
import asyncio
import httpx
from app.config import settings


async def create_bot(meeting_url: str):
    """Create a bot and monitor its status."""
    api_url = f"http://{settings.SERVER_HOST}:{settings.SERVER_PORT}"
    
    print(f"Creating bot for meeting: {meeting_url}")
    print(f"API URL: {api_url}")
    print("-" * 50)
    
    async with httpx.AsyncClient() as client:
        # Create bot
        try:
            response = await client.post(
                f"{api_url}/api/bots/",
                json={
                    "meeting_url": meeting_url,
                    "video_layout": "gallery_view_v2",
                    "auto_leave": True
                },
                timeout=30.0
            )
            response.raise_for_status()
            bot_data = response.json()
            
            bot_id = bot_data["id"]
            print(f"✅ Bot created successfully!")
            print(f"Bot ID: {bot_id}")
            print(f"Status: {bot_data.get('status', 'unknown')}")
            print(f"Meeting URL: {bot_data.get('meeting_url', 'N/A')}")
            print("-" * 50)
            
            # Monitor bot status
            print("Monitoring bot status (press Ctrl+C to stop)...")
            print("-" * 50)
            
            while True:
                try:
                    status_response = await client.get(
                        f"{api_url}/api/bots/{bot_id}",
                        timeout=10.0
                    )
                    status_response.raise_for_status()
                    status_data = status_response.json()
                    
                    status = status_data.get("status", "unknown")
                    print(f"Status: {status}")
                    
                    if status_data.get("error_message"):
                        print(f"Error: {status_data['error_message']}")
                    
                    if status in ["left_meeting", "ended", "failed"]:
                        print(f"\nBot finished with status: {status}")
                        break
                    
                    await asyncio.sleep(5)
                    
                except KeyboardInterrupt:
                    print("\n\nStopping monitoring...")
                    print(f"Bot ID: {bot_id}")
                    print("You can check status later with:")
                    print(f"  curl {api_url}/api/bots/{bot_id}")
                    break
                except Exception as e:
                    print(f"Error checking status: {e}")
                    await asyncio.sleep(5)
        
        except httpx.HTTPStatusError as e:
            print(f"❌ Error creating bot: {e.response.status_code}")
            print(f"Response: {e.response.text}")
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_bot.py <meeting_url>")
        print("Example: python test_bot.py https://meet.google.com/abc-defg-hij")
        sys.exit(1)
    
    meeting_url = sys.argv[1]
    asyncio.run(create_bot(meeting_url))
