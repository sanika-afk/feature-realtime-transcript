# summary.py

# app/summary.py

from typing import Dict, List
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key="YOUR_OPENAI_API_KEY")


async def generate_summaries(grouped_data: Dict[str, List[str]]) -> Dict[str, str]:
    summaries = {}

    for name, texts in grouped_data.items():
        combined_text = " ".join(texts)

        prompt = f"""
        Summarize what {name} said in the meeting.

        - Use bullet points
        - Keep it concise
        - Focus on key points

        Conversation:
        {combined_text}
        """

        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a meeting assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )

            summaries[name] = response.choices[0].message.content.strip()

        except Exception as e:
            summaries[name] = f"Error: {str(e)}"

    return summaries

async def generate_summaries(grouped_data: Dict[str, List[str]]) -> Dict[str, str]:
    """
    Generate per-person summaries using OpenAI

    grouped_data example:
    {
        "John": ["text1", "text2"],
        "Priya": ["text3"]
    }
    """

    summaries = {}

    for name, texts in grouped_data.items():
        combined_text = " ".join(texts)

        prompt = f"""
        Summarize what {name} said in the meeting.

        Instructions:
        - Keep it short
        - Use bullet points
        - Focus on key contributions, decisions, or concerns

        Conversation:
        {combined_text}
        """

        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful meeting assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )

            summaries[name] = response.choices[0].message.content.strip()

        except Exception as e:
            summaries[name] = f"Error generating summary: {str(e)}"

    return summaries