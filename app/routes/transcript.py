import httpx
from typing import Dict, List, Tuple

from app.config import RECALL_API_KEY


# 1️⃣ Fetch transcript from Recall
async def fetch_transcript(transcript_id: str) -> dict:
    url = f"https://api.recall.ai/v1/transcripts/{transcript_id}"

    headers = {
        "Authorization": f"Bearer {RECALL_API_KEY}"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()


# 2️⃣ Build speaker mapping
def build_speaker_map(participants: List[dict]) -> Dict[str, str]:
    """
    Converts:
    speaker_0 → John
    """

    mapping = {}

    for p in participants:
        speaker = p.get("speaker")   # e.g. speaker_0
        name = p.get("name")         # e.g. John

        if speaker and name:
            mapping[speaker] = name

    return mapping


# 3️⃣ Group transcript by speaker
def group_transcript_by_speaker(
    segments: List[dict],
    speaker_map: Dict[str, str]
) -> Dict[str, List[str]]:
    """
    Converts transcript into:
    {
        "John": ["text1", "text2"],
        "Priya": ["text3"]
    }
    """

    grouped = {}

    for seg in segments:
        speaker = seg.get("speaker")  # speaker_0
        text = seg.get("text")

        if not text:
            continue

        # Map to real name if available
        name = speaker_map.get(speaker, speaker)

        grouped.setdefault(name, []).append(text)

    return grouped


# 4️⃣ Full processing helper (USED BY WEBHOOK)
async def process_transcript_data(transcript_id: str) -> Tuple[Dict[str, List[str]], dict]:
    """
    Full pipeline:
    fetch → map → group

    Returns:
    - grouped transcript
    - raw data (optional)
    """

    data = await fetch_transcript(transcript_id)

    segments = data.get("segments", [])
    participants = data.get("participants", [])

    speaker_map = build_speaker_map(participants)

    grouped = group_transcript_by_speaker(segments, speaker_map)

    return grouped, data