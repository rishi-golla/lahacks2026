from pydantic import BaseModel


class PersonQuery(BaseModel):
    name: str
    organization: str
    title: str = ""


class PersonContext(BaseModel):
    summary: str
    confidence: str  # 'high' or 'low'
    source: str = "gemini"
