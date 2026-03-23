# Medical Meeting Bot - Implementation Guide

## Overview
This guide documents the recent enhancements to the Universal Meeting Bot for medical consultations with speaker detection, buffer management, and Vertex AI medical accuracy auditing.

---

## Key Changes

### 1. Speaker Detection & Buffer Management

#### Location: `app/speaker_detector.py`

**New Features:**
- **Speaker ID Mapping**: Automatically maps speaker IDs to roles
  - `speaker_0` → **Doctor**
  - `speaker_1` → **Interpreter**
- **Speaker Buffers**: Maintains separate buffers for doctor and interpreter text
- **Methods Added:**
  - `add_to_speaker_buffer(speaker_id, text)` - Add text to appropriate buffer
  - `get_doctor_buffer_text()` - Get concatenated doctor buffer
  - `get_interpreter_buffer_text()` - Get concatenated interpreter buffer
  - `get_all_buffers()` - Get all speaker buffers
  - `clear_buffers()` - Clear all buffers
  - `get_buffer_stats()` - Get buffer statistics

**Example Usage:**
```python
from app.speaker_detector import get_speaker_detector

detector = get_speaker_detector()

# Add text to buffers based on speaker ID
detector.add_to_speaker_buffer("speaker_0", "Take two tablets in the morning")
detector.add_to_speaker_buffer("speaker_1", "Necesita tomar dos pastillas por la mañana")

# Get buffer content
doctor_text = detector.get_doctor_buffer_text()
interpreter_text = detector.get_interpreter_buffer_text()

# Check statistics
stats = detector.get_buffer_stats()
# {
#   "doctor_segments": 1,
#   "interpreter_segments": 1,
#   "doctor_words": 6,
#   "interpreter_words": 7
# }
```

---

### 2. Vertex AI Medical Accuracy Audit

#### Location: `app/vertex_ai_client.py`

**New Method: `medical_accuracy_audit()`**

Performs comprehensive medical accuracy review on doctor and interpreter statements using Vertex AI Gemini 1.5 Pro.

**Parameters:**
- `doctor_buffer` (str): Concatenated doctor statements
- `interpreter_buffer` (str): Concatenated interpreter statements
- `frame_bytes` (Optional[bytes]): Video frame for context
- `mime_type` (str): Image MIME type (default: "image/png")

**Returns JSON Structure:**
```json
{
  "audit_status": "PASS|FAIL|WARNING",
  "overall_accuracy_score": 0-100,
  "sections": [
    {
      "section": "Medical Accuracy",
      "score": 0-100,
      "status": "PASS|FAIL|WARNING",
      "findings": ["finding1", "finding2"],
      "recommendations": ["action1", "action2"]
    }
  ],
  "critical_issues": [
    {
      "issue": "description",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "impact": "Patient Safety|Legal Compliance|Quality",
      "evidence": "quoted text",
      "recommendation": "corrective action"
    }
  ],
  "strengths": ["strength1", "strength2"],
  "summary": "executive summary of audit findings"
}
```

**Example Usage:**
```python
from app.vertex_ai_client import VertexAIClient

client = VertexAIClient(
    project_id="your-gcp-project",
    location="us-central1",
    model_id="gemini-1.5-pro"
)

# Run medical accuracy audit
audit_result = await client.medical_accuracy_audit(
    doctor_buffer="Take two tablets in the morning and one at night",
    interpreter_buffer="Necesita tomar dos pastillas por la mañana y una por la noche",
    frame_bytes=video_frame_bytes
)

print(f"Audit Status: {audit_result['audit_status']}")
print(f"Accuracy Score: {audit_result['overall_accuracy_score']}%")
```

---

### 3. Real-Time WebSocket Integration

#### Location: `app/routes/live.py`

**Changes to WebSocket Handler:**

1. **Speaker ID Extraction**
   - Now extracts `speaker` field from transcript payload
   - Maps to doctor/interpreter roles automatically

2. **Buffer Collection**
   - Transcript segments are automatically added to speaker-specific buffers
   - Maintains transcript history with speaker roles

3. **Example Flow:**
```python
# Incoming WebSocket message
{
  "event": "transcript.data",
  "data": {
    "speaker": "speaker_0",        # ← NEW: Speaker ID
    "text": "Take two tablets",
    "words": [...]
  }
}

# Automatic Processing:
# 1. Speaker ID "speaker_0" detected
# 2. Text added to doctor_buffer
# 3. Transcript history updated with speaker role
# 4. Vertex AI analysis triggered
```

