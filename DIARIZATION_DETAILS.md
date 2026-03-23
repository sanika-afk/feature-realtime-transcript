# Speaker Diarization & Role Assignment System

This document outlines the architecture and logic used by the Universal Meeting Bot to identify participants and assign them specific medical roles (Doctor, Patient, Interpreter).

## 1. System Architecture
Our system uses a "Two-Layer" approach to achieve maximum reliability:

### Layer A: Diarization (Who is speaking?)
- **Provider**: Handled by Recall.ai transcription.
- **Mechanism**: Detects changes in voice signatures (pitch, tone, timing) or separate audio streams (in remote calls).
- **Output**: Assigns a unique ID (`speaker_0`, `speaker_1`, etc.) to each distinct voice.

### Layer B: Role Assignment (What is their role?)
- **Provider**: Custom `SpeakerDetector` engine.
- **Mechanism**: Analyzes the **content** of the speech to map Speaker IDs to roles.
- **Output**: "[DOCTOR]", "[PATIENT]", or "[INTERPRETER]".

---

## 2. The Heuristic Scoring Engine
Unlike simple keyword matching, our system uses a **Dynamic Scoring Engine** to learn roles over the first few minutes of a meeting.

### How it Works:
Each speaker ID starts with a score of `0` for all roles. As they speak, we analyze every sentence:

| Category | Indicators | Score Value |
| :--- | :--- | :--- |
| **Doctor** | Clinical questions ("Do you have..."), medical commands ("Take a seat"), prescriptions. | +1.5 to +2.5 |
| **Patient** | Personal symptoms ("My head hurts"), medical history, "I feel...". | +1.0 to +2.0 |
| **Interpreter** | Transition phrases ("The doctor says...", "He is asking..."), translating languages. | +2.0 (Immediate Lock) |

### Role "Stickiness"
Once a speaker reaches a **Confidence Threshold (2.0)**, their role is **locked**.
- **Effect**: If the system identifies `speaker_0` as the "Doctor", even if they say generic things later (like "How was your weekend?"), the system maintains the [DOCTOR] label.

---

## 3. Reliability & Effectiveness
Our system is designed for the high-stakes environment of medical consultations.

### Why it is Effective:
1. **Clinical Context Awareness**: It doesn't just look for "medical words"; it looks for **interaction patterns**. Doctors ask questions; Patients describe feelings.
2. **Resilience to Small Talk**: By requiring a score threshold before locking, the system ignores generic introductions ("Hello", "Can you hear me?") until actual medical context appears.
3. **No Hardcoded Assumptions**: It doesn't matter if the Doctor or the Patient joins the call first or who has the first speaker ID; the system "learns" who is who based on what they say.
4. **Zero "Unknowns"**: Once roles are established, the hierarchy ensures every word is attributed to the correct person, keeping the transcript clean and professional.

### Example in Action:
- **Speaker A**: "Good morning. How can I help you today?" → **(Score: Doctor +1.5)**
- **Speaker B**: "I have been feeling very dizzy since yesterday." → **(Score: Patient +2.0) -> LOCKED AS PATIENT**
- **Speaker A**: "I see. Are you taking any meds for that?" → **(Score: Doctor +2.0) -> LOCKED AS DOCTOR**

---

## 4. Implementation Reference
The core logic resides in:
- `app/speaker_detector.py`: Heuristic engine.
- `app/routes/live.py`: Real-time WebSocket processing.
- `app/models/transcript.py`: Data structure for roles.
