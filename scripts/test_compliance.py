import asyncio
import json
import base64
import websockets
import sys
import httpx

async def test_compliance():
    # URL of our local server (port 8000 as specified by user)
    RECALL_WS_URL = "ws://localhost:8000/api/live/ws/recall"
    ANALYSIS_WS_URL = "ws://localhost:8000/api/live/ws/analysis"
    STATS_URL = "http://localhost:8000/api/live/stats"

    print("--- Starting Compliance Pipeline Test ---")

    try:
        async with websockets.connect(ANALYSIS_WS_URL) as analysis_ws:
            print("Connected to Analysis WebSocket (subscriber)")

            async with websockets.connect(RECALL_WS_URL) as recall_ws:
                print("Connected to Recall WebSocket (sender)")

                # 1. Send a mock frame
                red_pixel_b64 = "iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAYAAABw4pVUAAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH5QYFCQ0Xp3unvAAAADJJREFUaN7tyEEJAAAIBDDTv7QpDMcNCPYmS7K766ququqqqqqqqqqqqqqqqqqqqqqqqqrqXj8P7mH0UAAAAABJRU5ErkJggg=="
                frame_event = {
                    "event": "video_separate_png.data",
                    "data": {
                        "data": red_pixel_b64,
                        "timestamp": 123456789.0
                    }
                }
                await recall_ws.send(json.dumps(frame_event))
                print("Sent mock frame")

                # 2. Send partial transcripts
                partials = ["This is a", "test of the", "compliance analysis"]
                for p in partials:
                    event = {
                        "event": "transcript.partial_data",
                        "data": {"text": p}
                    }
                    await recall_ws.send(json.dumps(event))
                    print(f"Sent partial: {p}")
                    await asyncio.sleep(0.1)

                # 3. Send final transcript
                final_event = {
                    "event": "transcript.data",
                    "data": {"text": "This is a test of the compliance analysis system."}
                }
                await recall_ws.send(json.dumps(final_event))
                print("Sent final transcript")

                # 4. Check stats
                print("Checking server stats...")
                try:
                    stats_resp = httpx.get(STATS_URL)
                    print(f"Server Stats: {stats_resp.json()}")
                except Exception as e:
                    print(f"Could not fetch stats: {e}")

                # 5. Wait for analysis response
                print("Waiting for compliance analysis result (timeout 30s)...")
                try:
                    while True:
                        response_raw = await asyncio.wait_for(analysis_ws.recv(), timeout=30.0)
                        response = json.loads(response_raw)
                        print(f"Received event: {response.get('event')}")
                        if response.get("event") == "compliance_analysis":
                            print("\nSUCCESS: Received compliance analysis!")
                            print(json.dumps(response, indent=2))
                            return
                        elif response.get("event") == "compliance_error":
                            print("\nFAILURE: Received compliance error:")
                            print(json.dumps(response, indent=2))
                            return
                except asyncio.TimeoutError:
                    print("\nTIMEOUT: No analysis received within 30 seconds.")
    except Exception as e:
        print(f"Test error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_compliance())
