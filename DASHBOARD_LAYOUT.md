# Dashboard Layout - Vertex AI Live Meeting Analysis

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    UNIVERSAL MEETING BOT LIVE                 [Connected] ◉  │
├─────────────────────────────────────────────────────┬───────────────────────┤
│                                                     │                       │
│                                                     │ ┌───────────────────┐ │
│              MJPEG Video Stream                      │ │ TRANSCRIPT HISTORY│ │
│           (Latest Recall.ai frame)                  │ │ ───────────────────│ │
│                                                     │ │ 10:32:15 Doctor   │ │
│            [Red image placeholder]                  │ │ says take aspirin  │ │
│           160 × 90 pixels                           │ │                   │ │
│           Real-time MJPEG update                    │ │ 10:32:20 Patient  │ │
│                                                     │ │ confirms understanding
│                                                     │ │                   │ │
│                                                     │ │ 10:32:25 Doctor   │ │
│                                                     │ │ prescribes course  │ │
│                                                     │ │                   │ │
│                                                     │ └─ scrolling ──────┘ │
│                                                     │                       │
│                                                     │ ┌───────────────────┐ │
│   [STATUS] Disconnected                            │ │ VERTEX AI ANALYSIS│ │
│   Status will show: Connected • video_..data       │ │ ───────────────────│ │
│                                                     │ │ ✅ COMPLIANT       │ │
│   ┌──────────────────────────────────────────────┐│ │                   │ │
│   │ TRANSCRIPT FEED                      [Real-  ││ │   Participants  5 │ │
│   │ ─────────────────────────────────────────── ││ │   Compliance   92%│ │
│   │ "Doctor says: The patient needs antibiotics ││ │                   │ │
│   │  and rest for two weeks. Proper follow-up   ││ │ ⚠️  NOISE DETECTED│ │
│   │  is essential."                             ││ │                   │ │
│   │                                              ││ │ Background chatter│ │
│   │ [Partial flag overlay: Real-time]           ││ │ in waiting area    │ │
│   └──────────────────────────────────────────────┘│ │                   │ │
│                                                     │ │ 📋 Description     │ │
│   ┌──────────────────────────────────────────────┐│ │ Discussion about   │ │
│   │ DISCUSSION INSIGHT                           ││ │ medication dosage  │ │
│   │ ──────────────────────────────────────────  ││ │ and follow-up care │ │
│   │ Doctor recommended 500mg aspirin, patient    ││ │ plan.              │ │
│   │ acknowledged treatment plan. Meeting covered ││ │                   │ │
│   │ medication administration, dosage frequency, ││ │ [⭐ ⭐ ⭐ ⭐ ⭐  │ │
│   │ and follow-up requirements.                  ││ │  Professional]     │ │
│   └──────────────────────────────────────────────┘│ └───────────────────┘ │
│                                                     │                       │
│                                                     │ ┌───────────────────┐ │
│                                                     │ │ REVIEWER FEEDBACK │ │
│                                                     │ │ ───────────────────│ │
│                                                     │ │ Add general notes: │ │
│                                                     │ │ [textarea box  ]   │ │
│                                                     │ │                   │ │
│                                                     │ │ Tags:              │ │
│                                                     │ │ [#Professional]    │ │
│                                                     │ │ [#Noise        ]   │ │
│                                                     │ │ [#Technical    ]   │ │
│                                                     │ │                   │ │
│                                                     │ │ Rating:            │ │
│                                                     │ │ ⭐ ⭐ ⭐ ⭐ ⭐     │ │
│                                                     │ │                   │ │
│                                                     │ │ [💾 Save] [🔄 Clr]│ │
│                                                     │ │ [⚠️  Flag Info]   │ │
│                                                     │ └───────────────────┘ │
│                                                     │                       │
│                                                     │ Raw Stream Stats:     │ │
│                                                     │ {                     │ │
│                                                     │   "events": {...},   │ │
│                                                     │   "last": "tr.data"  │ │
│                                                     │ }                     │ │
└─────────────────────────────────────────────────────┴───────────────────────┘

LEFT COLUMN (Main Content)              RIGHT COLUMN (Sidebar - scrollable)
- Video stream (MJPEG)                  - Transcript history (scrolling)
- Status badge                          - Vertex AI analysis card:
- Transcript feed (current)               * Compliance status
- Discussion insight                     * Participants count
                                         * Compliance score
                                         * Noise detection alert
                                         * Meeting description
                                       - Reviewer feedback form:
                                         * Notes
                                         * Tags
                                         * Rating
                                         * Flag button
                                       - Raw stats JSON
```

## Key Vertex AI Outputs Displayed

### Analysis Card Fields

| Field | Source | Display |
|-------|--------|---------|
| Status | `compliance_score >= 80` | ✅ COMPLIANT / ⚠ ATTENTION REQUIRED |
| Participants | `person_count` | "5" in stat grid |
| Compliance | `compliance_score` | "92%" in stat grid |
| Professionalism | `environment_analysis.is_professional` | PROFESSIONAL / NON-PROFESSIONAL badge |
| Noise Alert | `noise_detection.detected` | Shows/hides with description |
| Description | `discussion_summary` | 📋 Meeting overview panel |
| Issues | `hipaa_compliance.violations[]` | "Issues: [violation1], [violation2]" |

### Real-time Updates

- **Partial Transcripts**: Appear in "TRANSCRIPT FEED" as they arrive (marked as "Real-time")
- **Final Transcripts**: Added to "TRANSCRIPT HISTORY" with timestamp
- **Analysis Update**: Triggers when final transcript received, updates all Vertex AI fields
- **Refresh Rate**: Frontend polls `/api/live/stats` every 3 seconds

## Color Scheme

- **Connected**: 🟢 Green badge (#4ade80)
- **Disconnected**: 🔴 Red badge (#f87171)
- **Compliant**: 🟢 Green (#22c55e border)
- **Violation**: 🔴 Red (#ef4444 border)
- **Background**: Dark theme (#0a0a0c)
- **Noise Alert**: 🔴 Red (#ef4444)
- **Timestamp**: Gray (#64748b)
- **Active Text**: Light (#e2e8f0)

## Responsive Design

```
Desktop (1200px+):                Mobile (<1000px):
┌─────────────┬──────────┐        ┌─────────────┐
│  Video      │ Sidebar  │    →   │  Video      │
│  Transcript │ Analysis │        │  Transcript │
│  Discussion │ Feedback │        │  Analysis   │
│             │ Stats    │        │  Feedback   │
└─────────────┴──────────┘        │  Stats      │
                                   └─────────────┘
                                   (Stacked vertically)
```

