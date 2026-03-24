from pydantic import BaseModel
from typing import Optional


class NoteCreate(BaseModel):
    title: str
    content: str = ""
    tags: list[str] = []


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[list[str]] = None


class NoteResponse(BaseModel):
    id: str
    title: str
    content: str
    tags: list[str]
    links: list[dict]
    backlinks: list[dict]
    created_at: str
    updated_at: str


class NoteSummary(BaseModel):
    id: str
    title: str
    tags: list[str]
    link_count: int
    updated_at: str


class SearchResult(BaseModel):
    id: str
    title: str
    snippet: str
    rank: float


class GraphData(BaseModel):
    nodes: list[dict]
    edges: list[dict]


class ContextRequest(BaseModel):
    note_ids: list[str]
    include_linked: bool = True
    depth: int = 1
    format: str = "xml"  # xml | markdown | json
    max_tokens_estimate: int = 8000
    include_metadata: bool = True


class ContextResponse(BaseModel):
    content: str
    format: str
    note_count: int
    estimated_tokens: int
