"""
Test script to verify Vertex AI integration.
Run this to ensure your credentials and setup are working correctly.
"""
import os
import asyncio
from pathlib import Path

# Set credentials path
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(
    Path(__file__).parent / "gcp-credentials.json"
)

from app.vertex_ai_client import VertexAIClient


async def test_vertex_ai():
    """Test Vertex AI client functionality."""
    
    print("=" * 60)
    print("🧪 Testing Vertex AI Integration")
    print("=" * 60)
    
    # Initialize client
    print("\n1️⃣ Initializing Vertex AI client...")
    try:
        client = VertexAIClient()
        print("✅ Client initialized successfully!")
        print(f"   Project: {client.project_id}")
        print(f"   Location: {client.location}")
        print(f"   Model: {client.model_id}")
    except Exception as e:
        print(f"❌ Failed to initialize client: {e}")
        return
    
    # Test interpretation quality analysis
    print("\n2️⃣ Testing interpretation quality analysis...")
    try:
        result = await client.analyze_interpretation_quality(
            doctor_text="You need to take two tablets in the morning and one at night.",
            interpreter_text="Necesitas tomar pastillas por la mañana y noche.",
            language_pair="en-es"
        )
        
        print("✅ Analysis completed successfully!")
        print(f"\n📊 Results:")
        print(f"   Flags detected: {len(result.get('flags', []))}")
        
        for i, flag in enumerate(result.get('flags', []), 1):
            print(f"\n   Flag {i}:")
            print(f"   - Type: {flag.get('error_type')}")
            print(f"   - Severity: {flag.get('severity')}")
            print(f"   - Confidence: {flag.get('confidence', 0) * 100:.0f}%")
            print(f"   - Reasoning: {flag.get('reasoning')}")
            print(f"   - Category: {flag.get('category')}")
        
        if not result.get('flags'):
            print("   ℹ️ No compliance issues detected")
            
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test with a correct interpretation
    print("\n3️⃣ Testing with correct interpretation...")
    try:
        result = await client.analyze_interpretation_quality(
            doctor_text="Good morning, how are you feeling today?",
            interpreter_text="Buenos días, ¿cómo se siente hoy?",
            language_pair="en-es"
        )
        
        print("✅ Analysis completed successfully!")
        print(f"   Flags detected: {len(result.get('flags', []))}")
        
        if not result.get('flags'):
            print("   ✅ No issues - interpretation is accurate!")
            
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return
    
    print("\n" + "=" * 60)
    print("✅ All tests passed! Vertex AI is ready to use.")
    print("=" * 60)
    print("\n📝 Next steps:")
    print("   1. Start the server: python -m uvicorn app.main:app --reload")
    print("   2. Visit: http://localhost:8000/transcript-review")
    print("   3. Test the API: http://localhost:8000/docs")
    print()


if __name__ == "__main__":
    asyncio.run(test_vertex_ai())
