# Interactive Transcript Review - Quick Start Guide

## 🚀 Getting Started

### Access the Interface
Navigate to: `http://localhost:8000/transcript-review`

## 📐 Layout Overview

The interface is divided into **3 columns**:

```
┌─────────────────────┬──────────────┬───────────────────┐
│                     │              │                   │
│    VIDEO PLAYER     │  TRANSCRIPT  │   RIGHT PANELS    │
│    (1.5fr)          │   (1fr)      │   (450px)         │
│                     │              │                   │
│  ┌───────────────┐  │ ┌──────────┐ │ ┌─────────────┐   │
│  │               │  │ │Segment 1 │ │ │  Flag Info  │   │
│  │  Video.mp4    │  │ │Segment 2 │ │ │  (Screen 5) │   │
│  │               │  │ │Segment 3⚠️│ │ │             │   │
│  │  [Controls]   │  │ │Segment 4⚠️│ │ │ Actions:    │   │
│  │               │  │ │Segment 5 │ │ │ ✅✌️✏️💬    │   │
│  │               │  │ │...       │ │ └─────────────┘   │
│  │               │  │ │          │ │ ┌─────────────┐   │
│  │               │  │ │[Search]  │ │ │  Feedback   │   │
│  │               │  │ │          │ │ │  (Screen 6) │   │
│  │               │  │ │          │ │ │             │   │
│  │               │  │ │          │ │ │ Notes, Tags │   │
│  │               │  │ │          │ │ │ Rating, Etc │   │
│  └───────────────┘  │ └──────────┘ │ └─────────────┘   │
└─────────────────────┴──────────────┴───────────────────┘
```

---

## 🎬 Video & Transcript Panel

### Features
- **Click any transcript line** → Video jumps to that timestamp
- **Hover over highlighted text** → See AI reasoning in tooltip
- **Auto-scroll** → Transcript follows video playback
- **Color-coded speakers**:
  - 🔵 Doctor
  - 🟢 Patient
  - 🟣 Interpreter→Patient
  - 🟠 Interpreter→Doctor

### Error Highlighting
- 🔴 **Red** = Critical (must address)
- 🟡 **Yellow** = Major (important)
- 🔵 **Blue** = Minor (note)

### Example Tooltip
```
⚠️ Critical Error - Omission
"Dosage quantity missing ('two' and 'one' not interpreted) (Confidence: 92%)"
```

---

## 🚩 Flag Validation Panel (Right Side - Top)

### What You'll See
```
🚩 Flag Validation [Pending]

Confidence:           92%
Error Type:           Omission
Severity:             Critical
Category:             Medical Dosage

Original vs. Interpreted Text Comparison
[Original block]      [Interpreted block]

[✅ Confirm] [❌ Reject] [✏️ Edit]

[💬 Comment field...]
[Add Comment]
```

### Actions Available

**✅ Confirm Flag**
- Agree with the AI assessment
- Status changes to "Confirmed" (green)

**❌ Reject Flag**
- Dismiss as false positive
- Status changes to "Rejected" (red)

**✏️ Edit Flag**
- Modify severity or error type
- Add context in comment
- Example: "Interpreter corrected at 05:35"

**💬 Comment**
- Document your reasoning
- Support audit trail
- Help train AI system

---

## 📋 Session Feedback Panel (Right Side - Bottom)

### 1. General Notes
```
[Text area for comprehensive feedback]
"Quality of interpretation good overall. 
Minor issues with medical terminology. 
Patient seemed confused at 3:45 mark."
```

### 2. Issue Tags
Pre-defined options:
- `#ProfessionalismIssue` - Behavior/conduct
- `#BackgroundNoise` - Audio quality
- `#TechnicalGlitch` - System issues
- `#Clarity` - Language clarity
- `#AccentIssue` - Accent/pronunciation

**Add Custom Tags:**
```
Input: "#CustomTag"
→ Creates new tag
→ Shows with ✕ to remove
```

