import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import (
    STATIC_DIR, EMBEDDING_PROVIDER, EMBEDDING_MODEL,
    EMBEDDING_API_KEY, OLLAMA_BASE_URL, AUTO_REINDEX,
)
from app.database import init_db
from app.services.note_service import scan_vault
from app.routers import notes, search, links, tags, context, semantic
from app.routers import vectors

logger = logging.getLogger(__name__)

app = FastAPI(title="OBSIDIAN", version="2.0.0")

# Include API routers
app.include_router(notes.router)
app.include_router(search.router)
app.include_router(links.router)
app.include_router(tags.router)
app.include_router(context.router)
app.include_router(semantic.router)
app.include_router(vectors.router)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
def startup():
    init_db()
    scan_vault()

    # Initialize vector service (non-blocking — app works without it)
    from app.services.vector_service import init_vector_service, is_available, reindex_all

    kwargs = {}
    model = EMBEDDING_MODEL or None
    if EMBEDDING_PROVIDER == "openai" and EMBEDDING_API_KEY:
        kwargs["api_key"] = EMBEDDING_API_KEY
    if EMBEDDING_PROVIDER == "ollama":
        kwargs["base_url"] = OLLAMA_BASE_URL

    success = init_vector_service(
        provider_type=EMBEDDING_PROVIDER,
        model_name=model,
        **kwargs,
    )

    if success and AUTO_REINDEX and is_available():
        from app.services.vector_service import _collection
        if _collection.count() == 0:
            logger.info("No vectors found — running initial indexing...")
            result = reindex_all()
            logger.info(f"Initial indexing: {result}")


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))
