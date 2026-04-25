import os
import asyncio

_LOW_CONFIDENCE_MARKERS = [
    "cannot",
    "not find",
    "unclear",
    "no information",
    "don't have",
]


async def get_person_context(name: str, org: str, title: str) -> dict:
    """Fetch professional context for a person using Gemini."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {
            "summary": "API key not configured.",
            "confidence": "low",
            "source": "gemini",
        }

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        title_clause = f", {title}" if title else ""
        prompt = (
            f"Write exactly 2 spoken sentences about {name}{title_clause} at {org}, "
            "describing their professional role and most notable work. "
            "Write for spoken audio — natural, concise, and clear. "
            "If you cannot find enough information about this person, say so in 1 sentence."
        )

        response = await asyncio.to_thread(model.generate_content, prompt)
        text = response.text.strip()

        text_lower = text.lower()
        confidence = "low" if any(m in text_lower for m in _LOW_CONFIDENCE_MARKERS) else "high"

        return {
            "summary": text,
            "confidence": confidence,
            "source": "gemini",
        }

    except Exception as exc:
        return {
            "summary": f"Error retrieving context: {exc}",
            "confidence": "low",
            "source": "gemini",
        }
