# Universal Meeting Bot

A FastAPI application that uses Recall.ai to join meetings (Zoom, Google Meet, Teams, etc.) and stream them in real-time via RTMP.

## Features

- 🎥 Join meetings on multiple platforms (Zoom, Google Meet, Microsoft Teams, Webex, etc.)
- 📺 Real-time RTMP streaming (720p, 30fps)
- 🤖 Bot management API (create, list, get status, delete)
- 🎨 Configurable video layouts (speaker view or gallery view)
- 🔄 Automatic bot leaving when meeting ends

## Prerequisites

1. **Recall.ai Account**: Sign up at [recall.ai](https://recall.ai) and get your API key
2. **RTMP Server**: You'll need an RTMP server to receive streams. Options:
   - **nginx-rtmp** (recommended for local development)
   - **SRS (Simple Realtime Server)**
   - **Cloud services** like Mux, AWS MediaLive, etc.

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory:

```env
# Recall.ai API Configuration
RECALL_AI_API_KEY=your_recall_ai_api_key_here
RECALL_AI_BASE_URL=https://us-west-2.recall.ai/api/v1

# Server Configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# RTMP Configuration
RTMP_HOST=localhost
RTMP_PORT=1935
RTMP_APPLICATION=live
RTMP_STREAM_KEY_PREFIX=meeting

# Public RTMP URL (for production or ngrok)
# If using ngrok: PUBLIC_RTMP_URL=rtmp://your-ngrok-url.ngrok.io
PUBLIC_RTMP_URL=
```

### 3. Set Up RTMP Server (Local Development)

#### Option A: Using nginx-rtmp

1. Install nginx with RTMP module:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install nginx libnginx-mod-rtmp
   
   # macOS
   brew install nginx-full --with-rtmp-module
   ```

2. Configure nginx (`/etc/nginx/nginx.conf` or `/usr/local/etc/nginx/nginx.conf`):
   ```nginx
   rtmp {
       server {
           listen 1935;
           chunk_size 4096;
           
           application live {
               live on;
               record off;
               
               # Convert to HLS for web playback
               hls on;
               hls_path /tmp/hls;
               hls_fragment 3;
               hls_playlist_length 60;
           }
       }
   }
   
   http {
       server {
           listen 8080;
           
           location /hls {
               types {
                   application/vnd.apple.mpegurl m3u8;
                   video/mp2t ts;
               }
               root /tmp;
               add_header Cache-Control no-cache;
               add_header Access-Control-Allow-Origin *;
               
               # Optional: Enable directory listing for testing
               autoindex on;
           }
       }
   }
   ```

3. **For WSL users**: Since nginx is already running, you need to:
   
   a. First, check if RTMP module is installed:
   ```bash
   nginx -V 2>&1 | grep rtmp
   ```
   
   If not installed, install it:
   ```bash
   sudo apt-get update
   sudo apt-get install libnginx-mod-rtmp
   ```
   
   b. Add the HTTP server block for HLS playback inside the `http {}` section:
   ```nginx
   server {
       listen 8080;
       
       location /hls {
           types {
               application/vnd.apple.mpegurl m3u8;
               video/mp2t ts;
           }
           root /tmp;
           add_header Cache-Control no-cache;
           add_header Access-Control-Allow-Origin *;
       }
   }
   ```
   
   c. Create the HLS directory:
   ```bash
   sudo mkdir -p /tmp/hls
   sudo chmod 777 /tmp/hls
   ```
   
   d. Test configuration:
   ```bash
   sudo nginx -t
   ```
   
   e. Reload nginx (don't restart, just reload):
   ```bash
   sudo nginx -s reload
   # OR
   sudo systemctl reload nginx
   ```

4. **For fresh installs**: Start nginx:
   ```bash
   sudo nginx
   ```

#### Option B: Using SRS (Simple Realtime Server)

1. Install SRS: https://github.com/ossrs/srs
2. Configure and start SRS server

### 4. For Local Development with ngrok

Since Recall.ai needs to send RTMP streams to a publicly accessible URL, use ngrok for local development:

```bash
# Install ngrok
# Then expose your RTMP server
ngrok tcp 1935
```

Update your `.env`:
```env
PUBLIC_RTMP_URL=rtmp://your-ngrok-url.ngrok.io
```

## Running the Application

```bash
# Recommendation: Use 'localhost' on Windows for Cloudflare Tunnel compatibility
uvicorn app.main:app --reload --host localhost --port 8000
```

The API will be available at:
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Usage

### Create a Bot

```bash
curl -X POST "http://localhost:8000/api/bots/" \
  -H "Content-Type: application/json" \
  -d '{
    "meeting_url": "https://meet.google.com/abc-defg-hij",
    "video_layout": "gallery_view",
    "auto_leave": true
  }'
