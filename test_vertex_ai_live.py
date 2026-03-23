#!/usr/bin/env python3
"""
Test Vertex AI analysis in live.py by sending sample WebSocket events.
Simulates Recall.ai sending frame + transcript, triggering Vertex AI analysis.
"""
import asyncio
import websockets
import json
import base64
from PIL import Image
import io

async def test_vertex_ai_live():
    """Send test events to /api/live/ws/recall and monitor stats."""
    
    # Create a simple test image (160x90 red frame)
    img = Image.new('RGB', (160, 90), color=(255, 0, 0))
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    frame_data = base64.b64encode(img_bytes.getvalue()).decode('utf-8')
    
    # Connect to the WebSocket
    ws_url = "ws://localhost:8000/api/live/ws/recall"
    print(f"[TEST] Connecting to {ws_url}...")
    
    try:
        async with websockets.connect(ws_url) as ws:
            print("[TEST] Connected! Sending events...")
            
            # Send video frame
            msg_video = {
                "event": "video_separate_png.data",
                "data": {
                    "data": frame_data
                }
            }
            await ws.send(json.dumps(msg_video))
            print("[TEST] Sent video frame")
            await asyncio.sleep(1)
            
            # Send partial transcript
            msg_partial = {
                "event": "transcript.partial_data",
                "data": {
                    "data": {
                        "text": "The patient needs antibiotics and rest for two weeks"
                    }
                }
            }
            await ws.send(json.dumps(msg_partial))
            print("[TEST] Sent partial transcript")
            await asyncio.sleep(1)
            
            # Send final transcript (triggers Vertex AI analysis)
            msg_final = {
                "event": "transcript.data",
                "data": {
                    "data": {
                        "text": "Doctor says: The patient needs antibiotics and rest for two weeks. Proper follow-up is essential."
                    }
                }
            }
            await ws.send(json.dumps(msg_final))
            print("[TEST] Sent final transcript - Vertex AI analysis should trigger!")
            
            # Keep connection open for a moment to let analysis complete
            await asyncio.sleep(3)
            
            print("[TEST] Closing WebSocket connection...")
            
    except Exception as e:
        print(f"[ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(test_vertex_ai_live())
    print("[TEST] Complete! Check http://localhost:8000/api/live/view to see results")
    print("[TEST] Also check http://localhost:8000/api/live/stats for latest_analysis data")