---

### 4. New API Endpoints

#### Medical Audit Endpoint
**POST `/api/live/medical-audit`**

Manually trigger a medical accuracy audit on current speaker buffers.

**Response:**
```json
{
  "status": "audit_triggered",
  "buffer_stats": {
    "doctor_segments": 2,
    "interpreter_segments": 2,
    "doctor_words": 25,
    "interpreter_words": 28
  },
  "latest_analysis": {
    "audit_type": "medical_accuracy",
    "analysis": {...audit result...}
  }
}
```

#### Get Speaker Buffers
**GET `/api/live/buffers`**

Retrieve current speaker buffers and statistics.

**Response:**
```json
{
  "buffers": {
    "doctor": "Take two tablets in the morning...",
    "interpreter": "Necesita tomar dos pastillas...",
    "combined": "Doctor: ... | Interpreter: ..."
  },
  "stats": {
    "doctor_segments": 2,
    "interpreter_segments": 2,
    "doctor_words": 25,
    "interpreter_words": 28
  },
  "speaker_roles": {"speaker_0": "Doctor", "speaker_1": "Interpreter"},
  "transcript_history": [...]
}
```

#### Clear Speaker Buffers
**POST `/api/live/buffers/clear`**

Clear all speaker buffers and transcript history.

#### Get Transcript History
**GET `/api/live/transcript-history?limit=100`**

Retrieve transcript history with speaker information.

---

### 5. Enhanced UI Layout

#### Location: `app/routes/live.py` - `_viewer_html()`

**New Three-Column Layout:**

```
┌─────────────┬──────────────────┬──────────────────┐
│   LEFT      │    CENTER        │     RIGHT        │
│  PANEL      │    COLUMN        │     PANEL        │
├─────────────┼──────────────────┼──────────────────┤
│             │                  │                  │
│  Transcript │  Live Video      │  Compliance      │
│  & Speaker  │  Stream          │  Analysis        │
│             │                  │                  │
│  History    │                  │  Medical Audit   │
│  Panel      │                  │  Results         │
│             │                  │                  │
│ Medical     │  Current         │  Buffer Status   │
│ Audit       │  Speaker Txt     │  & Stats         │
│ Button      │                  │                  │
│             │                  │  Raw Stats       │
└─────────────┴──────────────────┴──────────────────┘
```

**Left Panel (350px width):**
- Transcript history with speaker badges
- Color-coded speakers:
  - 🔵 **Blue** - Doctor
  - 🟣 **Purple** - Interpreter
- Medical Audit button to trigger analysis

**Center Column:**
- Live video stream (MJPEG)
- Current speaker display
- Latest transcript

**Right Panel:**
- HIPAA/Compliance analysis results
- Medical accuracy audit results
- Buffer statistics (doctor/interpreter segments and word counts)
- Raw stream statistics

**Speaker Badges:**
```html
<span class="speaker-badge speaker-doctor">Doctor</span>
<span class="speaker-badge speaker-interpreter">Interpreter</span>
<span class="speaker-badge speaker-unknown">Unknown</span>
```

---

## Usage Workflow

### 1. Start a Meeting
```bash
curl -X POST http://localhost:8000/api/live/bot \
  -H "Content-Type: application/json" \
  -d '{"meeting_url": "https://zoom.us/..."}' 
```

### 2. View Live Stream
```
Open: http://localhost:8000/api/live/view
```

### 3. Monitor Speaker Buffers
```bash
curl http://localhost:8000/api/live/buffers
```

### 4. Trigger Medical Audit
```bash
curl -X POST http://localhost:8000/api/live/medical-audit
```

### 5. Review Transcript History
```bash
curl http://localhost:8000/api/live/transcript-history?limit=50
```

---

## Configuration

### Required Environment Variables

```bash
# Vertex AI Configuration
VERTEX_AI_PROJECT_ID=your-gcp-project-id
VERTEX_AI_LOCATION=us-central1
VERTEX_AI_MODEL=gemini-1.5-pro
GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json

# Recall.ai Configuration
RECALL_API_KEY=your-recall-api-key
PUBLIC_WS_URL=wss://your-domain.com  # For WebSocket

# OpenAI (for fallback analysis)
OPENAI_API_KEY=sk-...
```

