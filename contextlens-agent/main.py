import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from context_service import get_person_context
from describe_service import get_scene_description

app = FastAPI(title="ContextLens Agent API", version="1.0.0")


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    messages: List[ChatMessage]


class ChatCompletionResponseMessage(BaseModel):
    role: str
    content: str


class ChatCompletionChoice(BaseModel):
    message: ChatCompletionResponseMessage


class ChatCompletionResponse(BaseModel):
    choices: List[ChatCompletionChoice]


class DescribeRequest(BaseModel):
    image_context: str


class DescribeResponse(BaseModel):
    description: str
    confidence: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    """
    Accepts messages in OpenAI-compatible format.
    Expects the last user message to look like:
        "Identify person: <Name>, <Org>, <Title>"
    """
    user_messages = [m for m in request.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="No user message provided.")

    content = user_messages[-1].content.strip()

    # Parse the task string
    task_body = content
    if content.lower().startswith("identify person:"):
        task_body = content[len("identify person:"):].strip()

    parts = [p.strip() for p in task_body.split(",")]
    name = parts[0] if len(parts) > 0 else ""
    org = parts[1] if len(parts) > 1 else ""
    title = parts[2] if len(parts) > 2 else ""

    result = await get_person_context(name, org, title)
    summary = result["summary"]

    return ChatCompletionResponse(
        choices=[
            ChatCompletionChoice(
                message=ChatCompletionResponseMessage(
                    role="assistant",
                    content=summary,
                )
            )
        ]
    )


@app.post("/v1/describe", response_model=DescribeResponse)
async def describe_scene(request: DescribeRequest):
    """Describe a scene from image context text."""
    result = await get_scene_description(request.image_context)
    return DescribeResponse(
        description=result["description"],
        confidence=result["confidence"],
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8001))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
