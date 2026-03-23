# System Architecture - Medical Meeting Bot

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      Recall.ai Meeting                           │
│                  (Real-time video + audio)                       │
└──────────────────────────────────────────────────────────────────┘
                              ↓
                    WebSocket Connection
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│                   Universal Meeting Bot                          │
│                    (FastAPI Server)                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  WebSocket Handler (/ws/recall)                                 │
│  ├── Parse video frames                                         │
│  ├── Extract transcripts                                        │
│  ├── Identify speaker (speaker_0, speaker_1)                   │
│  └── Add to speaker buffers                                     │
│                              ↓                                  │
│  Speaker Detector                                              │
│  ├── speaker_0 → Doctor Buffer                                 │
│  ├── speaker_1 → Interpreter Buffer                            │
│  └── Role Assignment                                           │
│                              ↓                                  │
│  Transcript History                                            │
│  ├── Timestamp                                                 │
│  ├── Speaker Role                                              │
│  ├── Text Content                                              │
│  └── Language (en/es)                                          │
│                              ↓                                  │
│  Medical Accuracy Audit (on demand)                           │
│  └── Send doctor_buffer + interpreter_buffer → Vertex AI      │
│                              ↓                                  │
│  Vertex AI Gemini 1.5 Pro                                     │
│  ├── Analyze medical accuracy                                 │
│  ├── Check dosage completeness                                │
│  ├── Identify critical issues                                 │
│  └── Return JSON scores                                        │
│                              ↓                                  │
│  Analysis Results                                              │
│  ├── Audit Status (PASS/WARN/FAIL)                           │
│  ├── Overall Accuracy Score (0-100)                          │
│  ├── Critical Issues                                          │
│  └── Recommendations                                          │
│                              ↓                                  │
│  REST API Endpoints                                           │
│  ├── /api/live/medical-audit → POST                          │
│  ├── /api/live/buffers → GET                                 │
│  ├── /api/live/transcript-history → GET                      │
│  ├── /api/live/stats → GET                                   │
│  └── /api/live/view → GET (Dashboard HTML)                   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│                    Web Browser Dashboard                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ LEFT PANEL       │ CENTER        │ RIGHT PANEL          │  │
│  │ ───────────────  │ ───────────   │ ─────────────        │  │
│  │ Transcript       │ Live Video    │ Compliance Score     │  │
│  │ History          │               │                      │  │
│  │                  │ Current       │ Medical Audit        │  │
│  │ Speaker Roles    │ Speaker       │ Results              │  │
│  │ 🔵 Doctor        │               │                      │  │
│  │ 🟣 Interpreter   │ Latest Text   │ Buffer Stats         │  │
│  │                  │               │ Doctor: 5 segments   │  │
│  │ 🏥 Run Audit     │               │ Interp: 5 segments   │  │
│  │ Button           │               │                      │  │
│  │                  │               │ ✅ PASS (94%)        │  │
│  │                  │               │                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### Speaker Detector Module
```
SpeakerDetector
├── Attributes:
│   ├── speaker_history: Dict[speaker_id] → [texts]
│   ├── role_assignments: Dict[speaker_id] → "Doctor"|"Interpreter"
│   ├── doctor_buffer: List[str] - Doctor statements
│   ├── interpreter_buffer: List[str] - Interpreter statements
│   └── speaker_id_mapping: {"speaker_0": "Doctor", "speaker_1": "Interpreter"}
│
└── Methods:
    ├── detect_speaker_role(speaker_id, text) → Role
    ├── add_to_speaker_buffer(speaker_id, text) → None
    ├── get_doctor_buffer_text() → str
    ├── get_interpreter_buffer_text() → str
    ├── get_all_buffers() → Dict[str, str]
    ├── clear_buffers() → None
    └── get_buffer_stats() → Dict[str, int]
```

### Vertex AI Client
```
VertexAIClient
├── Initialization:
│   ├── project_id: str (GCP Project)
│   ├── location: str (us-central1)
│   ├── model_id: str (gemini-1.5-pro)
│   └── Credentials: GOOGLE_APPLICATION_CREDENTIALS
│
└── Methods:
    ├── analyze_frame(frame_bytes, transcript) → Dict
    ├── analyze_interpretation_quality(doctor_text, interp_text) → Dict
    └── medical_accuracy_audit(doctor_buffer, interp_buffer, frame?) → Dict
```

