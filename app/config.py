import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
VAULT_DIR = BASE_DIR / "vault"
DB_PATH = VAULT_DIR / ".obsidian.db"
STATIC_DIR = Path(__file__).resolve().parent / "static"

# Ensure vault directory exists
VAULT_DIR.mkdir(parents=True, exist_ok=True)

# Server
HOST = os.getenv("OBSIDIAN_HOST", "0.0.0.0")
PORT = int(os.getenv("OBSIDIAN_PORT", "8080"))

# ---- Vector / Embedding Configuration ----
# Provider: "local" (offline, sentence-transformers) | "openai" | "ollama"
EMBEDDING_PROVIDER = os.getenv("OBSIDIAN_EMBEDDING_PROVIDER", "local")

# Model name (provider-specific defaults if not set):
#   local:  "all-MiniLM-L6-v2"
#   openai: "text-embedding-3-small"
#   ollama: "nomic-embed-text"
EMBEDDING_MODEL = os.getenv("OBSIDIAN_EMBEDDING_MODEL", "")

# API key for providers that need it (OpenAI)
EMBEDDING_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Ollama base URL
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Auto-reindex on startup if no vectors exist
AUTO_REINDEX = os.getenv("OBSIDIAN_AUTO_REINDEX", "true").lower() == "true"
