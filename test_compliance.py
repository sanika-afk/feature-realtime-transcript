import asyncio
import json
import base64
import time
import websockets
import os

async def test_compliance_pipeline():
    """
    Simulate Recall.ai WebSocket events to verify the compliance pipeline.
    Expects the server to be running on localhost:8000.
    """
    uri = "ws://localhost:8000/api/live/ws/recall"
    
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected!")
            
            # 1. Send Mock Audio (1 second of silence)
            audio_data = b'\x00' * 32000 # 1s of 16kHz mono PCM
            audio_event = {
                "event": "audio_mixed_raw.data",
                "data": base64.b64encode(audio_data).decode('utf-8')
            }
            await websocket.send(json.dumps(audio_event))
            print("Sent audio_mixed_raw.data")
            
            # 2. Send Mock Video Frame (small clear PNG - 64x64 white block)
            png_str = (
                "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAAAAACPAi4CAAAAL0lEQVRo"
                "Q+3OAREAAAQDsFv/qlvYAxmYwMmqRETEhISEhISEhISEhISEhISEhI"
                "SEhISEC6pLAn65o0Y5AAAAAElFTkSuQmCC"
            )
            png_data = base64.b64decode(png_str)
            video_event = {
                "event": "video_separate_png.data",
                "data": base64.b64encode(png_data).decode('utf-8')
            }
            await websocket.send(json.dumps(video_event))
            print("Sent video_separate_png.data")
            
            # Let the buffer fill a bit
            await asyncio.sleep(1)
            
            # 3. Send Final Transcript
            transcript_event = {
                "event": "transcript.data",
                "data": {
                    "text": "The patient reports feeling much better today after starting the new medication.",
                    "speaker": "speaker_0", # Doctor
                    "transcript_id": "test_seg_001"
                }
            }
            await websocket.send(json.dumps(transcript_event))
            print("Sent transcript.data")
            
            # 4. Wait and listen for compliance event broadcast (optional)
            # This would require connecting another websocket to /api/live/ws/analysis
            print("Waiting for server to process...")
            await asyncio.sleep(5)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_compliance_pipeline())