### Transcript Segment
```
{
  "timestamp": float (Unix time),
  "speaker_id": "speaker_0" | "speaker_1",
  "speaker_role": "Doctor" | "Interpreter",
  "text": "The actual transcript text",
  "language": "en" | "es",
  "words": int (word count)
}
```

### Medical Audit Result
```
{
  "audit_status": "PASS" | "WARNING" | "FAIL",
  "overall_accuracy_score": 0-100,
  "sections": [
    {
      "section": "Medical Accuracy",
      "score": 0-100,
      "status": "PASS" | "FAIL" | "WARNING",
      "findings": [strings],
      "recommendations": [strings]
    }
  ],
  "critical_issues": [
    {
      "issue": "Issue description",
      "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
      "impact": "Patient Safety" | "Legal" | "Quality",
      "evidence": "Quoted text",
      "recommendation": "Action to take"
    }
  ],
  "strengths": [strings],
  "summary": "Executive summary"
}
```

---

## Data Flow - Real-time Transcript

```
1. Recall.ai WebSocket Event
   └── {"event": "transcript.data", "data": {"speaker": "speaker_0", "text": "..."}}

2. Live Route Handler (/ws/recall)
   └── Parse event, extract speaker_id and text

3. Speaker Detector
   └── Identify role based on speaker_id
      ├── speaker_0 → "Doctor"
      └── speaker_1 → "Interpreter"

4. Add to Buffer
   ├── doctor_buffer.append("Take two tablets...")
   └── interpreter_buffer.append("Toma dos pastillas...")

5. Update Transcript History
   └── {timestamp, speaker_id, speaker_role, text, language}

6. Broadcast to Dashboard
   └── WebSocket → updateAnalysisUI(data)

7. Display in UI
   ├── Update current speaker display
   ├── Add to transcript history
   └── Update buffer statistics
```

---

## Data Flow - Medical Audit

```
1. User Clicks "Run Audit" Button
   └── fetch("/api/live/medical-audit", {method: "POST"})

2. Audit Endpoint (/api/live/medical-audit)
   └── Collect doctor_buffer + interpreter_buffer

3. Call Vertex AI
   ├── doctor_buffer: "Take two tablets in the morning and one at night"
   ├── interpreter_buffer: "Necesita tomar dos pastillas por la mañana y una por la noche"
   └── frame_bytes: (optional video frame)

4. Gemini 1.5 Pro Processing
   ├── Parse doctor statements
   ├── Parse interpreter statements
   ├── Compare for accuracy
   ├── Check dosage completeness
   ├── Identify critical issues
   └── Generate scores

5. JSON Response from Vertex AI
   └── {audit_status, overall_accuracy_score, critical_issues, ...}

6. Store Result
   └── _latest_analysis.analysis = audit_result

7. Broadcast to Dashboard
   └── WebSocket → updateAnalysisUI(analysis)

8. Display Results
   ├── Show audit status
   ├── Display accuracy score
   ├── List critical issues
   └── Show recommendations
```

---

## API Endpoint Flow

```
┌─ GET /api/live/view
│  └─ Returns HTML Dashboard
│
├─ GET /api/live/stream
│  └─ Returns MJPEG video stream
│
├─ POST /api/live/medical-audit
│  ├─ Collect buffers from speaker_detector
│  ├─ Call _run_medical_accuracy_audit()
│  ├─ Wait for Vertex AI response
│  └─ Return {status, buffers, latest_analysis}
│
├─ GET /api/live/buffers
│  ├─ Get doctor_buffer_text()
│  ├─ Get interpreter_buffer_text()
│  ├─ Get buffer_stats()
│  └─ Return {buffers, stats, speaker_roles, transcript_history}
│
├─ POST /api/live/buffers/clear
│  ├─ clear_buffers()
│  └─ Clear transcript_history
│
├─ GET /api/live/transcript-history
│  ├─ Query parameter: limit=100
│  └─ Return last N transcript entries
│
└─ GET /api/live/stats
   └─ Return {connected, events, latest_analysis, ...}
```

