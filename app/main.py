from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import STATIC_DIR
from app.database import init_db
from app.services.note_service import scan_vault
from app.routers import notes, search, links, tags, context

app = FastAPI(title="OBSIDIAN", version="1.0.0")

# Include API routers
app.include_router(notes.router)
app.include_router(search.router)
app.include_router(links.router)
app.include_router(tags.router)
app.include_router(context.router)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
def startup():
    init_db()
    scan_vault()


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))
