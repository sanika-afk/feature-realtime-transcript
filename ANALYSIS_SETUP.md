# Real-time Video Analysis Setup Guide

This guide explains how to set up and use the real-time video analysis feature that analyzes RTMP streams using Google Cloud Video Intelligence API.

## Prerequisites

1. **Google Cloud Project** with Video Intelligence API enabled
2. **Service Account** with Video Intelligence API permissions
3. **FFmpeg** installed on your system
4. **Python dependencies** installed

## Setup Steps

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Google Cloud

1. Create a Google Cloud project (or use existing)
2. Enable the Video Intelligence API:
   ```bash
   gcloud services enable videointelligence.googleapis.com
   ```

3. Create a service account:
   ```bash
   gcloud iam service-accounts create video-analysis-sa \
     --display-name="Video Analysis Service Account"
   ```

4. Grant Video Intelligence API permissions:
   ```bash
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:video-analysis-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/videointelligence.admin"
   ```

5. Create and download service account key:
   ```bash
   gcloud iam service-accounts keys create credentials.json \
     --iam-account=video-analysis-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com
   ```

6. Place `credentials.json` in your project root or specify path in `.env`

### 3. Configure Environment Variables

Add to your `.env` file:

```env
GOOGLE_CLOUD_PROJECT_ID=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=./credentials.json
GOOGLE_CLOUD_LOCATION=us-central1
```

### 4. Install FFmpeg

**Windows:**
- Download from https://ffmpeg.org/download.html
- Add to PATH

**Linux/WSL:**
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

## Usage

### Start Analysis Session

```bash
POST /api/analysis/start/{stream_key}
```

**Parameters:**
- `stream_key`: The RTMP stream key to analyze
- `features` (optional): Comma-separated list: `object_tracking,label_detection,explicit_content`
- `fps` (optional): Frames per second to analyze (default: 1)

**Example:**
```bash
curl -X POST "http://localhost:8000/api/analysis/start/meeting-5?features=object_tracking,label_detection&fps=1"
```

**Response:**
```json
{
  "session_id": "meeting-5_1234567890.123",
  "stream_key": "meeting-5",
  "rtmp_url": "rtmp://172.31.88.58:1935/live/meeting-5",
  "features": ["STREAMING_OBJECT_TRACKING", "STREAMING_LABEL_DETECTION"],
  "fps": 1,
  "status": "started",
  "websocket_url": "/api/analysis/stream/meeting-5_1234567890.123"
}
```

### Connect to WebSocket for Real-time Results

Connect to the WebSocket URL to receive real-time analysis results:

```javascript
const ws = new WebSocket('ws://localhost:8000/api/analysis/stream/{session_id}');

ws.onmessage = (event) => {
  const result = JSON.parse(event.data);
  console.log('Analysis result:', result);
  
  if (result.type === 'analysis_result') {
    // Process analysis data
    const annotations = result.data.annotation_results;
    annotations.forEach(annotation => {
      if (annotation.objects) {
        console.log('Detected objects:', annotation.objects);
      }
      if (annotation.labels) {
        console.log('Detected labels:', annotation.labels);
      }
    });
  }
};
```

### Check Analysis Status

```bash
GET /api/analysis/status/{session_id}
```

### Stop Analysis

```bash
POST /api/analysis/stop/{session_id}
```

### List All Sessions

```bash
GET /api/analysis/sessions
```

## How It Works

The system streams video **directly** from RTMP to Google Cloud Video Intelligence API:
- **No frame extraction**: The video stream is sent as continuous chunks
- **Fragmented MP4 format**: FFmpeg converts RTMP to fragmented MP4 (fmp4) which Video Intelligence API expects
- **Real-time processing**: Video chunks are analyzed as they arrive
- **Low latency**: Uses `zerolatency` encoding preset for minimal delay

This approach is more efficient than extracting individual frames because:
1. **Lower CPU usage**: No need to decode/encode individual frames
2. **Better quality**: Original video quality is preserved
3. **Faster processing**: Video Intelligence API processes video streams more efficiently than individual frames
4. **Lower bandwidth**: Streamed video is more compact than individual JPEG frames

## Analysis Features

### Object Tracking
Tracks objects (people, vehicles, etc.) across video frames.

### Label Detection
Detects and labels objects, scenes, and activities in the video.

### Explicit Content Detection
Detects explicit content in the video stream.

## Example: Complete Analysis Flow

```python
import asyncio
import websockets
import json

async def analyze_stream(stream_key: str):
    # 1. Start analysis
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://localhost:8000/api/analysis/start/{stream_key}",
            params={"features": "object_tracking,label_detection", "fps": 1}
        )
        session = response.json()
        session_id = session["session_id"]
    
    # 2. Connect to WebSocket
    uri = f"ws://localhost:8000/api/analysis/stream/{session_id}"
    async with websockets.connect(uri) as websocket:
        print(f"Connected to analysis stream for {stream_key}")
        
        while True:
            try:
                message = await websocket.recv()
                result = json.loads(message)
                
                if result["type"] == "analysis_result":
                    print("Analysis result received:")
                    print(json.dumps(result["data"], indent=2))
                elif result["type"] == "error":
                    print(f"Error: {result["message"]}")
                    break
                    
            except websockets.exceptions.ConnectionClosed:
                print("Connection closed")
                break

# Run analysis
asyncio.run(analyze_stream("meeting-5"))
```

## Troubleshooting

### FFmpeg Not Found
- Ensure FFmpeg is installed and in your PATH
- Test with: `ffmpeg -version`

### Google Cloud Authentication Error
- Verify `GOOGLE_APPLICATION_CREDENTIALS` path is correct
- Check service account has proper permissions
- Ensure Video Intelligence API is enabled

### RTMP Stream Not Found
- Verify RTMP stream is active
- Check stream key is correct
- Ensure nginx-rtmp server is running

### No Analysis Results
- Check WebSocket connection is established
- Verify stream is actively streaming
- Check server logs for errors

## Cost Considerations

Google Cloud Video Intelligence API charges based on:
- Video duration analyzed
- Features used
- Number of requests

For real-time streaming:
- Object Tracking: $0.10 per minute
- Label Detection: $0.10 per minute
- Explicit Content: $0.10 per minute

Monitor usage in Google Cloud Console to avoid unexpected charges.

## Performance Tips

1. **Lower FPS**: Use `fps=1` or lower for cost savings
2. **Selective Features**: Only enable needed features
3. **Batch Processing**: Consider batch analysis for non-real-time use cases
4. **Connection Pooling**: Reuse WebSocket connections when possible
