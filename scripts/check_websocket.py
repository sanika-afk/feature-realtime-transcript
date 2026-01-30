#!/usr/bin/env python3
"""
Quick script to test if the WebSocket endpoint accepts connections.
Usage:
  python scripts/check_websocket.py                    # test Recall endpoint (default)
  python scripts/check_websocket.py --analysis       # test analysis endpoint
  python scripts/check_websocket.py --url ws://localhost:8000/api/live/ws/recall
"""
import argparse
import asyncio
import sys


async def check(url: str, wait_seconds: float = 2.0) -> bool:
    try:
        import websockets
    except ImportError:
        print("Install websockets: pip install websockets")
        return False

    print(f"Connecting to {url} ...")
    try:
        async with asyncio.timeout(10):
            async with websockets.connect(url) as ws:
                print("Connected.")
                if wait_seconds > 0:
                    print(f"Waiting {wait_seconds}s for messages (Ctrl+C to skip) ...")
                    try:
                        async with asyncio.timeout(wait_seconds):
                            msg = await ws.recv()
                            print(f"Received: {msg[:200]}{'...' if len(msg) > 200 else ''}")
                    except asyncio.TimeoutError:
                        pass
                return True
    except asyncio.TimeoutError:
        print("Timeout: server did not respond in 10s.")
        return False
    except Exception as e:
        print(f"Failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Check if WebSocket endpoint is reachable.")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL (e.g. http://localhost:8000 or https://your-ngrok.dev)",
    )
    parser.add_argument(
        "--recall",
        action="store_true",
        default=True,
        help="Test /api/live/ws/recall (default)",
    )
    parser.add_argument(
        "--analysis",
        action="store_true",
        help="Test /api/live/ws/analysis",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Do not wait for messages after connecting",
    )
    args = parser.parse_args()

    base = args.url.rstrip("/").replace("https://", "wss://").replace("http://", "ws://")
    if args.analysis:
        url = f"{base}/api/live/ws/analysis"
    else:
        url = f"{base}/api/live/ws/recall"

    ok = asyncio.run(check(url, wait_seconds=0 if args.no_wait else 2.0))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
