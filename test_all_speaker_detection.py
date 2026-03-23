"""
Comprehensive test script for all speaker detection improvements.
Tests immediate labeling, interpreter detection, and role accuracy.
"""
from app.speaker_detector import SpeakerDetector

def test_immediate_detection():
    """Test that speakers are labeled from first utterance"""
    print("=" * 70)
    print("TEST 1: IMMEDIATE SPEAKER DETECTION")
    print("=" * 70)
    print("Testing that speakers are labeled correctly from FIRST utterance\n")
    
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
        
        print(f"{status} [{speaker_id}] '{text[:40]}...' → {detected_role}")
    
    print(f"\nRESULTS: {passed}/{len(test_cases)} passed\n")
    return passed, failed


def test_interpreter_variations():
    """Test interpreter phrase variations"""
    print("=" * 70)
    print("TEST 2: INTERPRETER PHRASE VARIATIONS")
    print("=" * 70)
    print("Testing flexible interpreter keyword matching\n")
    
    test_cases = [
        # With "the"
        ("the doctor says you need to take medicine", "Interpreter→Patient"),
        ("the patient says I have a headache", "Interpreter→Doctor"),
        
        # Without "the"
        ("doctor says you need to take medicine", "Interpreter→Patient"),
        ("patient says I have a headache", "Interpreter→Doctor"),
        
        # Other variations
        ("doctor told me to tell you", "Interpreter→Patient"),
        ("patient asked about the medication", "Interpreter→Doctor"),
        ("doctor mentioned the test results", "Interpreter→Patient"),
        ("patient mentioned feeling dizzy", "Interpreter→Doctor"),
        ("what the doctor said is important", "Interpreter→Patient"),
        ("what the patient told me earlier", "Interpreter→Doctor"),
    ]
    
    passed = 0
    failed = 0
    
    for text, expected_role in test_cases:
        detector = SpeakerDetector()
        detector.speaker_scores.clear()
        detector.role_assignments.clear()
        
        detected_role = detector.detect_speaker_role(
            speaker_id=f"test_speaker_{passed + failed}",
            text=text,
            language="en"
        )
        
        is_correct = detected_role == expected_role
        status = "✓ PASS" if is_correct else "✗ FAIL"
        
        if is_correct:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} '{text[:40]}...' → {detected_role}")
    
    print(f"\nRESULTS: {passed}/{len(test_cases)} passed\n")
    return passed, failed


def test_role_persistence():
    """Test that roles persist across multiple utterances"""
    print("=" * 70)
    print("TEST 3: ROLE PERSISTENCE")
    print("=" * 70)
    print("Testing that assigned roles remain consistent\n")
    
    detector = SpeakerDetector()
    
    # First utterance - should lock as Doctor
    role1 = detector.detect_speaker_role("speaker_0", "Take two tablets daily", "en")
    
    # Second utterance - should still be Doctor
    role2 = detector.detect_speaker_role("speaker_0", "Come back next week", "en")
    
    # Third utterance - should still be Doctor
    role3 = detector.detect_speaker_role("speaker_0", "Any questions?", "en")
    
    passed = 0
    failed = 0
    
    if role1 == "Doctor" and role2 == "Doctor" and role3 == "Doctor":
        print(f"✓ PASS speaker_0 remained 'Doctor' across 3 utterances")
        passed += 1
    else:
        print(f"✗ FAIL speaker_0 changed roles: {role1} → {role2} → {role3}")
        failed += 1
    
    print(f"\nRESULTS: {passed}/{passed + failed} passed\n")
    return passed, failed


def main():
    print("\n" + "=" * 70)
    print("COMPREHENSIVE SPEAKER DETECTION TEST SUITE")
    print("=" * 70)
    print()
    
    total_passed = 0
    total_failed = 0
    
    # Run all tests
    p1, f1 = test_immediate_detection()
    total_passed += p1
    total_failed += f1
    
    p2, f2 = test_interpreter_variations()
    total_passed += p2
    total_failed += f2
    
    p3, f3 = test_role_persistence()
    total_passed += p3
    total_failed += f3
    
    # Final summary
    print("=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    print(f"Total Passed: {total_passed}")
    print(f"Total Failed: {total_failed}")
    print(f"Success Rate: {total_passed}/{total_passed + total_failed} ({100 * total_passed / (total_passed + total_failed):.1f}%)")
    print("=" * 70)
    
    if total_failed == 0:
        print("\n✅ ALL TESTS PASSED! Speaker detection is working perfectly.")
    else:
        print(f"\n⚠️ {total_failed} test(s) failed. Review the output above.")
    
    return total_failed == 0


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
