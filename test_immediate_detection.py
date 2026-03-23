"""
Test script to verify speaker detection improvements.
Tests that speakers are labeled correctly from the FIRST utterance.
"""
from app.speaker_detector import SpeakerDetector

# Create fresh detector for testing
detector = SpeakerDetector()

print("=" * 70)
print("IMMEDIATE SPEAKER DETECTION TEST")
print("=" * 70)
print("\nTesting that speakers are labeled correctly from FIRST utterance\n")

test_cases = [
    # Doctor phrases
    ("speaker_0", "Hello, how can I help you today?", "Doctor"),
    ("speaker_1", "Let me check your blood pressure", "Doctor"),
    ("speaker_2", "Take two tablets in the morning", "Doctor"),
    
    # Patient phrases  
    ("speaker_3", "I feel pain in my chest", "Patient"),
    ("speaker_4", "My head hurts since yesterday", "Patient"),
    ("speaker_5", "I'm worried about the symptoms", "Patient"),
    
    # Interpreter phrases
    ("speaker_6", "doctor says you need to rest", "Interpreter"),
    ("speaker_7", "patient says I feel better", "Interpreter"),
    ("speaker_8", "the doctor wants to know about your pain", "Interpreter"),
]

passed = 0
failed = 0

for speaker_id, text, expected_base_role in test_cases:
    # Fresh detector for each test to simulate first utterance
    detector = SpeakerDetector()
    
    detected_role = detector.detect_speaker_role(
        speaker_id=speaker_id,
        text=text,
        language="en"
    )
    
    # For interpreter, just check if it starts with "Interpreter"
    if expected_base_role == "Interpreter":
        is_correct = detected_role.startswith("Interpreter")
    else:
        is_correct = detected_role == expected_base_role
    
    status = "✓ PASS" if is_correct else "✗ FAIL"
    if is_correct:
        passed += 1
    else:
        failed += 1
    
    print(f"{status}")
    print(f"  Speaker: {speaker_id}")
    print(f"  Text: '{text}'")
    print(f"  Expected: {expected_base_role}")
    print(f"  Got: {detected_role}")
    print()

print("=" * 70)
print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
print("=" * 70)

if failed == 0:
    print("\n✅ All speakers labeled correctly from FIRST utterance!")
else:
    print(f"\n⚠️ {failed} test(s) failed. Speakers may show as 'Unknown' initially.")
