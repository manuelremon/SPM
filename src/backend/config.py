from __future__ import annotations

import os
import secrets
from typing import List


def _split_csv(env: str, default: str) -> List[str]:
    raw = os.getenv(env, default)
    return [x.strip() for x in raw.split(",") if x.strip()]


def _env_flag(name: str, default: str = "0") -> bool:
    raw = os.getenv(name, default)
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    BASE_DIR = os.path.dirname(__file__)
    DATA_DIR = os.path.join(BASE_DIR, "data")
    LOGS_DIR = os.path.join(BASE_DIR, "logs")
    UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")

    DB_PATH = os.getenv("SPM_DB_PATH", os.path.join(DATA_DIR, "spm.db"))
    LOG_PATH = os.getenv("SPM_LOG_PATH", os.path.join(LOGS_DIR, "app.log"))

    ENV = os.getenv("SPM_ENV", "development")
    DEBUG = _env_flag("SPM_DEBUG", "1" if ENV.lower() != "production" else "0")

    _secret_from_env = os.getenv("SPM_SECRET_KEY")
    if _secret_from_env:
        SECRET_KEY = _secret_from_env
    elif DEBUG:
        SECRET_KEY = secrets.token_urlsafe(48)
    else:
        raise RuntimeError("SPM_SECRET_KEY must be defined when DEBUG is disabled")

    ACCESS_TOKEN_TTL = int(os.getenv("SPM_ACCESS_TTL", "3600"))
    TOKEN_TTL = int(os.getenv("SPM_TOKEN_TTL", str(ACCESS_TOKEN_TTL)))

    COOKIE_SAMESITE = os.getenv("SPM_COOKIE_SAMESITE", "Strict") or "Strict"
    if os.getenv("SPM_COOKIE_SECURE") is not None:
        COOKIE_SECURE = _env_flag("SPM_COOKIE_SECURE", "0")
    else:
        COOKIE_SECURE = not DEBUG
    COOKIE_ARGS = {
        "secure": COOKIE_SECURE,
        "httponly": True,
        "samesite": COOKIE_SAMESITE,
    }

    REFRESH_GRACE_PERIOD = int(os.getenv("SPM_REFRESH_GRACE_PERIOD", "300"))

    CORS_ORIGINS = _split_csv("SPM_CORS_ORIGINS", "http://127.0.0.1:10000")
    OLLAMA_ENDPOINT = os.getenv("SPM_OLLAMA_URL", "http://127.0.0.1:11434")
    OLLAMA_MODEL = os.getenv("SPM_OLLAMA_MODEL", "mistral")

    # Configuracion de IA
    AI_ENABLE: bool = bool(int(os.getenv("AI_ENABLE", "1")))
    AI_EMBED_MODEL: str = os.getenv("AI_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    AI_PRICE_SMOOTHING: float = float(os.getenv("AI_PRICE_SMOOTHING", "0.5"))
    AI_MAX_SUGGESTIONS: int = int(os.getenv("AI_MAX_SUGGESTIONS", "5"))

    # Configuracion de archivos adjuntos
    MAX_CONTENT_LENGTH = int(os.getenv("SPM_MAX_CONTENT_LENGTH", str(16 * 1024 * 1024)))
    ALLOWED_EXTENSIONS = {"txt", "pdf", "png", "jpg", "jpeg", "gif", "doc", "docx", "xls", "xlsx", "csv"}

    STATUS_TIMEOUT_MS = int(os.getenv("STATUS_TIMEOUT_MS", "2000"))
    STATUS_CACHE_SECS = int(os.getenv("STATUS_CACHE_SECS", "30"))
    STATUS_CHECK_GITHUB = os.getenv("STATUS_CHECK_GITHUB", "1").strip().lower() not in {"0", "false", "no"}
    STATUS_CHECK_RENDER = os.getenv("STATUS_CHECK_RENDER", "1").strip().lower() not in {"0", "false", "no"}
    STATUS_CHECK_OLLAMA = os.getenv("STATUS_CHECK_OLLAMA", "1").strip().lower() not in {"0", "false", "no"}

    @classmethod
    def ensure_dirs(cls) -> None:
        os.makedirs(os.path.dirname(cls.DB_PATH), exist_ok=True)
        os.makedirs(os.path.dirname(cls.LOG_PATH), exist_ok=True)
        os.makedirs(cls.UPLOADS_DIR, exist_ok=True)


class Config:
    DEBUG = True
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5000")
    COOKIE_NAME = os.getenv("COOKIE_NAME", "session")
    COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "Lax")  # Lax|None|Strict
    COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0") == "1"
    UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    ALLOWED_EXTS = {'.png','.jpg','.jpeg','.pdf','.csv','.txt'}
    ALLOWED_MIMES = {
      'image/png','image/jpeg','application/pdf','text/csv','text/plain'
    }