### 3. Interpreter Rating
```
⭐⭐⭐⭐☆  (4 out of 5 stars)
```
Click to set rating (1-5 stars)

### 4. Coaching Recommendation
```
[Toggle: OFF] Coaching Recommended: No
     ↓
[Toggle: ON]  Coaching Recommended: Yes
```

### 5. Save & Clear
- **💾 Save Feedback** → Submits all data to backend
- **🔄 Clear** → Resets with confirmation

---

## 📝 Workflow Example

### Scenario: Review a Medical Consultation

1. **Start Review**
   - Open transcript_review.html
   - Video loads with transcript

2. **Identify Issues**
   - Scan through transcript
   - Red flags appear at 5:32, 7:15, 12:08

3. **Validate First Flag**
   - Click flagged line at 5:32
   - Flag panel opens on right
   - Shows: Critical Omission (92% confidence)
   - Original: "Take two tablets..."
   - Interpreted: "Take tablets..."
   - Missing "two" and dosage details

4. **Take Action**
   - Click ✅ Confirm
   - Add comment: "Definite omission, safety risk"
   - Status → "Confirmed" (green)

5. **Validate Other Flags**
   - Repeat for remaining 2 flags

6. **Add Session Feedback**
   - Fill general notes
   - Tag: #MedicalTeminology
   - Rating: ⭐⭐⭐⭐ (4/5)
   - Toggle: Yes for coaching

7. **Submit**
   - Click 💾 Save Feedback
   - Data sent to backend
   - Confirmation message

---

## 🔌 API Endpoints

### Create/Update Flags
```
POST   /api/transcripts/flags/{flag_id}/validate
  Body: { "action": "confirm|reject", "comment": "..." }

PUT    /api/transcripts/flags/{flag_id}
  Body: { "severity": "...", "error_type": "...", "comment": "..." }

POST   /api/transcripts/flags/{flag_id}/comment
  Body: { "comment": "..." }
```

### Session Feedback
```
POST   /api/transcripts/session-feedback
  Body: {
    "overall_notes": "...",
    "tags": ["#Tag1", "#Tag2"],
    "interpreter_rating": 4,
    "recommend_coaching": true
  }

GET    /api/transcripts/{session_id}/feedback
  Returns: SessionFeedback object
```

### Get Transcript
```
GET    /api/transcripts/{session_id}
  Returns: TranscriptResponse with segments and flags

GET    /api/transcripts/{session_id}/flags?severity=critical
  Filters: severity, status_filter, error_type
```

---

## 🎨 Color Reference

| Element | Color | RGB |
|---------|-------|-----|
| Primary Blue | #64b5f6 | (100, 181, 246) |
| Success Green | #66bb6a | (102, 187, 106) |
| Critical Red | #f44336 | (244, 67, 54) |
| Warning Yellow | #ffc107 | (255, 193, 7) |
| Info Blue | #2196f3 | (33, 150, 243) |
| Dark Background | #1a1a2e | (26, 26, 46) |

---

## 💡 Tips & Tricks

1. **Hover First** - Always hover over red flags to see AI reasoning before confirming
2. **Use Comments** - Add context for false positives to help train the AI
3. **Tag Issues** - Use tags for audit trail and patterns
4. **Rate Fairly** - Rating helps identify interpreter performance trends
5. **Coaching Toggle** - Only recommend when specific improvements are needed

---

## 🐛 Troubleshooting

**Flag panel not showing?**
- Click on a transcript line with ⚠️ indicator

**Can't save feedback?**
- Ensure at least some feedback is provided
- Check browser console for API errors

**Tooltip not appearing?**
- Hover directly over the flagged text
- Wait 1-2 seconds for tooltip to appear

**Video not seeking?**
- Ensure video source is properly loaded
- Check that timestamp values are valid

---

## 📞 Support

For issues or feature requests, check the console (F12) for error details and review the API responses in Network tab.
