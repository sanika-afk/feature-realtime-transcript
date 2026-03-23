"""
Google Cloud Video Intelligence API Streaming Client
For real-time video analysis of RTMP streams.
Streaming client is optional; app starts even if this package has no streaming API.
"""
import asyncio
import logging
from typing import AsyncIterator, Dict, Any, Optional, List, Iterator
import threading
from queue import Queue

logger = logging.getLogger(__name__)

# Streaming API may be in v1 or v1p3beta1 depending on package version
StreamingVideoIntelligenceServiceClient = None
StreamingAnnotateVideoRequest = None
StreamingVideoConfig = None
Feature = None
StreamingAnnotateVideoResponse = None

try:
    from google.cloud.videointelligence_v1 import StreamingVideoIntelligenceServiceClient as _StreamClient
    from google.cloud.videointelligence_v1.types import (
        StreamingAnnotateVideoRequest as _StreamReq,
        StreamingVideoConfig as _StreamConfig,
        Feature as _Feature,
        StreamingAnnotateVideoResponse as _StreamResp,
    )
    StreamingVideoIntelligenceServiceClient = _StreamClient
    StreamingAnnotateVideoRequest = _StreamReq
    StreamingVideoConfig = _StreamConfig
    Feature = _Feature
    StreamingAnnotateVideoResponse = _StreamResp
except ImportError:
    try:
        from google.cloud.videointelligence_v1p3beta1 import StreamingVideoIntelligenceServiceClient as _StreamClient
        from google.cloud.videointelligence_v1p3beta1.types import (
            StreamingAnnotateVideoRequest as _StreamReq,
            StreamingVideoConfig as _StreamConfig,
            StreamingAnnotateVideoResponse as _StreamResp,
        )
        from google.cloud.videointelligence_v1 import Feature as _Feature
        StreamingVideoIntelligenceServiceClient = _StreamClient
        StreamingAnnotateVideoRequest = _StreamReq
        StreamingVideoConfig = _StreamConfig
        Feature = _Feature
        StreamingAnnotateVideoResponse = _StreamResp
    except ImportError:
        pass