### Vertex AI Setup
1. Create a GCP project
2. Enable Vertex AI API
3. Create a service account with Vertex AI permissions
4. Download JSON credentials
5. Set `GOOGLE_APPLICATION_CREDENTIALS` to the credentials file path

---

## Medical Audit Scoring

The medical accuracy audit evaluates multiple dimensions:

| Section | Score | Status |
|---------|-------|--------|
| Medical Accuracy | 0-100 | PASS/FAIL/WARNING |
| Dosage & Instructions | 0-100 | PASS/FAIL/WARNING |
| Patient Safety | 0-100 | PASS/FAIL/WARNING |
| Completeness | 0-100 | PASS/FAIL/WARNING |
| Professionalism | 0-100 | PASS/FAIL/WARNING |

**Overall Score:**
- **80-100%**: ✅ PASS - Compliant
- **60-79%**: ⚠️ WARNING - Attention Required
- **Below 60%**: ❌ FAIL - Critical Issues

---

## Error Handling

### Buffer States
- **Empty Buffers**: No text collected from speaker
- **Partial Buffers**: Only one speaker has content
- **Full Buffers**: Both speakers have content, ready for audit

### API Error Responses
```json
{
  "error": "Description of error",
  "timestamp": 1234567890
}
```

### Vertex AI Failures
- Graceful fallback to basic analysis
- Error messages logged to console
- Audit status set to "ERROR"

---

## Real-Time Data Flow

```
Recall.ai WebSocket
        ↓
    Transcript Event
        ↓
  Extract Speaker ID
        ↓
  Speaker Detection
        ↓
  Add to Buffer ← ← ← ← ← Speaker Detector
        ↓
 Update History
        ↓
 Trigger Analysis
        ↓
Vertex AI Gemini
        ↓
  JSON Response
        ↓
 Broadcast to UI
        ↓
Display in Dashboard
```

---

## Testing

### Test Medical Audit
```python
import asyncio
from app.vertex_ai_client import VertexAIClient

async def test_audit():
    client = VertexAIClient()
    result = await client.medical_accuracy_audit(
        doctor_buffer="Take two tablets twice daily with food",
        interpreter_buffer="Toma dos pastillas dos veces al día con comida"
    )
    print(result)

asyncio.run(test_audit())
```

### Test Speaker Detection
```python
from app.speaker_detector import get_speaker_detector

detector = get_speaker_detector()
detector.add_to_speaker_buffer("speaker_0", "You have diabetes")
detector.add_to_speaker_buffer("speaker_1", "Tienes diabetes")

print(detector.get_buffer_stats())
# Output:
# {
#   "doctor_segments": 1,
#   "interpreter_segments": 1,
#   "doctor_words": 3,
#   "interpreter_words": 2
# }
```

---

## Troubleshooting

### Vertex AI Not Working
1. Check `GOOGLE_APPLICATION_CREDENTIALS` path
2. Verify GCP project has Vertex AI enabled
3. Check service account permissions
4. Review logs for detailed error messages

### Speaker Buffers Empty
1. Verify Recall.ai is sending transcript events
2. Check speaker ID format (should be "speaker_0", "speaker_1")
3. Confirm transcript data contains "speaker" field

### UI Not Updating
1. Check WebSocket connection status (should show "Connected")
2. Verify `/api/live/stats` endpoint responds
3. Check browser console for JavaScript errors

---

## Performance Notes

- **Buffer Storage**: In-memory, cleared after audit
- **Vertex AI Calls**: Rate-limited to 2-second cooldown
- **Transcript History**: Last 50 entries displayed, all stored
- **Frame Buffer**: Last 20 frames kept in memory

---

## Future Enhancements

1. **Multi-Participant Support**: Handle >2 speakers
2. **Language Pair Validation**: Verify interpretation accuracy
3. **Dosage Extraction**: Automatic medication tracking
4. **Real-time Alerts**: Immediate notification of critical issues
5. **Historical Analysis**: Compare current meeting to past patterns

---

## Support

For issues or questions:
1. Check logs: `python -c "import logging; logging.basicConfig(level=logging.DEBUG)"`
2. Review Vertex AI quota and billing
3. Verify all environment variables are set
4. Test endpoints individually with `curl`

