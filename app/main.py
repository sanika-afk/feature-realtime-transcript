from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, Response
from pathlib import Path
from app.routes import bots, rtmp
from app.config import settings
import httpx

app = FastAPI(
    title="Universal Meeting Bot",
    description="API for streaming live meetings via Recall.ai",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(bots.router)
app.include_router(rtmp.router)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Universal Meeting Bot API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "create_bot": "/api/bots/",
            "list_bots": "/api/bots/",
            "get_bot": "/api/bots/{bot_id}",
            "delete_bot": "/api/bots/{bot_id}"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/favicon.ico")
async def favicon():
    """Return empty favicon to avoid 404 errors."""
    return Response(content=b"", media_type="image/x-icon")


@app.get("/viewer")
async def stream_viewer():
    """Serve the stream viewer HTML page."""
    viewer_path = Path("stream_viewer.html")
    if viewer_path.exists():
        return FileResponse(viewer_path)
    return {"error": "Stream viewer not found"}


@app.get("/hls/{stream_key:path}")
async def proxy_hls_stream(stream_key: str):
    """
    Proxy HLS stream from nginx-rtmp with CORS headers.
    This solves CORS issues when accessing HLS from the browser.
    """
    wsl_ip = "172.31.88.58"
    
    # Handle nested HLS structure (hls_nested on)
    # Paths can be:
    # - For .m3u8: "meeting-5" -> "/hls/meeting-5/index.m3u8"
    # - For .ts: "meeting-5/1234567890.ts" -> "/hls/meeting-5/1234567890.ts"
    
    is_ts = stream_key.endswith('.ts')
    is_m3u8_request = stream_key.endswith('.m3u8') or (not is_ts and '/' not in stream_key)
    base_key = None  # Will be set for .m3u8 requests
    
    if is_m3u8_request:
        # For .m3u8 requests, extract base key
        base_key = stream_key.replace('.m3u8', '').replace('/index', '')
        possible_paths = [
            f"/hls/{base_key}/index.m3u8",  # Nested structure (hls_nested on) - most likely
            f"/hls/{base_key}.m3u8",  # Flat structure
            f"/live/hls/{base_key}/index.m3u8",
            f"/stream/hls/{base_key}/index.m3u8",
        ]
    elif is_ts:
        # For .ts files, the path might already include the directory
        # e.g., "meeting-5/1234567890.ts" or just "1234567890.ts"
        if '/' in stream_key:
            # Already has directory: "meeting-5/1234567890.ts"
            possible_paths = [
                f"/hls/{stream_key}",  # Direct path
                f"/live/hls/{stream_key}",
                f"/stream/hls/{stream_key}",
            ]
        else:
            # Just filename, need to try with common stream keys
            # This is less common but possible
            possible_paths = [
                f"/hls/{stream_key}",  # Flat structure
            ]
    else:
        # Default: assume it's a stream key for .m3u8
        base_key = stream_key
        possible_paths = [
            f"/hls/{base_key}/index.m3u8",
            f"/hls/{base_key}.m3u8",
        ]
    
    # Determine content type
    content_type = "application/vnd.apple.mpegurl" if is_m3u8_request else "video/mp2t"
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        last_error = None
        for path in possible_paths:
            stream_url = f"http://{wsl_ip}:8080{path}"
            try:
                # For .m3u8 files, fetch the complete content (HLS.js needs full manifest)
                # For .ts files, we can stream
                if is_m3u8_request:
                    response = await client.get(stream_url)
                    response.raise_for_status()
                    # Rewrite URLs in m3u8 to use our proxy
                    content = response.text
                    # Replace any absolute paths to WSL IP with our proxy
                    content = content.replace(f'http://{wsl_ip}:8080/hls/', '/hls/')
                    content = content.replace(f'http://{wsl_ip}:8080/live/', '/hls/')
                    content = content.replace(f'http://{wsl_ip}:8080/stream/', '/hls/')
                    # For nested structure, ensure relative .ts paths work correctly
                    # The .m3u8 file should already have relative paths like "1234567890.ts"
                    # which will be requested as /hls/{base_key}/1234567890.ts
                    
                    return Response(
                        content=content.encode('utf-8'),
                        media_type=content_type,
                        headers={
                            "Access-Control-Allow-Origin": "*",
                            "Cache-Control": "no-cache, no-store, must-revalidate",
                            "Pragma": "no-cache",
                            "Expires": "0"
                        }
                    )
                else:
                    # For .ts segments, stream the response
                    async def generate():
                        # Create a new client for streaming to ensure it stays open
                        # during the entire streaming process
                        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as stream_client:
                            async with stream_client.stream("GET", stream_url) as stream_response:
                                stream_response.raise_for_status()
                                async for chunk in stream_response.aiter_bytes():
                                    yield chunk
                    
                    return StreamingResponse(
                        generate(),
                        media_type=content_type,
                        headers={
                            "Access-Control-Allow-Origin": "*",
                            "Cache-Control": "no-cache, no-store, must-revalidate",
                            "Pragma": "no-cache",
                            "Expires": "0"
                        }
                    )
            except httpx.HTTPStatusError as e:
                last_error = f"Path {path}: {e.response.status_code}"
                continue
            except httpx.RequestError as e:
                last_error = f"Path {path}: {str(e)}"
                continue
        
        # If all paths failed, return error
        raise HTTPException(
            status_code=404, 
            detail=f"HLS stream not found. Tried: {', '.join(possible_paths)}. Last error: {last_error}"
        )

@app.get("/rtmp/status")
async def check_rtmp_status():
    """Check RTMP server status"""

    wsl_ip = "172.31.88.58" 


    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"http://{wsl_ip}:8080/stat", timeout=5.0)
            return {
                "status": "running",
                "rtmp_url": f"rtmp://{wsl_ip}:1935/live",
                "public_rtmp_url": settings.PUBLIC_RTMP_URL,
                "stats_url": f"http://{wsl_ip}:8080/stat",
                "wsl_ip": wsl_ip
            }
        except:
            return {"status": "not_running"}
