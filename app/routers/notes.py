from fastapi import APIRouter, HTTPException
from app.models import NoteCreate, NoteUpdate
from app.services import note_service

router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.get("")
def list_notes():
    return note_service.list_notes()


@router.post("", status_code=201)
def create_note(data: NoteCreate):
    try:
        return note_service.create_note(data.title, data.content, data.tags)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{note_id}")
def get_note(note_id: str):
    note = note_service.get_note(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.put("/{note_id}")
def update_note(note_id: str, data: NoteUpdate):
    note = note_service.update_note(note_id, data.title, data.content, data.tags)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.delete("/{note_id}")
def delete_note(note_id: str):
    if not note_service.delete_note(note_id):
        raise HTTPException(status_code=404, detail="Note not found")
    return {"ok": True}
