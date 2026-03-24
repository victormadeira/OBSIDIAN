from fastapi import APIRouter
from app.services.graph_service import get_full_graph, get_ego_graph

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("")
def full_graph():
    return get_full_graph()


@router.get("/{note_id}")
def ego_graph(note_id: str, depth: int = 1):
    return get_ego_graph(note_id, depth)
