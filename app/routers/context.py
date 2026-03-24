from fastapi import APIRouter
from app.models import ContextRequest
from app.services.context_builder import build_context

router = APIRouter(prefix="/api/context", tags=["context"])


@router.post("/build")
def build(req: ContextRequest):
    return build_context(
        note_ids=req.note_ids,
        include_linked=req.include_linked,
        depth=req.depth,
        fmt=req.format,
        max_tokens=req.max_tokens_estimate,
        include_metadata=req.include_metadata,
    )