class VideoIntelligenceStreamingClient:
    """Client for Google Cloud Video Intelligence API Streaming."""
    
    def __init__(
        self,
        credentials_path: Optional[str] = None,
        project_id: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize the Video Intelligence Streaming client.
        
        Args:
            credentials_path: Path to Google Cloud service account JSON file (optional)
            project_id: Google Cloud project ID
            api_key: API key for Video Intelligence API (alternative to service account)
        """
        self.credentials_path = credentials_path
        self.project_id = project_id
        self.api_key = api_key
        self.client: Optional[StreamingVideoIntelligenceServiceClient] = None
        
        # Set credentials if provided (for service account)
        if credentials_path:
            import os
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
        
    def _get_client(self):
        """Get or create the streaming client."""
        if StreamingVideoIntelligenceServiceClient is None:
            raise RuntimeError(
                "Streaming Video Intelligence API is not available in this google-cloud-videointelligence version. "
                "Use Gemini Live (/api/live) for real-time analysis, or upgrade the package."
            )
        if self.client is None:
            if self.api_key and not self.credentials_path:
                logger.info("Using API key authentication. Note: Streaming API requires service account.")
            self.client = StreamingVideoIntelligenceServiceClient()
        return self.client
    
    def analyze_stream_sync(
        self,
        video_chunks: Iterator[bytes],
        features: List = None
    ) -> Iterator:
        """
        Analyze a video stream synchronously (for use with threading).
        
        Args:
            video_chunks: Iterator yielding video chunks (bytes)
            features: List of features to detect
        
        Yields:
            StreamingAnnotateVideoResponse objects with analysis results
        """
        if features is None and Feature is not None:
            features = [
                Feature.STREAMING_OBJECT_TRACKING,
                Feature.STREAMING_LABEL_DETECTION,
            ]
        elif features is None:
            features = []

        client = self._get_client()

        if StreamingVideoConfig is None or StreamingAnnotateVideoRequest is None:
            raise RuntimeError("Streaming types not available; use Gemini Live (/api/live) for real-time analysis.")

        # Configure streaming video
        config = StreamingVideoConfig()
        config.features = features
        
        def request_generator():
            # Send initial config
            yield StreamingAnnotateVideoRequest(video_config=config)
            
            # Send video chunks
            for chunk in video_chunks:
                yield StreamingAnnotateVideoRequest(input_content=chunk)
        
        # Stream to API and get responses
        try:
            responses = client.streaming_annotate_video(request_generator())
            for response in responses:
                yield response
        except Exception as e:
            logger.error(f"Error in video intelligence streaming: {e}")
            raise
    
    async def analyze_stream_async(
        self,
        video_stream: AsyncIterator[bytes],
        features: List = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Analyze a video stream asynchronously.
        Uses threading to bridge async/sync gap with gRPC.
        
        Args:
            video_stream: Async iterator yielding video chunks (bytes)
            features: List of features to detect
        
        Yields:
            Analysis results as dictionaries
        """
        if features is None and Feature is not None:
            features = [
                Feature.STREAMING_OBJECT_TRACKING,
                Feature.STREAMING_LABEL_DETECTION,
            ]
        elif features is None:
            features = []
        
        # Queue for video chunks
        chunk_queue = Queue()
        result_queue = Queue()
        
        # Thread to collect video chunks
        def collect_chunks():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                async def collect():
                    async for chunk in video_stream:
                        chunk_queue.put(chunk)
                    chunk_queue.put(None)  # Sentinel
                loop.run_until_complete(collect())
            finally:
                loop.close()
        
        # Thread to run analysis
        def run_analysis():
            try:
                def chunk_iterator():
                    while True:
                        chunk = chunk_queue.get()
                        if chunk is None:
                            break
                        yield chunk
                
                responses = self.analyze_stream_sync(chunk_iterator(), features)
                for response in responses:
                    result_queue.put(response)
                result_queue.put(None)  # Sentinel
            except Exception as e:
                logger.error(f"Error in analysis thread: {e}")
                result_queue.put(("error", str(e)))
        
        # Start threads
        collect_thread = threading.Thread(target=collect_chunks, daemon=True)
        analysis_thread = threading.Thread(target=run_analysis, daemon=True)
        
        collect_thread.start()
        analysis_thread.start()
        
        # Yield results asynchronously
        while True:
            result = result_queue.get()
            if result is None:
                break
            if isinstance(result, tuple) and result[0] == "error":
                raise Exception(result[1])
            
            # Convert response to dict
            yield self._response_to_dict(result)
    
    def _response_to_dict(self, response) -> Dict[str, Any]:
        """Convert StreamingAnnotateVideoResponse to dictionary."""
        result = {
            "annotation_results": []
        }
        
        if response.annotation_results:
            for annotation in response.annotation_results:
                annotation_dict = {}
                
                # Object tracking
                if annotation.object_annotations:
                    annotation_dict["objects"] = []
                    for obj in annotation.object_annotations:
                        annotation_dict["objects"].append({
                            "entity": {
                                "description": obj.entity.description,
                                "entity_id": obj.entity.entity_id,
                                "language_code": obj.entity.language_code
                            },
                            "confidence": obj.confidence,
                            "time_offset": {
                                "seconds": obj.time_offset.seconds,
                                "nanos": obj.time_offset.nanos
                            }
                        })
                
                # Label detection
                if annotation.label_annotations:
                    annotation_dict["labels"] = []
                    for label in annotation.label_annotations:
                        annotation_dict["labels"].append({
                            "description": label.entity.description,
                            "confidence": label.frames[0].confidence if label.frames else 0.0
                        })
                
                # Explicit content
                if annotation.explicit_annotation:
                    annotation_dict["explicit_content"] = {
                        "pornography_likelihood": annotation.explicit_annotation.frames[0].pornography_likelihood.name if annotation.explicit_annotation.frames else "UNKNOWN"
                    }
                
                result["annotation_results"].append(annotation_dict)
        
        return result
