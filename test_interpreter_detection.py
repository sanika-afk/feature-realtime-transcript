"""
Test script to verify interpreter detection improvements.
Tests various interpreter phrases to ensure proper labeling.
"""
from app.speaker_detector import get_speaker_detector

detector = get_speaker_detector()

# Test cases for interpreter detection
test_cases = [
    # Original format (should work)
    ("the doctor says you need to take medicine", "Interpreter→Patient"),
    ("the patient says I have a headache", "Interpreter→Doctor"),
    
    # New flexible formats (should now work)
    ("doctor says you need to take medicine", "Interpreter→Patient"),
    ("patient says I have a headache", "Interpreter→Doctor"),
    ("doctor told me to tell you", "Interpreter→Patient"),
    ("patient asked about the medication", "Interpreter→Doctor"),
    ("doctor wants you to come back next week", "Interpreter→Patient"),
    ("patient wants to know if it's serious", "Interpreter→Doctor"),
    ("doctor mentioned the test results", "Interpreter→Patient"),
    ("patient mentioned feeling dizzy", "Interpreter→Doctor"),
    
    # Edge cases
    ("what the doctor said is important", "Interpreter→Patient"),
    ("what the patient told me earlier", "Interpreter→Doctor"),
]

print("=" * 60)
print("INTERPRETER DETECTION TEST")
print("=" * 60)

passed = 0
failed = 0

for text, expected_role in test_cases:
    # Reset detector for each test to avoid role locking
    detector.speaker_scores.clear()
    detector.role_assignments.clear()
    
    detected_role = detector.detect_speaker_role(
        speaker_id=f"test_speaker_{passed + failed}",
        text=text,
        language="en"
    )
    
    status = "✓ PASS" if detected_role == expected_role else "✗ FAIL"
    if detected_role == expected_role:
        passed += 1
    else:
        failed += 1
    
    print(f"\n{status}")
    print(f"  Text: '{text}'")
    print(f"  Expected: {expected_role}")
    print(f"  Got: {detected_role}")

print("\n" + "=" * 60)
print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
print("=" * 60)

if failed == 0:
    print("\n✅ All tests passed! Interpreter detection is working correctly.")
else:
    print(f"\n⚠️ {failed} test(s) failed. Review the output above.")
