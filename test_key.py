import httpx
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test_key():
    api_key = os.getenv("RECALL_AI_API_KEY")
    url = "https://us-west-2.recall.ai/api/v1/bot/"
    headers = {
        "Authorization": f"Token {api_key}",
        "accept": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            print(f"Testing API Key: {api_key[:5]}...")
            response = await client.get(url, headers=headers, timeout=10.0)
            print(f"Status Code: {response.status_code}")
            print(f"Response Body: {response.text}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_key())
