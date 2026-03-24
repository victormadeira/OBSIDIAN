from fastapi import APIRouter, Query
from app.services.search_service import search_notes

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
def search(q: str = Query(..., min_length=1)):
    return search_notes(q)
