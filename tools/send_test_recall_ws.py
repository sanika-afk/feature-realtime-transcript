#!/usr/bin/env python3
"""Test client: connects to the app's Recall WebSocket endpoint and sends
one PNG frame and a transcript message so the /api/live/view shows "Connected".

Run from the project venv:

python tools/send_test_recall_ws.py
"""
import asyncio
import base64
import json
import time
import sys

import websockets
from io import BytesIO
from PIL import Image

WS_URL = "ws://localhost:8000/api/live/ws/recall"

async def send_test_events():
    print(f"Connecting to {WS_URL} ...")
    try:
        async with websockets.connect(WS_URL) as ws:
            print("Connected, sending test frame...")
            # Create a small PNG in memory
            img = Image.new('RGB', (160, 90), (255, 0, 0))
            buf = BytesIO()
            img.save(buf, format='PNG')
            png_bytes = buf.getvalue()
            b64 = base64.b64encode(png_bytes).decode('ascii')

            frame_msg = {
                "event": "video_separate_png.data",
                "data": {"data": b64}
            }
            await ws.send(json.dumps(frame_msg))
            print("Frame sent")

            # Send partial transcript
            await asyncio.sleep(0.2)
            partial = {"event": "transcript.partial_data", "data": {"data": {"text": "Hola, esto es una prueba parcial"}}}
            await ws.send(json.dumps(partial))
            print("Partial transcript sent")

            # Send final transcript
            await asyncio.sleep(0.5)
            final = {"event": "transcript.data", "data": {"data": {"text": "You need to take two tablets in the morning and one at night."}}}
            await ws.send(json.dumps(final))
            print("Final transcript sent")

            # Keep connection open briefly so server processes
            await asyncio.sleep(2)
    except Exception as e:
        print("Error:", e)
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(send_test_events())
