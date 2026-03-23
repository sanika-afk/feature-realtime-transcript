import asyncio
import time
import json
from collections import deque
import logging

# Mock objects to mimic the environment in live.py
_recent_frames = deque(maxlen=50)

def _select_best_frame(target_time: float) -> str:
    if not _recent_frames:
        return None
    
    best_frame = None
    min_diff = float('inf')
    
    for ts, frame in _recent_frames:
        diff = abs(target_time - ts)
        if diff < min_diff:
            min_diff = diff
            best_frame = frame
            
    return best_frame

async def test_frame_selection():
    print("Testing frame selection logic...")
    _recent_frames.clear()
    
    # Simulate adding frames with timestamps
    now = time.time()
    for i in range(10):
        # Add a frame every 0.1s
        _recent_frames.append((now + i * 0.1, f"frame_{i}"))
    
    # Test 1: Exact match
    target = now + 0.3
    selected = _select_best_frame(target)
    print(f"Test 1 (Target: {target:.2f}): Selected {selected} (Expected: frame_3)")
    assert selected == "frame_3"
    
    # Test 2: Between frames
    target = now + 0.45
    selected = _select_best_frame(target)
    print(f"Test 2 (Target: {target:.2f}): Selected {selected} (Expected: frame_4 or frame_5)")
    assert selected in ["frame_4", "frame_5"]
    
    # Test 3: Before all frames
    target = now - 1.0
    selected = _select_best_frame(target)
    print(f"Test 3 (Target: {target:.2f}): Selected {selected} (Expected: frame_0)")
    assert selected == "frame_0"
    
    # Test 4: After all frames
    target = now + 2.0
    selected = _select_best_frame(target)
    print(f"Test 4 (Target: {target:.2f}): Selected {selected} (Expected: frame_9)")
    assert selected == "frame_9"
    
    print("Frame selection logic tests passed!")

if __name__ == "__main__":
    asyncio.run(test_frame_selection())
