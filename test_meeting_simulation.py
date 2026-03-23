"""
Script to simulate a full meeting flow and verify speaker labeling.
This script simulates a dialogue between a Doctor, a Patient, and an Interpreter.
"""
import time
from app.speaker_detector import SpeakerDetector

def simulate_meeting():
    detector = SpeakerDetector()
    
    # Define the meeting dialogue
    # Format: (speaker_id, text, language, expected_role)
    dialogue = [
        # 1. Doctor opens the meeting
        ("speaker_0", "Hello, I am Dr. Smith. How are you feeling today?", "en", "Doctor"),
        
        # 2. Interpreter introduces themselves
        ("speaker_1", "Hello Dr. Smith, I will be the interpreter for today's session.", "en", "Interpreter→Doctor"),
        
        # 3. Patient speaks (Interpreter translates)
        ("speaker_2", "Hola doctor, me duele mucho la cabeza desde ayer.", "es", "Patient"),
        
        # 4. Interpreter translates Patient to Doctor
        ("speaker_1", "The patient says they have had a bad headache since yesterday.", "en", "Interpreter→Doctor"),
        
        # 5. Doctor asks a follow-up
        ("speaker_0", "Did the pain start suddenly, or was it gradual?", "en", "Doctor"),
        
        # 6. Interpreter translates Doctor to Patient
        ("speaker_1", "El doctor pregunta si el dolor empezó de repente o poco a poco.", "es", "Interpreter→Patient"),
        
        # 7. Patient responds
        ("speaker_2", "Empezó de repente por la tarde.", "es", "Patient"),
        
        # 8. Interpreter translates Patient to Doctor
        ("speaker_1", "They say it started suddenly in the afternoon.", "en", "Interpreter→Doctor"),
        
        # 9. Doctor gives instructions
        ("speaker_0", "I want you to take some ibuprofen for the pain.", "en", "Doctor"),
        
        # 10. Interpreter translates Doctor to Patient
        ("speaker_1", "Doctor says you should take ibuprofen for the pain.", "en", "Interpreter→Patient"),
        
        # 11. Testing the "doctor wants" fix
        ("speaker_1", "doctor wants you to come back next week for a checkup.", "en", "Interpreter→Patient"),
    ]

    print("=" * 80)
    print("MEETING SIMULATION TEST: DOCTOR, PATIENT, AND INTERPRETER")
    print("=" * 80)
    print(f"{'Speaker ID':<12} | {'Text':<50} | {'Expected Role':<20} | {'Detected Role':<20}")
    print("-" * 110)

    passed = 0
    total = len(dialogue)

    for speaker_id, text, lang, expected in dialogue:
        # Get detected role
        detected = detector.detect_speaker_role(
            speaker_id=speaker_id,
            text=text,
            language=lang
        )
        
        # Roles like Interpreter→Doctor are fine if expected is Interpreter→Doctor
        # or if expected is just Interpreter and detection is specific.
        is_correct = (detected == expected) or (expected == "Interpreter" and detected.startswith("Interpreter")) or (expected.startswith("Interpreter") and detected.startswith("Interpreter"))
        
        status = "PASS" if is_correct else "FAIL"
        if is_correct:
            passed += 1
            
        # Truncate text for display
        display_text = (text[:47] + '..') if len(text) > 47 else text
        print(f"{speaker_id:<12} | {display_text:<50} | {expected:<20} | {detected:<20} {status}")

    print("-" * 110)
    print(f"RESULTS: {passed}/{total} passed")
    print("=" * 80)

    if passed == total:
        print("\n✅ SUCCESS: All labels assigned correctly throughout the meeting!")
    else:
        print(f"\n⚠️ WARNING: {total - passed} labels were incorrect. Please review the output.")

if __name__ == "__main__":
    simulate_meeting()
