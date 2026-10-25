"""Central settings. Everything is overridable from .env, so you never edit code to switch models."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # keeps offline tests working
    load_dotenv = lambda *a, **k: None

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")  # your original model name
FALLBACK_MODELS = [m.strip() for m in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash").split(",") if m.strip()]
ALLOWED_ORIGINS = [o.strip() for o in os.getenv(
    "ALLOWED_ORIGINS",
    "http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:3000,http://localhost:3000,http://localhost:5173",
).split(",") if o.strip()]
CONTEXT_BUDGET_TOKENS = int(os.getenv("CONTEXT_BUDGET_TOKENS", "6000"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "15"))
SKILLS_DIR = BASE_DIR / "skills"
