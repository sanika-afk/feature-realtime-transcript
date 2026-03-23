"""
Example script to demonstrate real-time video analysis.
"""
import asyncio
import json
import httpx
import websockets
from typing import Optional


async def start_analysis(stream_key: str, base_url: str = "http://localhost:8000") -> Optional[str]:
    """Start analysis session and return session_id."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{base_url}/api/analysis/start/{stream_key}",
                params={
                    "features": "object_tracking,label_detection",
                    "fps": 1
                }
            )
            response.raise_for_status()
            session = response.json()
            print(f"✅ Analysis started for stream: {stream_key}")
            print(f"   Session ID: {session['session_id']}")
            print(f"   Features: {session['features']}")
            return session['session_id']
        except httpx.HTTPStatusError as e:
            print(f"❌ Error starting analysis: {e.response.status_code}")
            print(f"   {e.response.text}")
            return None


async def stream_analysis_results(session_id: str, base_url: str = "localhost:8000"):
    """Connect to WebSocket and stream analysis results."""
    uri = f"ws://{base_url}/api/analysis/stream/{session_id}"
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"✅ Connected to analysis stream")
            print(f"   Waiting for analysis results...\n")
            
            result_count = 0
            while True:
                try:
                    message = await websocket.recv()
                    result = json.loads(message)
                    
                    if result["type"] == "analysis_result":
                        result_count += 1
                        print(f"\n📊 Analysis Result #{result_count}")
                        print(f"   Timestamp: {result.get('timestamp', 'N/A')}")
                        
                        data = result.get("data", {})
                        annotations = data.get("annotation_results", [])
                        
                        for i, annotation in enumerate(annotations):
                            print(f"\n   Annotation #{i+1}:")
                            
                            # Object tracking results
                            if "objects" in annotation:
                                print(f"   🎯 Objects detected: {len(annotation['objects'])}")
                                for obj in annotation['objects'][:3]:  # Show first 3
                                    entity = obj.get('entity', {})
                                    print(f"      - {entity.get('description', 'Unknown')} "
                                          f"(confidence: {obj.get('confidence', 0):.2f})")
                            
                            # Label detection results
                            if "labels" in annotation:
                                print(f"   🏷️  Labels detected: {len(annotation['labels'])}")
                                for label in annotation['labels'][:3]:  # Show first 3
                                    print(f"      - {label.get('description', 'Unknown')} "
                                          f"(confidence: {label.get('confidence', 0):.2f})")
                            
                            # Explicit content results
                            if "explicit_content" in annotation:
                                exp = annotation['explicit_content']
                                likelihood = exp.get('pornography_likelihood', 'UNKNOWN')
                                print(f"   ⚠️  Explicit content: {likelihood}")
                    
                    elif result["type"] == "error":
                        print(f"❌ Error: {result.get('message', 'Unknown error')}")
                        break
                        
                except websockets.exceptions.ConnectionClosed:
                    print("\n🔌 WebSocket connection closed")
                    break
                except Exception as e:
                    print(f"❌ Error processing message: {e}")
                    break
                    
    except websockets.exceptions.InvalidURI:
        print(f"❌ Invalid WebSocket URI: {uri}")
    except Exception as e:
        print(f"❌ Error connecting to WebSocket: {e}")


async def check_status(session_id: str, base_url: str = "http://localhost:8000"):
    """Check analysis session status."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{base_url}/api/analysis/status/{session_id}")
            response.raise_for_status()
            status = response.json()
            print(f"\n📊 Session Status:")
            print(f"   Session ID: {status['session_id']}")
            print(f"   Stream Key: {status['stream_key']}")
            print(f"   Status: {status['status']}")
            print(f"   Features: {status['features']}")
        except Exception as e:
            print(f"❌ Error checking status: {e}")


async def stop_analysis(session_id: str, base_url: str = "http://localhost:8000"):
    """Stop analysis session."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{base_url}/api/analysis/stop/{session_id}")
            response.raise_for_status()
            result = response.json()
            print(f"✅ Analysis stopped: {result['status']}")
        except Exception as e:
            print(f"❌ Error stopping analysis: {e}")


async def main():
    """Main function to demonstrate analysis workflow."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python example_analysis.py <stream_key>")
        print("Example: python example_analysis.py meeting-5")
        sys.exit(1)
    
    stream_key = sys.argv[1]
    base_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000"
    ws_base_url = base_url.replace("http://", "").replace("https://", "")
    
    print("=" * 60)
    print("Real-time Video Analysis Example")
    print("=" * 60)
    print(f"Stream Key: {stream_key}")
    print(f"API Base URL: {base_url}\n")
    
    # Start analysis
    session_id = await start_analysis(stream_key, base_url)
    if not session_id:
        return
    
    try:
        # Stream results
        await stream_analysis_results(session_id, ws_base_url)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    finally:
        # Stop analysis
        print("\n🛑 Stopping analysis...")
        await stop_analysis(session_id, base_url)
        print("\n✅ Done!")


if __name__ == "__main__":
    asyncio.run(main())
