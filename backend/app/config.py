import os

# Load .env if present (very small loader, no extra dependency)
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(_env_path):
    for line in open(_env_path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY is not set. Copy backend/.env.example to backend/.env and "
        "set a unique value, e.g. python -c \"import secrets; print(secrets.token_hex(32))\""
    )
if len(SECRET_KEY.encode("utf-8")) < 32:
    raise RuntimeError("SECRET_KEY must be at least 32 bytes")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./aipulse.db")
AI_MODE = os.getenv("AI_MODE", "mock")  # "mock" or "live"
LLM_API_URL = os.getenv("LLM_API_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
TOKEN_HOURS = 12
PASSWORD_ROUNDS = int(os.getenv("PASSWORD_ROUNDS", "260000"))
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]

if AI_MODE not in ("mock", "live"):
    raise RuntimeError("AI_MODE must be either 'mock' or 'live'")
if AI_MODE == "live" and not all((LLM_API_URL, LLM_API_KEY, LLM_MODEL)):
    raise RuntimeError(
        "LLM_API_URL, LLM_API_KEY, and LLM_MODEL are required when AI_MODE=live"
    )
