import asyncio
import time
import logging
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.openai_client import OpenAIClient
from app.compliance_engine import ComplianceEngine
from app.audio_processor import AudioBuffer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_compliance_flow():
    print("\n" + "="*80)
    print("🚀 STARTING INTERPRETATION COMPLIANCE VERIFICATION")
    print("="*80 + "\n")

    # 1. Initialize Components
    try:
        openai_client = OpenAIClient()
    except Exception as e:
        print(f"❌ FAILED to init OpenAI: {e}")
        return

    audio_buffer = AudioBuffer()
    captured_events = []

    async def mock_broadcast(event):
        captured_events.append(event)
        event_type = event.get("event")
        data = event.get("data", {})
        if event_type == "interpretation_accuracy":
            print(f"✅ [EVENT] Interpretation Check: {data.get('issue_type')} ({data.get('severity')})")
            print(f"   Notes: {data.get('notes')}")
        elif event_type == "compliance_event":
            print(f"✅ [EVENT] Compliance: {data.get('speaker')} -> {data.get('issue_type')}")

    engine = ComplianceEngine(openai_client, audio_buffer, mock_broadcast)

    # 2. Simulate Conversation Flow
    
    # Step 1: Doctor Identifies Role and gives instructions
    print("👉 Step 1: Doctor provides dosage instructions...")
    doc_segment = {
        "text": "Take 20mg of this medicine every morning before breakfast.",
        "speaker": "Doctor",
        "start_time": time.time() - 5,
        "end_time": time.time() - 4
    }
    await engine.analyze_segment(doc_segment, [])

    # Step 2: Interpreter provides WRONG translation (Alteration + Omission)
    print("👉 Step 2: Interpreter gives incorrect translation...")
    # Simulate a small delay to mimic real-time
    await asyncio.sleep(1) 
    
    int_segment = {
        "text": "The doctor says take 5mg every night.",
        "speaker": "Interpreter",
        "start_time": time.time() - 3,
        "end_time": time.time() - 2
    }
    await engine.analyze_segment(int_segment, [])

    # Wait for Async LLM task to finish
    print("\n⏳ Waiting for Semantic Analysis (LLM)...")
    await asyncio.sleep(8) # Allow time for LLM response

    # 3. Verify Results
    print("\n" + "="*80)
    print("📊 VERIFICATION RESULTS")
    print("="*80)
    
    found_accuracy_issue = False
    for event in captured_events:
        if event["event"] == "interpretation_accuracy":
            data = event["data"]
            if data["issue_type"] in ["Alteration", "Omission"] and data["severity"] in ["Critical", "Major"]:
                found_accuracy_issue = True
                print(f"✨ SUCCESS: Detected mapping error!")
                print(f"   Expected: 20mg morning | Received: 5mg night")
                print(f"   Severity: {data['severity']}")
    
    if found_accuracy_issue:
        print("\n✅ End-to-End Compliance Flow Verified Successfully.")
    else:
        print("\n❌ FAILED: Accuracy issue was not detected properly.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_compliance_flow())
