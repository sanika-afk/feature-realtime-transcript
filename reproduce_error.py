import httpx
import asyncio

async def test_create_bot():
    url = "http://localhost:8000/api/bots/"
    payload = {
        "meeting_url": "https://meet.google.com/abc-defg-hij",
        "bot_name": "Test Bot"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            print(f"Sending POST to {url}...")
            response = await client.post(url, json=payload, timeout=30.0)
            print(f"Status Code: {response.status_code}")
            print(f"Response Body: {response.text}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_create_bot())
