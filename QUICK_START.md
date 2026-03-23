# Quick Start Guide - Medical Meeting Bot

## Running the Bot

### 1. Start the Server
```bash
cd c:\Users\As\Desktop\universal-meeting-bot
python -m uvicorn app.main:app --reload
```

### 2. Open the Dashboard
```
http://localhost:8000/api/live/view
```

### 3. Create a Recall.ai Bot
```bash
curl -X POST http://localhost:8000/api/live/bot \
  -H "Content-Type: application/json" \
  -d '{
    "meeting_url": "https://zoom.us/j/...",
    "bot_name": "Medical Consultation Bot",
    "auto_leave": false
  }'
```

---

## Using the Dashboard

### Live View
- **Left Panel:** Transcript history with speaker roles
- **Center:** Live video stream (MJPEG)
- **Right Panel:** Compliance analysis and medical audit results

### Medical Audit
1. Click **"Run Audit"** button in left panel
2. Bot analyzes doctor and interpreter buffers
3. Results appear in right panel showing:
   - ✅ PASS / ⚠️ WARNING / ❌ FAIL
   - Overall accuracy score (0-100%)
   - Critical issues (if any)
   - Recommendations

### Speaker Identification
- **🔵 Blue badge** = Doctor speaking
- **🟣 Purple badge** = Interpreter speaking
- **Gray badge** = Unknown speaker

---

## API Commands

### Get Current Buffers
```bash
curl http://localhost:8000/api/live/buffers | jq
```

### Check Transcript History
```bash
curl http://localhost:8000/api/live/transcript-history?limit=20 | jq
```

### Trigger Medical Audit
```bash
curl -X POST http://localhost:8000/api/live/medical-audit | jq
```

### Clear Buffers
```bash
curl -X POST http://localhost:8000/api/live/buffers/clear
```

### Get Stream Stats
```bash
curl http://localhost:8000/api/live/stats | jq
```

---

## Medical Audit Scoring

### Interpretation Accuracy
- **Medical Terms:** Correct medical terminology
- **Dosage:** Complete and accurate medication instructions
- **Safety:** No misinterpretations that could harm patient

### Scoring
- **80-100%:** ✅ PASS - Ready for use
- **60-79%:** ⚠️ WARNING - Review needed
- **<60%:** ❌ FAIL - Critical issues

---

## Monitoring

### Check Logs
```bash
# In terminal where server is running - look for:
[SPEAKER] ID: speaker_0, Role: Doctor
[SPEAKER] ID: speaker_1, Role: Interpreter
[MEDICAL-AUDIT] Audit complete. Status: PASS
```

### Buffer Status
- Doctor segments: Number of doctor statements
- Interpreter segments: Number of interpreter statements
- Doctor words: Total words spoken by doctor
- Interpreter words: Total words spoken by interpreter

---

## Common Issues

### No Video Showing?
1. Check WebSocket connection (should show "Connected")
2. Verify Recall.ai is sending frames
3. Check browser console for errors

### Audit Not Running?
1. Both buffers must have content
2. Check VERTEX_AI_PROJECT_ID is set
3. Verify credentials file exists
4. Check logs for Vertex AI errors

### Wrong Speaker Detected?
1. Verify speaker ID in Recall.ai payload
2. Check speaker_detector.py mapping (speaker_0, speaker_1)
3. Can manually override in UI (future feature)

---

## Performance

- **Transcript Update:** Real-time (100ms)
- **Audit Run:** 5-10 seconds (Vertex AI latency)
- **Buffer Stats:** Updates every 3 seconds
- **Video Stream:** 30fps MJPEG

---

## Key Features

✅ Speaker identification and role assignment
✅ Real-time transcript with speaker labels
✅ Medical accuracy auditing with Vertex AI
✅ Buffer management for doctor/interpreter statements
✅ HIPAA compliance checking
✅ Critical issue detection
✅ Live dashboard with 3-column layout
✅ API endpoints for programmatic access

---

## Next Meeting?

1. Start server
2. Open dashboard at http://localhost:8000/api/live/view
3. Create bot with meeting URL
4. Watch transcript and speaker identification in real-time
5. Click "Run Audit" when ready for medical accuracy review
6. Check results in right panel

---

## Support

For issues:
1. Check **CHANGES_SUMMARY.md** for what changed
2. Review **IMPLEMENTATION_GUIDE.md** for details
3. Check server logs for errors
4. Verify all env variables are set
5. Test endpoints with `curl` commands above

