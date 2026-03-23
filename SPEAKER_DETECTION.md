# Speaker Detection & Role Assignment

## How It Works

The system uses **multiple methods** to differentiate between Doctor, Interpreter, and Patient:

### 1. **Recall.ai Speaker Labels** (Primary Method)

Recall.ai provides speaker diarization in the transcript data:

```json
{
  "speaker": "speaker_0",
  "text": "You need to take two tablets in the morning",
  "speaker_metadata": {
    "name": "Dr. Smith"
  }
}
```

The system checks the speaker name for keywords:
- `"doctor"`, `"dr"`, `"physician"` → **Doctor**
- `"patient"` → **Patient**
- `"interpreter"`, `"translator"` → **Interpreter**

### 2. **Text Content Analysis** (Secondary Method)

If speaker labels aren't available, the system analyzes the text:

#### Doctor Indicators:
- Medical terminology: "prescription", "dosage", "medication", "diagnosis"
- Clinical language: "blood pressure", "mg", "tablets", "treatment"

#### Patient Indicators:
- Personal expressions: "I feel", "my pain", "I have", "it hurts"
- Questions: "I don't understand", "what should I do"

#### Interpreter Indicators:
- Meta-language: "the doctor says", "the patient says"
- Translation phrases: "let me translate", "he/she is saying"

### 3. **Language Detection** (For Interpreter Direction)

The interpreter speaks **two languages**:
- **English** → Speaking to Doctor (`Interpreter→Doctor`)
- **Spanish/Other** → Speaking to Patient (`Interpreter→Patient`)

Example:
```
[Interpreter→Patient] "Necesitas tomar dos pastillas" (Spanish)
[Interpreter→Doctor] "The patient understands" (English)
```

### 4. **Voice Characteristics** (Future Enhancement)

Can be added using audio analysis:
- **Pitch/Tone**: Typically different between genders
- **Speaking Rate**: Doctors often speak faster
- **Voice Print**: Unique voice signatures

---

## Implementation

### Step 1: Install Speaker Detector

The `speaker_detector.py` file has been created with the `SpeakerDetector` class.

### Step 2: Integrate with Recall.ai WebSocket

Update `routes/live.py` to use speaker detection:

```python
from app.speaker_detector import get_speaker_detector

# In websocket_recall function:
speaker_detector = get_speaker_detector()

# When processing transcript:
if event in ("transcript.data", "transcript.partial_data"):
    # Extract speaker info
    speaker_info = speaker_detector.update_from_recall_transcript(data)
    
    # Now you have:
    # speaker_info["role"] = "Doctor" | "Patient" | "Interpreter→Patient" | "Interpreter→Doctor"
    # speaker_info["text"] = "You need to take two tablets"
    # speaker_info["language"] = "en" | "es"
```

### Step 3: Store Transcript with Speaker Roles

Save to the transcript database:

```python
from app.models.transcript import TranscriptSegment

segment = TranscriptSegment(
    id=str(uuid.uuid4()),
    session_id=session_id,
    timestamp=current_time,
    speaker=speaker_info["role"],  # "Doctor", "Patient", etc.
    text=speaker_info["text"],
    language=speaker_info["language"]
)
```

### Step 4: Display in UI

The transcript review UI already supports color-coded speakers:

```javascript
function getSpeakerClass(speaker) {
    if (speaker === "Doctor") return "doctor";           // Blue
    if (speaker === "Patient") return "patient";         // Green
    if (speaker.includes("Interpreter→Patient")) return "interpreter-patient";  // Purple
    if (speaker.includes("Interpreter→Doctor")) return "interpreter-doctor";    // Orange
    return "";
}
```

---

## Example Flow

### Input (from Recall.ai):
```json
{
  "event": "transcript.data",
  "data": {
    "speaker": "speaker_0",
    "text": "You need to take two tablets in the morning and one at night."
  }
}
```

### Processing:
1. **Speaker Detector** analyzes text
2. Finds medical keywords: "tablets", "morning", "night"
3. Assigns role: **"Doctor"**

### Output (stored in database):
```json
{
  "id": "seg123",
  "session_id": "78923",
  "timestamp": 323.5,
  "speaker": "Doctor",
  "text": "You need to take two tablets in the morning and one at night.",
  "language": "en"
}
```

### Display (in UI):
```
[00:05:23] [Doctor] You need to take two tablets in the morning and one at night.
           ^^^^^^^^
           Blue color
```

---

## Advanced: Manual Speaker Assignment

If automatic detection fails, provide a UI for manual assignment:

```html
<select class="speaker-selector">
  <option value="Doctor">Doctor</option>
  <option value="Patient">Patient</option>
  <option value="Interpreter→Patient">Interpreter→Patient</option>
  <option value="Interpreter→Doctor">Interpreter→Doctor</option>
</select>
```

---

## Testing

Test the speaker detector:

```python
from app.speaker_detector import SpeakerDetector

detector = SpeakerDetector()

# Test 1: Doctor
role = detector.detect_speaker_role(
    speaker_id="speaker_0",
    text="You need to take two tablets in the morning",
    language="en"
)
print(role)  # Output: "Doctor"

# Test 2: Patient
role = detector.detect_speaker_role(
    speaker_id="speaker_1",
    text="I feel pain in my chest",
    language="en"
)
print(role)  # Output: "Patient"

# Test 3: Interpreter to Patient
role = detector.detect_speaker_role(
    speaker_id="speaker_2",
    text="Necesitas tomar dos pastillas por la mañana",
    language="es"
)
print(role)  # Output: "Interpreter→Patient"
```

---

## Summary

**Speaker differentiation uses:**
1. ✅ Recall.ai speaker labels (if available)
2. ✅ Text content analysis (medical terms, personal expressions)
3. ✅ Language detection (English vs Spanish)
4. ✅ Context clues ("the doctor says", "the patient says")

**Visual differentiation in UI:**
- 🔵 **Doctor** = Blue
- 🟢 **Patient** = Green  
- 🟣 **Interpreter→Patient** = Purple
- 🟠 **Interpreter→Doctor** = Orange

The system is **automatic** but can be **manually corrected** if needed.
