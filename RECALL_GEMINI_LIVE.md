# Recall AI → WebSocket → Gemini Multimodal Live API

**Yes, it is possible** to receive the Recall AI stream over WebSocket and pass it to the Gemini Multimodal Live API for real-time meeting analysis.

Last checked: **29 January 2026**.

---

## Architecture

```
┌─────────────┐     WebSocket (wss)      ┌──────────────────┐     WebSocket      ┌─────────────────────┐
│  Recall AI  │ ──────────────────────► │  Your server     │ ─────────────────► │  Gemini Live API    │
│  (meeting   │  video / audio /         │  (FastAPI        │  JPEG @ 1 FPS +    │  (real-time         │
│   bot)      │  transcript events)      │   WebSocket)     │  transcript        │   multimodal        │
└─────────────┘                           └────────┬─────────┘                     └──────────┬──────────┘
                                                  │                                            │
                                                  │  analysis stream (WebSocket / SSE)          │
                                                  ▼                                            │
                                           ┌──────────────┐                                    │
                                           │  Dashboard   │◄───────────────────────────────────┘
                                           │  (HIPAA etc) │   real-time analysis
                                           └──────────────┘
```

---

## Recall AI – WebSocket streaming

- **Docs:** [Real-Time Websocket Endpoints](https://docs.recall.ai/docs/real-time-websocket-endpoints), [Real-Time Event Payloads](https://docs.recall.ai/docs/real-time-event-payloads).
- When creating a bot, set a **realtime endpoint** with `type: "websocket"` and your **public `wss://` URL**.
- Recall’s backend **connects to your URL** and pushes events as WebSocket messages.

### Event types you can use

| Event | Description |
|-------|-------------|
| `video_separate_png.data` | Per-participant video, PNG, ~2 FPS (360p) |
| `video_separate_h264.data` | Per-participant video, H.264 (200–1000px, 10–30 FPS; web4core) |
| `video_mixed_flv.data` | Mixed video+audio as FLV (over WebSocket if supported; otherwise use RTMP) |
| `audio_mixed_raw.data` | Mixed audio, base64 PCM 16 kHz mono |
| `transcript.data` | Final transcript utterances |
| `transcript.partial_data` | Partial transcript |

### Message format (high level)

```json
{
  "event": "event_type_string",
  "data": {
    "data": { /* event-specific (e.g. buffer, timestamp) */ },
    "realtime_endpoint": { "id": "...", "metadata": {} },
    "recording": { "id": "...", "metadata": {} },
    "bot": { "id": "...", "metadata": {} }
  }
}
```

Video/audio payloads typically include a **base64-encoded buffer** and **timestamp**.

---

## Gemini Multimodal Live API

- **Docs:** [Get started with Live API](https://ai.google.dev/gemini-api/docs/live), [Live API – WebSockets](https://ai.google.dev/api/live).
- **WebSocket endpoint (Google AI):**  
  `wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent`
- **Behavior:** Stateful, bidirectional WebSocket: you send setup (model, config, system instructions), then **real-time input** (text, audio, or **video as image frames**), and receive model responses in real time.

### Video input

- **Format:** Discrete **JPEG** (or supported image) frames.
- **Rate:** About **1 FPS** recommended.
- **Resolution:** e.g. 768×768 for good results (you can resize before sending).

### Python SDK

- Package: **`google-genai`** (not `google-generativeai` for the Live API).
- Example pattern:

```python
async with client.aio.live.connect(model='gemini-2.0-flash-live', config=config) as session:
    await session.send_realtime_input(media=types.Blob(data=jpeg_bytes, mime_type="image/jpeg"))
    async for message in session.receive():
        # handle analysis / tool calls
```

---

## Implementation choices in this repo

1. **Recall → your server**
   - **Option A – WebSocket only:** Create the bot with a **WebSocket** realtime endpoint; use events such as `video_separate_png.data` (and optionally `transcript.data`, `audio_mixed_raw.data`). Your server exposes a **WebSocket route** Recall connects to.
   - **Option B – RTMP (current):** Bot streams to RTMP; your server pulls the RTMP stream (e.g. with FFmpeg), decodes to frames, and feeds Gemini Live. No Recall WebSocket needed.

2. **Your server → Gemini Live**
   - Decode/sample video to **~1 FPS JPEG** (from Recall PNG, FLV, or RTMP).
   - Optionally send **transcript** (and/or audio) for context.
   - Use **`google-genai`** Live API over WebSocket to send frames and get **real-time analysis** (e.g. HIPAA/compliance, summarization).

3. **Session limits (Gemini Live)**
   - With video: typically short sessions (e.g. ~2 minutes) unless you use resumable sessions or chunk the meeting into segments.

---

## Summary

| Question | Answer |
|----------|--------|
| Can we get the Recall AI stream in WebSocket? | **Yes** – create the bot with `realtime_endpoints` `type: "websocket"` and your `wss://` URL. |
| Can we pass that to Gemini Multimodal Live API? | **Yes** – convert incoming video (e.g. PNG/FLV) to JPEG at ~1 FPS and send via the Live API WebSocket. |
| Real-time full meeting analysis? | **Yes** – Gemini Live returns analysis in real time; you can stream it to a dashboard or store it. |

This repo implements a **Recall WebSocket receiver**, a **Gemini Live client**, and a **bridge** that samples frames and streams analysis (see `app/routes/live.py`, `app/gemini_live_client.py`, and `app/recall_client.py`).

---

## How to run (this repo)

1. **Env**
   - `RECALL_AI_API_KEY`, `GEMINI_API_KEY`
   - `PUBLIC_WS_URL` = public WebSocket base URL (e.g. `wss://your-domain.com`) so Recall can connect to `/api/live/ws/recall`.

2. **Create bot with WebSocket**
   - `POST /api/live/bot` with body `{ "meeting_url": "https://meet.google.com/xxx", ... }` (same as `CreateBotRequest`).
   - Recall will connect to `PUBLIC_WS_URL/api/live/ws/recall` and push events.

3. **Receive real-time analysis**
   - Connect to `wss://your-server/api/live/ws/analysis` to get JSON analysis from Gemini Live.

4. **Dependencies**
   - `pip install google-genai` for the Live API (see `requirements.txt`).
