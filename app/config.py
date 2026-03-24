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