```

Response:
```json
{
  "id": "bot_123456",
  "status": "joining_meeting",
  "meeting_url": "https://meet.google.com/abc-defg-hij",
  "created_at": "2024-01-01T12:00:00Z"
}
```

### Get Bot Status

```bash
curl "http://localhost:8000/api/bots/bot_123456"
```

### List All Bots

```bash
curl "http://localhost:8000/api/bots/?limit=10&offset=0"
```

### Delete a Bot

```bash
curl -X DELETE "http://localhost:8000/api/bots/bot_123456"
```

## How It Works

1. **Create Bot**: Your API creates a bot via Recall.ai API with an RTMP endpoint
2. **Bot Joins Meeting**: Recall.ai bot joins the meeting as a participant
3. **Stream Capture**: Bot captures video + audio from the meeting
4. **RTMP Streaming**: Bot streams to your RTMP server at the configured URL
5. **View Stream**: You can view the stream via HLS (if configured) or convert to WebRTC

## Improving Transcription Accuracy

If the default transcription is not accurate enough for your meetings (especially for non-English languages like Hindi, Marathi, or Spanish), you can switch to a high-quality transcription provider.

The bot supports **Gladia** and **AssemblyAI** as alternatives to the default Recall engine.

### How to use a high-quality provider:

1. **Get an API Key** from [Gladia](https://gladia.io) or [AssemblyAI](https://assemblyai.com).
2. **Update your `.env` file**:

```env
# Switch the provider (options: recallai_streaming, gladia, assembly_ai)
TRANSCRIPTION_PROVIDER=gladia

# Add your API key
GLADIA_API_KEY=your_gladia_api_key_here
# ASSEMBLY_AI_API_KEY=your_assembly_ai_api_key_here
```

3. **Specify the Language** when creating the bot (e.g., `hi-IN` for Hindi, `mr-IN` for Marathi).

### Language Codes (Examples):
- English: `en-US`
- Hindi: `hi-IN`
- Marathi: `mr-IN`
- Spanish: `es-ES`

## Video Layouts

- **`speaker_view`**: Shows only the active speaker
- **`gallery_view_v2`**: Shows all participants in a grid layout

## Supported Platforms

According to Recall.ai documentation:
- ✅ Zoom
- ✅ Google Meet
- ✅ Microsoft Teams
- ✅ Cisco Webex (requires setup)
- ✅ Slack Huddles (Beta, requires setup)
- ✅ Go-To Meeting (Beta)

## RTMP Stream Specifications

- **Resolution**: 720p
- **Frame Rate**: 30 FPS
- **Format**: FLV (via RTMP)

## Next Steps

1. **View Streams**: Set up HLS conversion in your RTMP server to view streams in a web browser
2. **WebRTC**: Convert RTMP to WebRTC for lower latency viewing
3. **Recording**: Store streams for later playback
4. **Transcription**: Add real-time transcription using Recall.ai's transcription features
5. **Analytics**: Track meeting metrics and participant data

## Troubleshooting

### Bot Not Joining Meeting

- Check meeting URL is correct
- Verify Recall.ai API key is valid
- Check if meeting requires host approval
- Some platforms may require waiting room approval

### RTMP Stream Not Receiving

- Verify RTMP server is running and accessible
- Check firewall settings (port 1935)
- For local development, ensure ngrok is running and PUBLIC_RTMP_URL is set
- Verify RTMP URL format: `rtmp://host:port/application/stream_key`

### Stream Quality Issues

- RTMP streams are 720p, 30fps (fixed by Recall.ai)
- Check network bandwidth
- Verify RTMP server can handle the stream

## License

MIT