---

## Database Storage (Future)

```
Current: In-Memory
├── doctor_buffer: List[str]
├── interpreter_buffer: List[str]
└── transcript_history: List[Dict]

Future: PostgreSQL
├── medical_audits table
│   ├── id (UUID)
│   ├── session_id
│   ├── doctor_text
│   ├── interpreter_text
│   ├── audit_status
│   ├── accuracy_score
│   ├── critical_issues (JSON)
│   └── timestamp
│
├── transcripts table
│   ├── id
│   ├── session_id
│   ├── timestamp
│   ├── speaker_id
│   ├── speaker_role
│   ├── text
│   └── language
│
└── sessions table
    ├── id
    ├── recall_bot_id
    ├── meeting_url
    ├── status
    ├── started_at
    └── ended_at
```

---

## Security Considerations

```
┌─ Input Validation
│  ├─ Speaker ID format (speaker_X)
│  ├─ Text content length limits
│  └─ Frame size validation
│
├─ Authentication (Future)
│  ├─ API key validation
│  ├─ User role-based access
│  └─ Session tokens
│
├─ Data Privacy
│  ├─ HIPAA compliance
│  ├─ Patient PII redaction
│  ├─ Secure transcript storage
│  └─ Encrypted audit results
│
└─ Rate Limiting
   ├─ Vertex AI throttling (2s cooldown)
   ├─ API endpoint rate limits
   └─ WebSocket message frequency
```

---

## Deployment Architecture

```
┌──────────────────────────────────────────┐
│         Production Environment           │
├──────────────────────────────────────────┤
│                                          │
│  ┌─ Docker Container                   │
│  │  ├─ FastAPI App (uvicorn)           │
│  │  ├─ Python 3.11+                    │
│  │  ├─ app/                            │
│  │  │  ├─ main.py                      │
│  │  │  ├─ speaker_detector.py          │
│  │  │  ├─ vertex_ai_client.py          │
│  │  │  └─ routes/live.py               │
│  │  └─ requirements.txt                │
│  │      ├─ fastapi                     │
│  │      ├─ google-cloud-aiplatform     │
│  │      ├─ python-dotenv               │
│  │      └─ ...                          │
│  │                                      │
│  └─ Environment                         │
│     ├─ VERTEX_AI_PROJECT_ID            │
│     ├─ VERTEX_AI_LOCATION              │
│     ├─ VERTEX_AI_MODEL                 │
│     ├─ GOOGLE_APPLICATION_CREDENTIALS  │
│     ├─ RECALL_API_KEY                  │
│     └─ PUBLIC_WS_URL                   │
│                                          │
└──────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────┐
│      Google Cloud Platform (GCP)         │
├──────────────────────────────────────────┤
│  ├─ Vertex AI API (Gemini)              │
│  ├─ Cloud Storage (optional)            │
│  └─ Cloud Logging (optional)            │
└──────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────┐
│        External Services                 │
├──────────────────────────────────────────┤
│  ├─ Recall.ai (WebSocket)              │
│  └─ OpenAI API (fallback)              │
└──────────────────────────────────────────┘
```

---

## Performance Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| Transcript Latency | ~100ms | Real-time update |
| Audit Latency | 5-10s | Vertex AI processing |
| Buffer Update | ~3s | Stats polling interval |
| Frame Rate | 30fps | MJPEG stream |
| Concurrent Connections | 1 WebSocket | Design: single session |
| Memory Usage | ~50-100MB | Typical operation |
| Buffer Retention | Session | Cleared after audit |

---

## Monitoring & Logging

```
Application Logs
├── [SPEAKER] Speaker identification
│   └── "ID: speaker_0, Role: Doctor"
├── [TRANSCRIPT] Transcript received
│   └── "Final: Take two tablets..."
├── [MEDICAL-AUDIT] Audit execution
│   └── "Audit complete. Status: PASS"
├── [VERTEX-AI] API interaction
│   └── "Processing medical accuracy audit"
└── [ERROR] Exception handling
    └── "Failed to analyze frame..."
```

