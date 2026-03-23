from fastapi import APIRouter, Request
import httpx

from app.storage import MEETINGS
from app.summary import generate_summaries

router = APIRouter(prefix="/webhook", tags=["webhook"])

RECALL_API_KEY = "YOUR_RECALL_API_KEY"


# 1️⃣ WEBHOOK HANDLER
@router.post("/recall")
async def recall_webhook(request: Request):
    payload = await request.json()

    event = payload.get("event")
    data = payload.get("data", {})

    meeting_id = data.get("meeting_id")

    if event == "meeting_started":
        MEETINGS[meeting_id] = {"status": "started"}

    elif event == "meeting_ended":
        if meeting_id in MEETINGS:
            MEETINGS[meeting_id]["status"] = "ended"

    elif event == "transcript_ready":
        transcript_id = data.get("transcript_id")

        await process_transcript(meeting_id, transcript_id)

    return {"status": "ok"}


# 2️⃣ FETCH TRANSCRIPT
async def fetch_transcript(transcript_id: str):
    url = f"https://api.recall.ai/v1/transcripts/{transcript_id}"

    headers = {
        "Authorization": f"Bearer {RECALL_API_KEY}"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        return response.json()


# 3️⃣ PROCESS TRANSCRIPT
async def process_transcript(meeting_id: str, transcript_id: str):
    data = await fetch_transcript(transcript_id)

    segments = data.get("segments", [])
    participants = data.get("participants", [])

    # Step 1: Speaker mapping
    speaker_map = build_speaker_map(participants)

    # Step 2: Group by speaker
    grouped = {}

    for seg in segments:
        speaker = seg.get("speaker")  # speaker_0
        text = seg.get("text")

        name = speaker_map.get(speaker, speaker)

        grouped.setdefault(name, []).append(text)

    # Step 3: Generate summaries
    summaries = await generate_summaries(grouped)

    # Step 4: Store result
    MEETINGS[meeting_id] = {
        "status": "completed",
        "summary": summaries
    }


# 4️⃣ SPEAKER MAPPING
def build_speaker_map(participants):
    mapping = {}

    for p in participants:
        speaker = p.get("speaker")   # speaker_0
        name = p.get("name")         # John

        if speaker and name:
            mapping[speaker] = name

    return mapping


# 5️⃣ GET SUMMARY API
@router.get("/summary/{meeting_id}")
async def get_summary(meeting_id: str):
    meeting = MEETINGS.get(meeting_id)

    if not meeting:
        return {"message": "Meeting not found"}

    if "summary" not in meeting:
        return {"message": "Summary not ready yet"}

    return {
        "meeting_id": meeting_id,
        "summary": meeting["summary"]
    }