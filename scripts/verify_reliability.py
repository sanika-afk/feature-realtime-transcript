import asyncio
import os
import secrets
from app.gemini_client import GeminiClient
from dotenv import load_dotenv

async def verify_parsing():
    load_dotenv()
    client = GeminiClient()
    
    print(f"--- Verifying Analysis Reliability (Model: {client.model_id}) ---")
    
    # Create a dummy image (1x1 black pixel)
    dummy_frame = b'\xff\xd8\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x08\x01\x01\x00\x00?\x00\x14\xdf\xff\xd9'
    
    try:
        result = await client.analyze_frame(dummy_frame, audio_transcript="Test transcript")
        
        if "error_info" in result:
            print(f"FAILED: {result['error_info']}")
            print(f"Raw Response: {result.get('raw_response')}")
        else:
            print("SUCCESS: JSON parsed successfully")
            print(f"Person Count: {result.get('person_count')}")
            print(f"HIPAA Score: {result.get('hipaa_compliance', {}).get('compliance_score')}")
            
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(verify_parsing())
