import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.speaker_detector import SpeakerDetector

def test_speaker_detection():
    detector = SpeakerDetector()
    
    test_cases = [
        ("speaker_p", "My head hurts so much, I think I have a fever.", "Patient"),
        ("speaker_p", "I really like the coffee they serve here.", "Patient"),
        ("speaker_d", "I'm going to prescribe some ibuprofen for the pain.", "Doctor"),
        ("speaker_d", "How was your weekend?", "Doctor"),
        ("speaker_new", "Hello there.", "Speaker speaker_new")
    ]
    
    passed = 0
    for sid, text, expected in test_cases:
        detected = detector.detect_speaker_role(sid, text)
        match = (detected.lower().replace(" ", "") == expected.lower().replace(" ", ""))
        if match:
            passed += 1
            print(f"PASS: {sid} | '{text}' -> {detected}")
        else:
            print(f"FAIL: {sid} | '{text}'")
            print(f"  Expected: {expected}")
            print(f"  Detected: {detected}")
            print(f"  Scores: {detector.speaker_scores.get(sid)}")
            print(f"  Assignments: {detector.role_assignments.get(sid)}")

    print(f"\nFinal: {passed}/{len(test_cases)} passed")
    if passed == len(test_cases):
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    test_speaker_detection()
