# HIPAA Compliance & Medical Interpreter QA Analysis System

## Overview

This system provides real-time HIPAA compliance analysis and medical interpreter quality assurance for medical consultation videos. **All analysis logic is performed by AI models** - no hardcoded rules or local processing.

## Key Features

### 1. Dual API Analysis
- **Video Intelligence API**: Object tracking and label detection
- **Gemini Multimodal**: Comprehensive HIPAA compliance and interpreter QA analysis
- **Speed Comparison**: Automatically compares processing times between APIs

### 2. HIPAA Compliance Checks (AI-Driven)
All checks are performed by AI models via prompts:
- ✅ **Person Count Verification**: Ensures exactly 3 people (Patient, Doctor, Interpreter)
- ✅ **Unauthorized Person Detection**: Detects any unauthorized individuals
- ✅ **Privacy Violations**: Checks for privacy breaches
- ✅ **Environment Security**: Verifies private and secure environment
- ✅ **Compliance Scoring**: 0-100 score with detailed violations

### 3. Medical Interpreter QA (AI-Driven)
All QA metrics determined by AI:
- ✅ **Professionalism Score**: 0-100 rating
- ✅ **Engagement Level**: Whether interpreter is actively engaged
- ✅ **Issue Detection**: Identifies professionalism issues
- ✅ **Role Verification**: Confirms interpreter is present and performing role

### 4. Audio Disturbance Detection
- ✅ **Third-Party Sounds**: Detects baby crying, pet sounds, etc.
- ✅ **Background Conversations**: Identifies unauthorized audio
- ✅ **Environmental Noise**: Monitors for privacy violations

## Architecture

```
RTMP Stream
    ↓
Frame Extraction (FFmpeg)
    ↓
    ├─→ Video Intelligence API → Object Tracking
    └─→ Gemini API → HIPAA Compliance Analysis
    ↓
HIPAA Analyzer (Combines Results)
    ↓
WebSocket → Real-time Results
```

## Setup

### 1. Environment Variables

Add to `.env`:

```env
# Google Cloud Video Intelligence API
# Option 1: Use API key (simpler, recommended for development)
GOOGLE_CLOUD_API_KEY=your-video-intelligence-api-key

# Option 2: Use service account (for production/streaming)
# GOOGLE_CLOUD_PROJECT_ID=your-project-id
# GOOGLE_APPLICATION_CREDENTIALS=./credentials.json

# Gemini API
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.0-flash-exp
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Get API Keys

**Gemini API Key:**
1. Go to https://makersuite.google.com/app/apikey
2. Create API key
3. Add to `.env` as `GEMINI_API_KEY`

**Video Intelligence API:**
1. Go to Google Cloud Console
2. Enable Video Intelligence API
3. Create API key (recommended) OR create service account
4. Add to `.env` as `GOOGLE_CLOUD_API_KEY` (or use `GOOGLE_APPLICATION_CREDENTIALS` for service account)

## Usage

### Start Analysis

```bash
POST /api/analysis/start/{stream_key}?fps=1
```

**Parameters:**
- `stream_key`: RTMP stream key
- `fps`: Frames per second to analyze (default: 1)

**Response:**
```json
{
  "session_id": "meeting-5_1234567890.123",
  "stream_key": "meeting-5",
  "analysis_type": "HIPAA Compliance & Medical Interpreter QA",
  "apis_used": ["Video Intelligence API", "Gemini"],
  "fps": 1,
  "status": "started",
  "websocket_url": "/api/analysis/stream/{session_id}"
}
```

### Connect to WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8000/api/analysis/stream/{session_id}');

ws.onmessage = (event) => {
  const result = JSON.parse(event.data);
  
  if (result.type === 'analysis_result') {
    const analysis = result.data;
    
    // Speed comparison
    console.log('Video Intelligence API time:', analysis.speed_comparison.vi_time);
    console.log('Gemini API time:', analysis.speed_comparison.gemini_time);
    console.log('Faster API:', analysis.speed_comparison.faster_api);
    
    // HIPAA Compliance
    const compliance = analysis.combined_analysis.hipaa_compliance;
    console.log('Compliance Score:', compliance.compliance_score);
    console.log('Status:', analysis.combined_analysis.compliance_status);
    console.log('Violations:', compliance.violations);
    
    // Person Detection
    console.log('Person Count:', analysis.combined_analysis.person_count);
    console.log('Required Roles:', analysis.combined_analysis.required_roles_present);
    console.log('Unauthorized Persons:', analysis.combined_analysis.unauthorized_persons);
    
    // Interpreter QA
    const qa = analysis.combined_analysis.interpreter_qa;
    console.log('Professionalism Score:', qa.professionalism_score);
    console.log('Issues:', qa.issues);
  }
  
  if (result.type === 'compliance_alert') {
    console.warn('COMPLIANCE ALERT:', result.severity);
    console.warn('Details:', result.details);
  }
};
```

## Analysis Results Structure

```json
{
  "timestamp": "2024-01-01T12:00:00",
  "video_intelligence": {
    "api": "video_intelligence",
    "processing_time": 0.5,
    "objects_detected": []
  },
  "gemini": {
    "api": "gemini",
    "processing_time": 0.3,
    "person_count": 3,
    "required_roles_present": {
      "patient": true,
      "doctor": true,
      "interpreter": true
    },
    "unauthorized_persons_detected": false,
    "hipaa_compliance": {
      "privacy_violations": false,
      "environment_secure": true,
      "compliance_score": 95,
      "violations": []
    },
    "interpreter_qa": {
      "professionalism_score": 92,
      "is_present": true,
      "is_engaged": true,
      "issues": []
    }
  },
  "speed_comparison": {
    "vi_time": 0.5,
    "gemini_time": 0.3,
    "faster_api": "gemini"
  },
  "combined_analysis": {
    "person_count": 3,
    "hipaa_compliance": {...},
    "interpreter_qa": {...},
    "unauthorized_persons": false,
    "compliance_status": "COMPLIANT"
  }
}
```

## Compliance Status Levels

- **COMPLIANT**: Score ≥ 90, no violations
- **MINOR_ISSUES**: Score ≥ 70, minor issues detected
- **NON_COMPLIANT**: Score ≥ 50, significant violations
- **CRITICAL_VIOLATIONS**: Score < 50, critical HIPAA violations

## AI-Powered Analysis

All analysis logic is handled by AI models:

1. **Person Detection**: AI counts and identifies people in frame
2. **Role Identification**: AI determines if patient, doctor, and interpreter are present
3. **Unauthorized Detection**: AI identifies unauthorized persons
4. **HIPAA Compliance**: AI evaluates privacy, security, and compliance
5. **Interpreter QA**: AI assesses professionalism and engagement
6. **Environment Analysis**: AI checks for privacy and distractions

No hardcoded rules - all decisions are made by AI based on visual and contextual analysis.

## Performance

- **Frame Rate**: Configurable (default: 1 fps)
- **Processing**: Concurrent analysis with both APIs
- **Latency**: Real-time results via WebSocket
- **Speed Comparison**: Automatic tracking of API performance

## Cost Considerations

- **Video Intelligence API**: ~$0.10/minute for object tracking
- **Gemini API**: Pay-per-use based on tokens
- **Recommendation**: Use lower FPS (0.5-1) for cost optimization

## Future Enhancements

1. **Audio Analysis**: Integrate Speech-to-Text for disturbance detection
2. **Transcript Analysis**: Analyze conversation for HIPAA compliance
3. **Historical Tracking**: Track compliance trends over time
4. **Alert System**: Real-time alerts for critical violations
5. **Reporting**: Generate compliance reports
