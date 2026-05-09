from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=8000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: List[ChatMessage] = Field(default=[], max_length=50)
    use_web_search: bool = False


class Source(BaseModel):
    filename: str
    excerpt: str
    score: float


class WebResult(BaseModel):
    title: str
    url: str
    snippet: str


class ChatResponse(BaseModel):
    message: str
    sources: List[Source] = []
    web_results: List[WebResult] = []
    suggestions: List[str] = []


class StatusResponse(BaseModel):
    total_chunks: int
    indexed_files: List[str]
    last_sync: Optional[str]
    model: str
