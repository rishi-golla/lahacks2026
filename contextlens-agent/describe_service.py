import os
import asyncio

_LOW_CONFIDENCE_MARKERS = [
    "cannot",
    "not find",
    "unclear",
    "no information",
    "don't have",
    "unable",
]


async def get_scene_description(image_context: str) -> dict:
    """Describe a scene given a text description of image context using Gemini."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {
            "description": "API key not configured.",
            "confidence": "low",
            "source": "gemini",
        }

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = (
            "You are describing a scene for a visually impaired user. "
            "Given the following image context, provide a clear and concise spoken description "
            "of what is in the scene in 2-3 sentences. Write for spoken audio.\n\n"
            f"Image context: {image_context}"
        )

        response = await asyncio.to_thread(model.generate_content, prompt)
        text = response.text.strip()

        text_lower = text.lower()
        confidence = "low" if any(m in text_lower for m in _LOW_CONFIDENCE_MARKERS) else "high"

        return {
            "description": text,
            "confidence": confidence,
            "source": "gemini",
        }

    except Exception as exc:
        return {
            "description": f"Error retrieving scene description: {exc}",
            "confidence": "low",
            "source": "gemini",
        }
