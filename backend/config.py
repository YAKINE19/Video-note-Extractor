from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # ── Mode auto-detection ────────────────────────────────────────────────────
    # If GROQ_API_KEY is set  → "cloud" mode: Groq API (no torch, fits free tier)
    # If not set              → "local" mode: Ollama + local Whisper + ChromaDB
    groq_api_key: Optional[str] = None

    # ── Groq (cloud, free) ─────────────────────────────────────────────────────
    # Get a free key at https://console.groq.com — no credit card required
    # Free limits: ~14,400 LLM req/day, ~7,200 Whisper req/day
    groq_model: str = "llama-3.1-8b-instant"       # fast + free
    groq_whisper_model: str = "whisper-large-v3-turbo"

    # ── Ollama (local, zero cost) ──────────────────────────────────────────────
    # Install: https://ollama.com  |  brew install ollama
    # Start:   ollama serve && ollama pull llama3.2
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # ── Whisper (local, used when groq_api_key is NOT set) ────────────────────
    # tiny | base | small | medium | large-v3
    whisper_model: str = "base"

    # ── Embeddings (local, only used in local mode) ───────────────────────────
    embed_model: str = "all-MiniLM-L6-v2"

    # ── Storage ────────────────────────────────────────────────────────────────
    upload_dir: str = "./data/uploads"
    audio_dir: str = "./data/audio"
    chroma_persist_dir: str = "./data/chroma"

    # ── RAG (local mode only) ─────────────────────────────────────────────────
    chunk_size: int = 500
    chunk_overlap: int = 50
    rag_top_k: int = 5

    # ── Server ─────────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_url: str = "http://localhost:8501"

    @property
    def use_groq(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def mode(self) -> str:
        return "cloud (Groq)" if self.use_groq else "local (Ollama)"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

for _dir in (settings.upload_dir, settings.audio_dir, settings.chroma_persist_dir):
    os.makedirs(_dir, exist_ok=True)
