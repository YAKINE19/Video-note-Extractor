"""Video Note Extractor — FastAPI application entry point."""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from api.routes import video, notes, chat, export

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log = logging.getLogger(__name__)
    log.info("Starting in %s mode", settings.mode)

    if settings.use_groq:
        log.info(
            "Groq API: model=%s  whisper=%s",
            settings.groq_model,
            settings.groq_whisper_model,
        )
    else:
        log.info(
            "Ollama: %s  model=%s  whisper=%s",
            settings.ollama_base_url,
            settings.ollama_model,
            settings.whisper_model,
        )
        from services.summarizer import check_ollama
        status = check_ollama()
        if status["ok"]:
            log.info("Ollama reachable. Models: %s", status["models"])
            if settings.ollama_model not in status["models"]:
                log.warning(
                    "Model '%s' not pulled yet. Run: ollama pull %s",
                    settings.ollama_model, settings.ollama_model,
                )
        else:
            log.warning(
                "Ollama not reachable at %s — start with: ollama serve",
                settings.ollama_base_url,
            )
    yield


app = FastAPI(
    title="Video Note Extractor",
    description=(
        "Extract transcripts, structured notes, and Q&A from any video. "
        "100%% free — local (Ollama + Whisper) or cloud (Groq free API)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/api/v1/sessions"
app.include_router(video.router,  prefix=PREFIX, tags=["Sessions"])
app.include_router(notes.router,  prefix=PREFIX, tags=["Notes"])
app.include_router(chat.router,   prefix=PREFIX, tags=["Chat"])
app.include_router(export.router, prefix=PREFIX, tags=["Export"])


@app.get("/health", tags=["Health"])
def health():
    info: dict = {
        "status": "ok",
        "mode": settings.mode,
        "whisper": settings.groq_whisper_model if settings.use_groq else settings.whisper_model,
        "llm": settings.groq_model if settings.use_groq else settings.ollama_model,
    }
    if not settings.use_groq:
        from services.summarizer import check_ollama
        info["ollama"] = check_ollama()
    return info


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", settings.api_port))
    uvicorn.run("main:app", host=settings.api_host, port=port, reload=True)
